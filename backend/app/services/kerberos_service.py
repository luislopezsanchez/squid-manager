"""Validación y materialización del keytab de Kerberos (autenticación Negotiate).

El .keytab lo genera el administrador de Active Directory del cliente FUERA de
SquidManager (msktutil u equivalente, con credenciales de administrador de
dominio que este panel no debe pedir ni manejar): se sube ya generado, igual
que el certificado CA del proxy padre.
"""

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

KEYTAB_PATH = Path("/etc/squid/HTTP.keytab")

# Cabecera fija de todo fichero keytab v5 (RFC no numerado, pero es el formato
# que usan tanto MIT Kerberos como Heimdal). Rechazar cualquier otra cosa evita
# que un archivo equivocado (o vacío) quede referenciado en squid.conf sin que
# Squid avise hasta el primer intento de autenticación real.
_KEYTAB_MAGIC = b"\x05"


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
            KEYTAB_PATH.write_bytes(config.keytab_data)
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
