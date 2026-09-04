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

# Mismo uid/gid que usa squid_service.py para todo lo que Squid necesita leer.
PROXY_UID = 13
PROXY_GID = 13

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


def escribir_keytab(config) -> bool:
    """Deja el keytab en el volumen que lee el helper de Squid.

    Devuelve si hay un keytab en uso, que es lo que decide si el squid.conf
    debe declarar el bloque de autenticación Negotiate. Si no lo hay, el
    fichero se retira: dejarlo con contenido viejo referenciaría un keytab que
    ya no corresponde a la configuración activa.
    """
    try:
        tiene_keytab = bool(
            config
            and getattr(config, "enabled", False)
            and getattr(config, "keytab_data", None)
        )
        if tiene_keytab:
            KEYTAB_PATH.parent.mkdir(parents=True, exist_ok=True)
            KEYTAB_PATH.write_bytes(config.keytab_data)
            # El keytab equivale a la contraseña de la cuenta de equipo del
            # proxy en el AD: legible solo por el usuario que corre Squid.
            os.chmod(KEYTAB_PATH, 0o640)
            try:
                os.chown(KEYTAB_PATH, PROXY_UID, PROXY_GID)
            except (PermissionError, OSError):
                pass
            logger.info("Keytab de Kerberos escrito")
            return True

        if KEYTAB_PATH.exists():
            KEYTAB_PATH.unlink()
            logger.info("Keytab de Kerberos retirado (Negotiate desactivado o sin keytab)")
        return False
    except Exception as e:
        logger.error(f"Error escribiendo el keytab de Kerberos: {e}")
        return False
