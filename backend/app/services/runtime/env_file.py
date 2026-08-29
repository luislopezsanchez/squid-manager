"""Escritura del PROXY_PORT en el .env, compartida por los dos runtimes.

Vive aparte porque el .env guarda tambien la contrasena de la base de datos y
la clave de firma de los JWT: la escritura tiene que ser atomica en los dos
modos de despliegue, y tener dos copias de esto era pedir que una se quedara
atras.
"""

import logging
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)


def escribir_puerto(env_file: Path, nuevo_puerto: str) -> tuple[bool, str]:
    """Deja PROXY_PORT=<nuevo_puerto> en el .env indicado, de forma atomica."""
    if not env_file.is_file():
        return False, f"No se encontro el fichero {env_file}"

    try:
        original = env_file.read_text()
    except Exception as e:
        return False, f"No se pudo leer el .env: {e}"

    lines = original.splitlines()
    found = False
    for i, line in enumerate(lines):
        # Solo asignaciones reales: una linea comentada que mencione la
        # variable debe quedarse como esta.
        if re.match(r"^\s*PROXY_PORT\s*=", line):
            lines[i] = f"PROXY_PORT={nuevo_puerto}"
            found = True

    if not found:
        lines.append(f"PROXY_PORT={nuevo_puerto}")

    updated = "\n".join(lines) + "\n"
    if updated == original:
        return True, "El .env ya estaba sincronizado"

    tmp = env_file.with_name(f".env.tmp-{os.getpid()}")
    try:
        # Conservar los permisos del original: lleva secretos.
        mode = env_file.stat().st_mode & 0o777
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
        with os.fdopen(fd, "w") as f:
            f.write(updated)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, env_file)
    except Exception as e:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
        return False, f"No se pudo escribir el .env: {e}"

    logger.info(f".env sincronizado: PROXY_PORT = {nuevo_puerto}")
    return True, f".env actualizado a {nuevo_puerto}"
