"""Validación y materialización del keytab de Kerberos (autenticación Negotiate).

El .keytab lo genera el administrador de Active Directory del cliente FUERA de
SquidManager (msktutil u equivalente, con credenciales de administrador de
dominio que este panel no debe pedir ni manejar): se sube ya generado, igual
que el certificado CA del proxy padre.
"""

import logging
import os
import struct
from pathlib import Path

logger = logging.getLogger(__name__)

KEYTAB_PATH = Path("/etc/squid/HTTP.keytab")

# En /etc/squid, no en el /etc/krb5.conf real del sistema: es el mismo
# directorio que ya comparten backend y Squid en modo Docker (volumen
# squid-config) y en modo nativo (grupo `proxy`, bit setgid), así que el
# mismo código sirve para los dos despliegues sin distinguir uno de otro. El
# proceso de Squid lo lee de ahí porque KRB5_CONFIG apunta a esta ruta -fijado
# en el Dockerfile (modo Docker) y en un drop-in de systemd (modo nativo)-,
# nunca al /etc/krb5.conf del sistema: si alguien más en la máquina depende
# de una configuración Kerberos distinta, esto no la pisa.
KRB5_CONF_PATH = Path("/etc/squid/krb5.conf")

# Cabecera fija de todo fichero keytab v5 (RFC no numerado, pero es el formato
# que usan tanto MIT Kerberos como Heimdal). Rechazar cualquier otra cosa evita
# que un archivo equivocado (o vacío) quede referenciado en squid.conf sin que
# Squid avise hasta el primer intento de autenticación real.
_KEYTAB_MAGIC = b"\x05"

# Tipos de cifrado DES clásicos (RFC 3961 / valores de enctype de MIT krb5):
# des-cbc-crc=1, des-cbc-md4=2, des-cbc-md5=3. `ktpass -crypto All` en Windows
# los sigue generando porque cubre TODO lo que un KDC pueda haber elegido
# históricamente, pero MIT Kerberos >= 1.18 (Ubuntu 24.04 trae 1.20) eliminó
# el soporte de DES del todo, no solo lo desalienta. Un keytab que aún los
# trae puede romper gss_accept_sec_context() al aceptar el contexto -"Bad
# encryption type"- antes de llegar siquiera a las entradas AES/RC4 válidas,
# aunque esas sí estén presentes. Confirmado en vivo: el mismo keytab dejó de
# fallar en cuanto se le quitaron esas dos entradas.
_ENCTYPES_DES = {1, 2, 3}


def validar_keytab(data: bytes) -> tuple[bool, str]:
    """Comprueba que el archivo subido tenga pinta de keytab de verdad."""
    if not data:
        return False, "El archivo está vacío."
    if len(data) < 8:
        return False, "El archivo es demasiado pequeño para ser un keytab válido."
    if data[0:1] != _KEYTAB_MAGIC:
        return False, (
            "Eso no parece un archivo .keytab: no empieza con la cabecera "
            "esperada (0x05). Verifica que sea el archivo que generó msktutil "
            "y no, por ejemplo, un volcado de texto."
        )
    return True, "Keytab válido"


def quitar_entradas_des(data: bytes) -> bytes:
    """Devuelve el keytab sin las entradas DES, o el original si algo no cuadra.

    Formato binario del keytab (versión 0x0502, la que produce `ktpass` en
    Windows y `ktutil`): una cabecera de 2 bytes, y una lista de entradas
    variable, cada una precedida por su longitud en 4 bytes (con signo: si es
    negativa, es un hueco/entrada borrada, se salta sin más). Dentro de cada
    entrada, tras el principal (número de componentes + reino + componentes,
    todos con su propia longitud) vienen name_type, timestamp, el VNO de 8
    bits y recién ahí el enctype de 2 bytes que decide si la entrada se
    conserva. No hace falta tocar nada más del contenido de la entrada: se
    conserva byte a byte tal cual, solo se decide incluirla o no.

    Solo actúa sobre el formato 0x0502; cualquier otra cosa (versión
    distinta, o un parseo que no cierra) devuelve el dato de entrada sin
    tocar -mejor un keytab con DES de más que uno corrupto por una asunción
    equivocada sobre su formato-.
    """
    if len(data) < 2 or data[0:2] != b"\x05\x02":
        return data

    try:
        pos = 2
        entradas = []
        while pos + 4 <= len(data):
            (longitud,) = struct.unpack_from(">i", data, pos)
            pos += 4
            if longitud == 0:
                continue
            if longitud < 0:
                # Hueco de una entrada borrada: se salta sin conservar nada.
                pos += -longitud
                continue

            entrada = data[pos:pos + longitud]
            if len(entrada) != longitud:
                return data  # el fichero se corta antes de lo declarado
            pos += longitud

            epos = 0
            (num_componentes,) = struct.unpack_from(">H", entrada, epos); epos += 2
            (largo_reino,) = struct.unpack_from(">H", entrada, epos); epos += 2
            epos += largo_reino
            for _ in range(num_componentes):
                (largo_comp,) = struct.unpack_from(">H", entrada, epos); epos += 2
                epos += largo_comp
            epos += 4  # name_type (uint32, solo en formato 0x0502)
            epos += 4  # timestamp
            epos += 1  # vno de 8 bits
            (enctype,) = struct.unpack_from(">H", entrada, epos)

            entradas.append((enctype, longitud, entrada))

        if not any(enctype in _ENCTYPES_DES for enctype, _, _ in entradas):
            return data  # nada que quitar: no reescribir sin necesidad

        salida = bytearray(b"\x05\x02")
        for enctype, longitud, entrada in entradas:
            if enctype in _ENCTYPES_DES:
                continue
            salida += struct.pack(">i", longitud)
            salida += entrada
        return bytes(salida)
    except struct.error:
        return data


def kerberos_activo(config) -> bool:
    """¿Debe ofrecerse Negotiate? Activado en el panel Y con un keytab real.

    Única fuente de verdad para esta pregunta: config_generator (si declarar
    el bloque `auth_param negotiate`), escribir_keytab (si escribir el
    archivo) y la plantilla la consultan a través de esta función, para que
    las tres decisiones no puedan divergir entre sí — antes cada una repetía
    su propia versión de la condición, y coincidían solo porque una de ellas
    (la plantilla) volvía a repetir el `enabled` que otra (config_generator)
    había dejado fuera.
    """
    return bool(
        config
        and getattr(config, "enabled", False)
        and getattr(config, "keytab_data", None)
    )


def escribir_keytab(config) -> bool:
    """Deja el keytab en el volumen que lee el helper de Squid.

    Devuelve si hay un keytab en uso, que es lo que decide si el squid.conf
    debe declarar el bloque de autenticación Negotiate. Si no lo hay, el
    fichero se retira: dejarlo con contenido viejo referenciaría un keytab que
    ya no corresponde a la configuración activa.
    """
    try:
        tiene_keytab = kerberos_activo(config)
        if tiene_keytab:
            KEYTAB_PATH.parent.mkdir(parents=True, exist_ok=True)
            KEYTAB_PATH.write_bytes(quitar_entradas_des(config.keytab_data))
            # El keytab equivale a la contraseña de la cuenta de equipo del
            # proxy en el AD: legible solo por el usuario que corre Squid.
            os.chmod(KEYTAB_PATH, 0o640)
            # uid/gid reales del usuario 'proxy', no un 13:13 fijo: en una
            # instalacion nativa donde ese usuario se creo con otro id (el
            # paquete de Squid usa el primer id libre si 13 ya estaba tomado)
            # un valor fijo dejaria el keytab con el propietario equivocado
            # sin ningun aviso. Mismo resolutor que usa squid_service.py para
            # la contraseña de bind LDAP y el htpasswd.
            from app.services.squid_service import _proxy_ids

            try:
                os.chown(KEYTAB_PATH, *_proxy_ids())
            except (PermissionError, OSError) as e:
                logger.warning(f"No se pudo cambiar el propietario del keytab: {e}")
            logger.info("Keytab de Kerberos escrito")
            return True

        if KEYTAB_PATH.exists():
            KEYTAB_PATH.unlink()
            logger.info("Keytab de Kerberos retirado (Negotiate desactivado o sin keytab)")
        return False
    except Exception as e:
        logger.error(f"Error escribiendo el keytab de Kerberos: {e}")
        return False


def _krb5_conf(realm: str) -> str:
    """Contenido de krb5.conf para el realm indicado.

    Sin este archivo, libkrb5 usa sus valores por defecto, que en MIT
    Kerberos moderno (1.18+, lo que trae Ubuntu 24.04 y Debian 12) rechazan
    RC4-HMAC -el tipo de cifrado más común en un Active Directory real, salvo
    que el dominio esté forzado a solo-AES- con "Bad encryption type", y
    eliminaron el soporte de DES del todo. Confirmado en vivo contra un AD
    real: la autenticación fallaba siempre, con un keytab válido y sin ningún
    otro error de por medio, hasta escribir este archivo.

    `dns_lookup_kdc = true` en vez de fijar un KDC a mano: un Active
    Directory de verdad ya publica sus controladores de dominio por SRV
    (`_kerberos._tcp.<realm>`), que es lo que este proxy va a tener siempre
    -la alternativa, pedir la IP del KDC en el panel, es un dato más para
    pedirle al administrador y una fuente más de desincronización si el AD
    cambia de controlador-. `dns_lookup_realm = false` porque el realm ya lo
    fija el panel, no hace falta adivinarlo de un PTR.

    El mapeo `[domain_realm]` asume que el dominio DNS es el realm en
    minúsculas, que es como Active Directory nombra sus dominios siempre -no
    una convención que el administrador podría romper, es inherente a como
    funciona un dominio de AD-.
    """
    dominio = realm.lower()
    return (
        "[libdefaults]\n"
        f"    default_realm = {realm}\n"
        "    dns_lookup_realm = false\n"
        "    dns_lookup_kdc = true\n"
        "    rdns = false\n"
        "    permitted_enctypes = aes256-cts-hmac-sha1-96 aes128-cts-hmac-sha1-96 rc4-hmac\n"
        "    allow_weak_crypto = true\n"
        "\n"
        "[domain_realm]\n"
        f"    .{dominio} = {realm}\n"
        f"    {dominio} = {realm}\n"
    )


def escribir_krb5_conf(config) -> None:
    """Deja en `/etc/squid/krb5.conf` la configuración que necesita Squid

    para aceptar tickets de un Active Directory real -no solo para tener un
    keytab con las claves correctas, hace falta además que la librería
    Kerberos del sistema permita el tipo de cifrado que el AD emite-. Se
    retira si Kerberos no está activo, igual que el keytab: dejarlo con un
    realm viejo no rompe nada por sí solo, pero es un rastro de una
    configuración que ya no es la vigente.
    """
    try:
        if kerberos_activo(config) and getattr(config, "realm", None):
            KRB5_CONF_PATH.parent.mkdir(parents=True, exist_ok=True)
            KRB5_CONF_PATH.write_text(_krb5_conf(config.realm))
            os.chmod(KRB5_CONF_PATH, 0o644)  # libkrb5 lo lee como el propio Squid, sin secretos dentro
            logger.info("krb5.conf de Kerberos escrito (realm %s)", config.realm)
        elif KRB5_CONF_PATH.exists():
            KRB5_CONF_PATH.unlink()
            logger.info("krb5.conf de Kerberos retirado (Negotiate desactivado o sin keytab)")
    except Exception as e:
        logger.error(f"Error escribiendo krb5.conf de Kerberos: {e}")
