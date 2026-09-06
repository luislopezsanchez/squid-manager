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

from app.routes.ldap import _escapar_filtro_ldap as escapar_panel

_AUTH_HELPER_PATH = Path(__file__).parent.parent.parent / "squid" / "auth_helper.py"


def _cargar_escapar_helper():
    """Importa squid/auth_helper.py por ruta (no es parte del paquete `app`)."""
    spec = importlib.util.spec_from_file_location("_auth_helper_bajo_prueba", _AUTH_HELPER_PATH)
    modulo = importlib.util.module_from_spec(spec)
    # syslog.syslog() se llama solo dentro de log_error(), nunca al importar
    # ni al escapar un filtro: no hace falta mockear nada para cargar el
    # módulo ni para llamar a _escapar_filtro_ldap.
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
