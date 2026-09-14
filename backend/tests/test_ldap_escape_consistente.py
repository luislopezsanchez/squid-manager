"""Detector de deriva entre las dos copias del escape de filtro LDAP.

Existen DOS implementaciones de `_escapar_filtro_ldap` (RFC 4515):
  - backend/app/routes/ldap.py — usada por el botón "Probar conexión" del panel.
  - squid/auth_helper.py — la que de verdad autentica cada login del proxy.

No se pueden unificar en un solo import: auth_helper.py corre en el runtime
de Squid, fuera del paquete del backend. Este test carga el archivo por
ruta (no como parte del paquete `app`) y compara ambas contra el mismo
juego de casos, para que una corrección aplicada a una sola copia falle
aquí en vez de reabrir en silencio la inyección de filtro LDAP que la
auditoría de seguridad de agosto cerró.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

# squid/auth_helper.py hace `import syslog` a nivel de módulo, exclusivo de
# Unix: cargarlo por ruta (más abajo) revienta la RECOLECCIÓN entera de la
# suite en Windows, no solo este test — sin `--continue-on-collection-errors`
# ni un solo test corre. El destino real del proyecto es Linux, donde este
# test se ejecuta con normalidad; en Windows se omite todo el módulo antes de
# intentar la carga.
if sys.platform == "win32":
    pytest.skip(
        "squid/auth_helper.py importa el módulo syslog (exclusivo de Unix); "
        "el destino real de despliegue es Linux",
        allow_module_level=True,
    )

_AUTH_HELPER_PATH = Path(__file__).parent.parent.parent / "squid" / "auth_helper.py"

# El contenedor squidmgr-backend solo tiene copiado backend/ (ver Dockerfile):
# no existe un directorio squid/ hermano dentro de él, así que esta ruta
# nunca resuelve ahí. Bug real, visto en vivo: correr la suite con
# `docker exec squidmgr-backend python -m pytest tests/` -el comando que la
# propia documentación recomienda (docs/actualizacion.md)- rompía la
# RECOLECCIÓN entera (0 tests corridos, no solo este), porque el error pasaba
# al importar el módulo a nivel de archivo, antes de que pytest pudiera
# aislarlo a un solo test. En instalación nativa, o corriendo la suite desde
# un checkout completo del repo (CI, o dentro del propio contenedor con el
# repo montado), el archivo sí está y el test corre con normalidad.
if not _AUTH_HELPER_PATH.is_file():
    pytest.skip(
        f"{_AUTH_HELPER_PATH} no existe -normal dentro del contenedor Docker "
        "del backend, que solo tiene copiado backend/, no el repo completo-",
        allow_module_level=True,
    )

from app.routes.ldap import _escapar_filtro_ldap as escapar_panel


def _cargar_escapar_helper():
    """Importa squid/auth_helper.py por ruta (no es parte del paquete `app`)."""
    spec = importlib.util.spec_from_file_location("_auth_helper_bajo_prueba", _AUTH_HELPER_PATH)
    modulo = importlib.util.module_from_spec(spec)
    # El propio `import syslog` de auth_helper.py SÍ se ejecuta aquí, al
    # cargar el módulo (por eso el guard de plataforma vive arriba, antes de
    # llegar a este punto). Lo que no se ejecuta es syslog.syslog(): esa
    # llamada vive solo dentro de log_error(), nunca al importar ni al
    # escapar un filtro, así que no hace falta mockear nada más para llamar
    # a _escapar_filtro_ldap una vez que el módulo ya cargó.
    spec.loader.exec_module(modulo)
    return modulo._escapar_filtro_ldap


escapar_helper = _cargar_escapar_helper()


@pytest.mark.parametrize("valor", [
    "usuario.normal",
    "usuario(con)parentesis",
    "usuario*con*asterisco",
    "usuario\\con\\backslash",
    "todo(*)junto\\en\\uno*",
    "usuario\x00con\x00nul",
    "",
    "sin caracteres especiales",
])
def test_ambas_copias_escapan_igual(valor):
    assert escapar_panel(valor) == escapar_helper(valor), (
        f"Las dos copias de _escapar_filtro_ldap divergen para {valor!r}: "
        "backend/app/routes/ldap.py y squid/auth_helper.py deben mantenerse "
        "sincronizadas (ver el docstring de cualquiera de las dos)."
    )
