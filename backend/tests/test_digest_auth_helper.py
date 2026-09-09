"""Helper de autenticación Digest de Squid (squid/digest_auth_helper.py).

Standalone respecto al backend a propósito (corre dentro del contenedor de
Squid, sin el venv del backend): se importa como script suelto.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

# squid/digest_auth_helper.py hace `import syslog` a nivel de módulo,
# exclusivo de Unix: cargarlo por ruta revienta la RECOLECCIÓN entera de la
# suite en Windows. Mismo guard que test_ldap_escape_consistente.py para
# squid/auth_helper.py. El destino real de despliegue es Linux.
if sys.platform == "win32":
    pytest.skip(
        "squid/digest_auth_helper.py importa el módulo syslog (exclusivo de "
        "Unix); el destino real de despliegue es Linux",
        allow_module_level=True,
    )


def _raiz_del_proyecto() -> Path | None:
    for base in Path(__file__).resolve().parents:
        if (base / "squid" / "digest_auth_helper.py").is_file():
            return base
    return None


@pytest.fixture
def modulo(tmp_path, monkeypatch):
    raiz = _raiz_del_proyecto()
    if raiz is None:
        pytest.skip("el proyecto no esta accesible desde aqui")
    ruta = raiz / "squid" / "digest_auth_helper.py"
    spec = importlib.util.spec_from_file_location("digest_auth_helper", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    archivo = tmp_path / "squid_digest"
    archivo.write_text(
        "jperez:SquidManager Proxy:aabbccdd112233445566778899aabbcc\n"
        "# comentario\n"
        "\n"
        "ana:SquidManager Proxy:00112233445566778899aabbccddeeff\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "DIGEST_FILE", str(archivo))
    return mod


def test_usuario_existente_devuelve_ok_con_ha1(modulo):
    respuesta = modulo.handle('"jperez":"SquidManager Proxy"')
    assert respuesta == 'OK ha1="aabbccdd112233445566778899aabbcc"'


def test_usuario_inexistente_devuelve_err(modulo):
    assert modulo.handle('"nadie":"SquidManager Proxy"') == "ERR"


def test_realm_distinto_no_matchea(modulo):
    """El realm es parte de la clave: un HA1 calculado para otro realm no
    sirve (ver digest_ha1_realm en el modelo ProxyUser)."""
    assert modulo.handle('"jperez":"Otro Realm"') == "ERR"


def test_linea_sin_formato_valido_devuelve_bh(modulo):
    assert modulo.handle("esto no tiene el formato esperado").startswith("BH")


def test_usuario_vacio_devuelve_err(modulo):
    assert modulo.handle('"":"SquidManager Proxy"') == "ERR"


def test_no_consulta_ldap_en_absoluto():
    """Digest solo sabe de usuarios locales: si este archivo empieza a
    importar ldap3 o un allow-list, se rompió esa separación deliberada."""
    raiz = _raiz_del_proyecto()
    fuente = (raiz / "squid" / "digest_auth_helper.py").read_text(encoding="utf-8")
    assert "ldap3" not in fuente
    assert "ldap_allowlist" not in fuente
