"""Salida a Internet a través de otro proxy (proxy padre).

Squid lo resuelve con `cache_peer`. Este servicio se ocupa de lo que hay que
comprobar antes de escribir esa directiva, porque un padre mal configurado no
degrada la navegación: la corta entera, para todos los usuarios a la vez.

La comprobación se hace pidiéndole al padre una URL conocida y mirando qué
contesta. Interesa distinguir cuatro situaciones, porque cada una se arregla de
una forma distinta y el mensaje debe decir cuál es:

  - No se llega al padre (apagado, cortafuegos, host o puerto equivocados).
  - El padre pide credenciales y no se le han dado.
  - El padre pide un método de autenticación que Squid no sabe presentar.
  - El padre responde y deja pasar.

Ese tercer caso merece atención: Squid solo sabe autenticarse contra un padre
con autenticación básica. Si el proxy corporativo exige NTLM o Kerberos —
habitual cuando está integrado con Active Directory— no hay campo que rellenar
que lo resuelva, y conviene decirlo antes de que alguien pierda una tarde
probando usuarios y contraseñas.
"""

import base64
import ipaddress
import logging
import os
import re
import socket
from pathlib import Path

logger = logging.getLogger(__name__)

# El certificado del padre vive en el volumen que comparten backend y Squid.
CA_PADRE_PATH = Path("/etc/squid/parent_ca.crt")

# uid/gid del usuario 'proxy' dentro de la imagen de Squid.
PROXY_UID = 13
PROXY_GID = 13

# Se pide un dominio de Internet cualquiera para ver si el padre lo sirve.
# example.com está reservado por la IANA justo para esto.
URL_DE_PRUEBA = "http://example.com/"
HOST_DE_PRUEBA = "example.com"

TIMEOUT_POR_DEFECTO = 8.0

# Métodos que Squid SÍ puede presentar a un padre con `cache_peer login=`.
METODOS_SOPORTADOS = {"basic"}


def parsear_lista(valor: str | None) -> list[str]:
    """Separa dominios o redes escritos con espacios, comas o saltos de línea."""
    if not valor:
        return []
    normalizado = valor.replace(",", " ").replace("\n", " ").replace("\t", " ")
    return [t for t in normalizado.split() if t]


def validar_destino(host: str | None, port: int | None) -> tuple[bool, str]:
    """Comprueba que el destino tenga sentido antes de intentar nada."""
    if not host or not str(host).strip():
        return False, "Falta la dirección del proxy padre"

    try:
        puerto = int(port)
    except (TypeError, ValueError):
        return False, "El puerto del proxy padre no es un número"

    if not 1 <= puerto <= 65535:
        return False, f"El puerto {puerto} está fuera del rango válido (1-65535)"

    return True, "Destino válido"


METODOS_AUTH_SOPORTADOS = ("fixed", "passthru")


def validar_auth_method_compatible(auth_method: str, db) -> tuple[bool, str]:
    """'passthru' reenvía tal cual las credenciales del cliente hacia el
    padre: es la única forma de llegar a un padre que exige Digest, NTLM o
    Negotiate (login=user:pass de cache_peer solo sabe hacer Basic —
    https://www.squid-cache.org/Doc/config/cache_peer/). Pero HTTP solo
    permite un Proxy-Authorization por petición: si este Squid también
    autentica a SUS clientes (usuarios locales activos, LDAP o Kerberos),
    ese header ya está siendo usado para el desafío local y no queda "hueco"
    para el reenvío. No es una limitación de SquidManager: es como funciona
    la autenticación HTTP orientada a conexión (RFC 7617 / RFC 2617).
    """
    if auth_method not in METODOS_AUTH_SOPORTADOS:
        return False, f"Método de autenticación no soportado: '{auth_method}'."

    if auth_method != "passthru":
        return True, "Compatible"

    from app.models.kerberos_config import KerberosConfig
    from app.models.ldap_config import LdapConfig
    from app.models.proxy_user import ProxyUser

    conflictos = []

    if db.query(ProxyUser).filter(ProxyUser.enabled == True).count() > 0:  # noqa: E712
        conflictos.append("hay usuarios locales del proxy habilitados")

    ldap = db.query(LdapConfig).first()
    if ldap and ldap.enabled:
        conflictos.append("LDAP está habilitado")

    kerberos = db.query(KerberosConfig).first()
    if kerberos and kerberos.enabled and getattr(kerberos, "keytab_data", None):
        conflictos.append("Kerberos está activo")

    if conflictos:
        return False, (
            "El modo 'passthru' reenvía tal cual las credenciales del cliente al "
            "proxy padre, y no se puede combinar con que este mismo Squid "
            "autentique a sus clientes: " + "; ".join(conflictos) + ". "
            "Desactiva la autenticación local (deshabilita los usuarios del "
            "proxy, LDAP y Kerberos) antes de activar 'passthru', o usa 'fixed' "
            "si el padre solo exige Basic."
        )

    return True, "Compatible"


ESQUEMAS_AUTH_CLIENTE_SOPORTADOS = ("basic", "digest", "none")


def validar_proxy_auth_scheme_none(db) -> tuple[bool, str]:
    """'none' deja que Squid pase clientes SIN pedirles usuario/contraseña
    propios: pensado para un Squid HIJO cuyo control de acceso real lo hace
    el proxy padre (o la red que lo rodea), no él mismo.

    Sin un padre configurado y habilitado, 'none' convertiría este Squid en
    un proxy abierto de verdad hacia Internet -cualquiera que alcance el
    puerto navega sin dejar ningún usuario identificable en los logs-, que
    es exactamente el tipo de abuso (relay abierto) que los operadores de
    red bloquean por defecto. Por eso 'none' solo se permite si hay un
    proxy padre configurado Y habilitado: la topología para la que existe
    esta opción siempre tiene uno.
    """
    from app.models.parent_proxy import ParentProxy
    from app.models.user_group import UserGroup

    padre = db.query(ParentProxy).first()
    if not padre or not padre.enabled:
        return False, (
            "El esquema 'none' (sin autenticación local) solo se puede "
            "activar con un proxy padre configurado y habilitado: sin uno, "
            "este Squid quedaría como un proxy abierto hacia Internet, "
            "accesible sin usuario para cualquiera que llegue al puerto. "
            "Configura el proxy padre en Proxy Padre antes de activar "
            "'none', o usa 'basic'/'digest' si este Squid navega "
            "directamente."
        )

    # Los grupos de usuarios se traducen a ACLs `proxy_auth` en squid.conf, y
    # las reglas del panel las referencian por nombre. Sin ningún auth_param
    # declarado (que es justo lo que hace 'none'), esa ACL no se puede
    # emitir -Squid aborta el arranque con "ACL not found" en cuanto una
    # regla la nombre-. Se detecta ANTES de aplicar, no dejando que el
    # generador escriba un squid.conf que Squid va a rechazar.
    if db.query(UserGroup).count() > 0:
        return False, (
            "No se puede activar 'none' con grupos de usuarios existentes: "
            "los grupos se traducen a ACLs que dependen de la autenticación "
            "local, y sin ella Squid no arrancaría. Borra los grupos de "
            "usuarios (y las reglas que los referencien) antes de activar "
            "'none'."
        )

    return True, "Compatible"


def _metodos_ofrecidos(cabeceras: str) -> list[str]:
    """Extrae los métodos de autenticación que anuncia el padre."""
    metodos = []
    for linea in cabeceras.splitlines():
        if linea.lower().startswith("proxy-authenticate:"):
            valor = linea.split(":", 1)[1].strip()
            # "Basic realm=..." -> "basic"
            metodos.append(valor.split()[0].lower() if valor.split() else "")
    return [m for m in metodos if m]


def probar_padre(
    host: str,
    port: int,
    username: str | None = None,
    password: str | None = None,
    timeout: float = TIMEOUT_POR_DEFECTO,
) -> tuple[bool, str]:
    """Pide una URL a través del padre y traduce la respuesta."""
    ok, mensaje = validar_destino(host, port)
    if not ok:
        return False, mensaje

    host = str(host).strip()
    port = int(port)

    peticion = (
        f"GET {URL_DE_PRUEBA} HTTP/1.1\r\n"
        f"Host: {HOST_DE_PRUEBA}\r\n"
        "User-Agent: SquidManager-comprobacion\r\n"
    )
    if username:
        credenciales = base64.b64encode(
            f"{username}:{password or ''}".encode()
        ).decode()
        peticion += f"Proxy-Authorization: Basic {credenciales}\r\n"
    peticion += "Proxy-Connection: close\r\nConnection: close\r\n\r\n"

    sock = None
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.sendall(peticion.encode())

        datos = b""
        while b"\r\n\r\n" not in datos and len(datos) < 65536:
            trozo = sock.recv(4096)
            if not trozo:
                break
            datos += trozo
    except socket.timeout:
        return False, (
            f"{host}:{port} no respondió en {timeout:g} s. Comprueba la "
            f"dirección, el puerto y que el cortafuegos deje salir hasta ahí."
        )
    except socket.gaierror:
        return False, f"No se pudo resolver el nombre «{host}»"
    except ConnectionRefusedError:
        return False, (
            f"{host}:{port} rechazó la conexión. ¿Es ese el puerto del proxy?"
        )
    except OSError as e:
        return False, f"No se pudo conectar con {host}:{port}: {e}"
    finally:
        if sock is not None:
            sock.close()

    if not datos:
        return False, f"{host}:{port} cerró la conexión sin responder"

    cabeceras = datos.split(b"\r\n\r\n", 1)[0].decode("latin-1", errors="replace")
    primera = cabeceras.splitlines()[0] if cabeceras.splitlines() else ""

    codigo_match = re.search(r"HTTP/\d\.\d\s+(\d{3})", primera)
    if not codigo_match:
        return False, f"{host}:{port} no contestó como un proxy HTTP"
    codigo = int(codigo_match.group(1))

    if codigo == 407:
        metodos = _metodos_ofrecidos(cabeceras)
        soportado = any(m in METODOS_SOPORTADOS for m in metodos)

        if metodos and not soportado:
            return False, (
                f"El proxy padre exige autenticación {'/'.join(metodos).upper()}, "
                f"que Squid no sabe presentar a un padre (solo admite Basic). "
                f"Haría falta un intermediario que traduzca la autenticación; "
                f"no se resuelve con usuario y contraseña aquí."
            )
        if not username:
            return False, (
                f"{host}:{port} pide credenciales. Rellena el usuario y la "
                f"contraseña del proxy padre."
            )
        return False, (
            f"{host}:{port} rechazó las credenciales. Revisa el usuario y la "
            f"contraseña."
        )

    if codigo in (200, 301, 302, 303, 307, 308):
        return True, f"{host}:{port} responde y deja salir (HTTP {codigo})"

    if codigo == 403:
        return False, (
            f"{host}:{port} respondió 403: el proxy funciona, pero no permite "
            f"esta salida. Puede que filtre por origen o por destino."
        )

    return False, f"{host}:{port} respondió HTTP {codigo} al intentar salir"


def validar_certificado(pem: str | None) -> tuple[bool, str]:
    """Comprueba que el texto pegado parece un certificado PEM.

    No se valida criptográficamente: basta con descartar lo que Squid no va a
    poder leer, porque ante un fichero ilegible solo deja un WARNING en su log
    y sigue arrancando —sin confiar en el padre—, con lo que el síntoma sería
    otra vez la navegación HTTPS caída sin explicación aparente.
    """
    if not pem or not pem.strip():
        return True, "Sin certificado (el padre no intercepta HTTPS)"

    texto = pem.strip()
    if "-----BEGIN CERTIFICATE-----" not in texto:
        return False, (
            "Eso no parece un certificado PEM: debe empezar por "
            "«-----BEGIN CERTIFICATE-----». Descárgalo del panel del proxy "
            "padre, en Certificado CA."
        )
    if "-----END CERTIFICATE-----" not in texto:
        return False, "El certificado está incompleto: falta la línea final."

    return True, "Certificado válido"


def escribir_ca_padre(config) -> bool:
    """Deja el certificado del padre en el volumen que lee Squid.

    Devuelve si hay certificado en uso, que es lo que decide si el squid.conf
    debe declararlo. Si no lo hay, el fichero se retira: dejarlo con contenido
    viejo haría que Squid confiara en un certificado que ya no toca.
    """
    try:
        if config and getattr(config, "enabled", False) and (config.ca_cert or "").strip():
            CA_PADRE_PATH.parent.mkdir(parents=True, exist_ok=True)
            CA_PADRE_PATH.write_text(config.ca_cert.strip() + "\n")
            # Legible por Squid, que corre como 'proxy'. No es un secreto: un
            # certificado es público por definición.
            os.chmod(CA_PADRE_PATH, 0o644)
            try:
                os.chown(CA_PADRE_PATH, PROXY_UID, PROXY_GID)
            except (PermissionError, OSError):
                pass
            logger.info("Certificado CA del proxy padre escrito")
            return True

        if CA_PADRE_PATH.exists():
            CA_PADRE_PATH.unlink()
            logger.info("Certificado CA del proxy padre retirado")
        return False
    except Exception as e:
        logger.error(f"No se pudo escribir el certificado del proxy padre: {e}")
        return False


def probar_configuracion(config) -> tuple[bool, str]:
    """Comprueba una configuración de proxy padre tal como está guardada."""
    if not config or not getattr(config, "enabled", False):
        return True, "Salida directa a Internet (sin proxy padre)"

    return probar_padre(
        host=config.host,
        port=config.port,
        username=config.username,
        password=config.password,
    )
