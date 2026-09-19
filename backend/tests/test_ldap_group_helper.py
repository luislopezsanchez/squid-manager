"""Helper de ACL externa de Squid para grupos de LDAP/AD
(squid/ldap_group_helper.py).

Standalone respecto al backend a propósito (corre dentro del contenedor de
Squid, sin el venv del backend): se importa como script suelto, mismo
patrón que test_digest_auth_helper.py.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

if sys.platform == "win32":
    pytest.skip(
        "squid/ldap_group_helper.py importa el módulo syslog (exclusivo de Unix)",
        allow_module_level=True,
    )


def _raiz_del_proyecto() -> Path | None:
    for base in Path(__file__).resolve().parents:
        if (base / "squid" / "ldap_group_helper.py").is_file():
            return base
    return None


class FakeEntry:
    def __init__(self, dn):
        self.entry_dn = dn


class FakeConnection:
    """Responde según un callback que decide, por filtro, qué DNs "existen".

    `responder(search_base, search_filter) -> list[str]` -una lista vacía
    significa "no se encontró nada", igual que un search real sin resultados.
    """

    def __init__(self, responder):
        self._responder = responder
        self.entries = []

    def search(self, search_base, search_filter, search_scope=None, attributes=None):
        dns = self._responder(search_base, search_filter)
        self.entries = [FakeEntry(dn) for dn in dns]
        return bool(self.entries)

    def unbind(self):
        pass


@pytest.fixture
def modulo(tmp_path, monkeypatch):
    raiz = _raiz_del_proyecto()
    if raiz is None:
        pytest.skip("el proyecto no esta accesible desde aqui")
    ruta = raiz / "squid" / "ldap_group_helper.py"
    spec = importlib.util.spec_from_file_location("ldap_group_helper", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    archivo = tmp_path / "ldap_helper.conf"
    archivo.write_text(
        "server_url=ldap://172.30.36.45:389\n"
        "bind_dn=svc@test.com\n"
        "bind_password=secreto\n"
        "search_base=cn=Users,dc=test,dc=com\n"
        "user_filter=(sAMAccountName=%s)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "LDAP_CONF_FILE", str(archivo))
    return mod


def _con_respuesta(monkeypatch, mod, responder):
    monkeypatch.setattr(mod, "_connect", lambda config: FakeConnection(responder))


def test_miembro_directo_devuelve_ok(monkeypatch, modulo):
    def responder(base, filtro):
        if "cn=Ventas" in filtro or "sAMAccountName=Ventas" in filtro:
            return ["CN=Ventas,CN=Users,DC=test,DC=com"]
        if "sAMAccountName=jperez" in filtro:
            return ["CN=Juan Perez,CN=Users,DC=test,DC=com"]
        if filtro.startswith("(member="):
            return ["CN=Ventas,CN=Users,DC=test,DC=com"]  # el usuario SI es member
        return []

    _con_respuesta(monkeypatch, modulo, responder)
    assert modulo.check_group("jperez", "Ventas", "direct") is True


def test_no_miembro_devuelve_false(monkeypatch, modulo):
    def responder(base, filtro):
        if "sAMAccountName=Ventas" in filtro or "cn=Ventas" in filtro:
            return ["CN=Ventas,CN=Users,DC=test,DC=com"]
        if "sAMAccountName=jperez" in filtro:
            return ["CN=Juan Perez,CN=Users,DC=test,DC=com"]
        if filtro.startswith("(member="):
            return []  # no aparece en el grupo
        return []

    _con_respuesta(monkeypatch, modulo, responder)
    assert modulo.check_group("jperez", "Ventas", "direct") is False


def test_grupo_inexistente_devuelve_false_sin_reventar(monkeypatch, modulo):
    _con_respuesta(monkeypatch, modulo, lambda base, filtro: [])
    assert modulo.check_group("jperez", "GrupoQueNoExiste", "direct") is False


def test_usuario_inexistente_devuelve_false(monkeypatch, modulo):
    def responder(base, filtro):
        if "sAMAccountName=Ventas" in filtro or "cn=Ventas" in filtro:
            return ["CN=Ventas,CN=Users,DC=test,DC=com"]
        return []  # el usuario nunca aparece

    _con_respuesta(monkeypatch, modulo, responder)
    assert modulo.check_group("nadie", "Ventas", "direct") is False


def test_modo_nested_usa_la_regla_de_coincidencia_recursiva_de_ad(monkeypatch, modulo):
    llamadas = []

    def responder(base, filtro):
        llamadas.append(filtro)
        if "sAMAccountName=Domain Admins" in filtro or "cn=Domain Admins" in filtro:
            return ["CN=Domain Admins,CN=Users,DC=test,DC=com"]
        if "memberOf:1.2.840.113556.1.4.1941:=" in filtro:
            return ["CN=Juan Perez,CN=Users,DC=test,DC=com"]
        return []

    _con_respuesta(monkeypatch, modulo, responder)
    assert modulo.check_group("jperez", "Domain Admins", "nested") is True
    assert any("1.2.840.113556.1.4.1941" in f for f in llamadas)


def test_modo_direct_no_usa_la_regla_recursiva(monkeypatch, modulo):
    llamadas = []

    def responder(base, filtro):
        llamadas.append(filtro)
        if "Ventas" in filtro and "member=" not in filtro:
            return ["CN=Ventas,CN=Users,DC=test,DC=com"]
        if "sAMAccountName=jperez" in filtro:
            return ["CN=Juan Perez,CN=Users,DC=test,DC=com"]
        if filtro.startswith("(member="):
            return ["CN=Ventas,CN=Users,DC=test,DC=com"]
        return []

    _con_respuesta(monkeypatch, modulo, responder)
    modulo.check_group("jperez", "Ventas", "direct")
    assert not any("1.2.840.113556.1.4.1941" in f for f in llamadas)


def test_sin_configuracion_ldap_devuelve_false(monkeypatch, tmp_path):
    raiz = _raiz_del_proyecto()
    ruta = raiz / "squid" / "ldap_group_helper.py"
    spec = importlib.util.spec_from_file_location("ldap_group_helper_vacio", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "LDAP_CONF_FILE", str(tmp_path / "no_existe.conf"))

    assert mod.check_group("jperez", "Ventas", "direct") is False


def test_falla_de_conexion_devuelve_false_sin_reventar(monkeypatch, modulo):
    def _connect_falla(config):
        raise RuntimeError("servidor inalcanzable")

    monkeypatch.setattr(modulo, "_connect", _connect_falla)
    assert modulo.check_group("jperez", "Ventas", "direct") is False


def test_handle_protocolo_de_squid(monkeypatch, modulo):
    """El protocolo real: 'login grupo modo' separado por espacios, valores
    %XX-decodificados (grupos con espacio en el nombre llegan escapados)."""
    def responder(base, filtro):
        if "Soporte" in filtro and "member=" not in filtro:
            return ["CN=Soporte Tecnico,CN=Users,DC=test,DC=com"]
        if "sAMAccountName=jperez" in filtro:
            return ["CN=Juan Perez,CN=Users,DC=test,DC=com"]
        if filtro.startswith("(member="):
            return ["CN=Soporte Tecnico,CN=Users,DC=test,DC=com"]
        return []

    _con_respuesta(monkeypatch, modulo, responder)
    assert modulo.handle("jperez Soporte%20Tecnico direct") == "OK"


def test_handle_linea_incompleta_devuelve_err(modulo):
    assert modulo.handle("solo_un_campo") == "ERR"


def test_handle_sin_modo_usa_direct_por_defecto(monkeypatch, modulo):
    llamadas = []

    def responder(base, filtro):
        llamadas.append(filtro)
        return []

    _con_respuesta(monkeypatch, modulo, responder)
    modulo.handle("jperez Ventas")
    assert not any("1.2.840.113556.1.4.1941" in f for f in llamadas)


def test_resolucion_del_grupo_se_cachea_por_proceso(monkeypatch, modulo):
    """Una vez resuelto el DN de un grupo, no hace falta volver a buscarlo
    -el nombre de un grupo no cambia mientras el helper sigue vivo."""
    busquedas_de_grupo = []

    def responder(base, filtro):
        if "Ventas" in filtro and "member=" not in filtro and "sAMAccountName=jperez" not in filtro:
            busquedas_de_grupo.append(filtro)
            return ["CN=Ventas,CN=Users,DC=test,DC=com"]
        if "sAMAccountName=jperez" in filtro:
            return ["CN=Juan Perez,CN=Users,DC=test,DC=com"]
        if filtro.startswith("(member="):
            return []
        return []

    _con_respuesta(monkeypatch, modulo, responder)
    modulo.check_group("jperez", "Ventas", "direct")
    modulo.check_group("jperez", "Ventas", "direct")
    assert len(busquedas_de_grupo) == 1
