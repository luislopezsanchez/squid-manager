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
import re
import socket

logger = logging.getLogger(__name__)

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
