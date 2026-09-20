"""Tests de las herramientas del asistente agéntico (ai_tools.py).

El punto central a probar: las herramientas de lectura devuelven datos
reales, y las de "proponer_*" NUNCA tocan la base -se interceptan antes de
llegar a ejecutar nada, ver ejecutar_herramienta()."""

import pytest

from app.models.acl import Acl
from app.models.access_rule import AccessRule
from app.models.squid_settings import SquidSetting
from app.models.user_group import UserGroup, UserGroupMember
from app.services import ai_tools


class _FakeQuery:
    def __init__(self, items):
        self._items = list(items)

    def options(self, *a, **k):
        return self

    def filter(self, *a, **k):
        return self

    def order_by(self, *a, **k):
        return self

    def all(self):
        return self._items


class FakeDB:
    def __init__(self, acls=None, rules=None, groups=None, members=None, settings=None):
        self._map = {
            Acl: acls or [], AccessRule: rules or [],
            UserGroup: groups or [], UserGroupMember: members or [],
            SquidSetting: settings or [],
        }

    def query(self, model):
        return _FakeQuery(self._map.get(model, []))


class FakeAcl:
    def __init__(self, name, type_="dstdomain", source="inline", is_category=False, enabled=True, line_count=None):
        self.name = name
        self.type = type_
        self.source = source
        self.is_category = is_category
        self.enabled = enabled
        self.line_count = line_count


class FakeRule:
    def __init__(self, order, action, acl_names, enabled=True, description=""):
        self.order = order
        self.action = action
        self.acl_names = acl_names
        self.enabled = enabled
        self.description = description


class FakeGroup:
    def __init__(self, id, name, source="local", no_bump=False):
        self.id = id
        self.name = name
        self.source = source
        self.no_bump = no_bump


class FakeMember:
    def __init__(self, group_id):
        self.group_id = group_id


class FakeSetting:
    def __init__(self, key, value, category="general"):
        self.key = key
        self.value = value
        self.category = category


def test_listar_acls_no_expone_el_contenido_de_archivo():
    db = FakeDB(acls=[
        FakeAcl("redes_sociales", "dstdomain"),
        FakeAcl("hagezi_amenazas", "dstdomain", source="file", line_count=187666),
    ])
    resultado = ai_tools.ejecutar_herramienta(db, None, "listar_acls", {})
    nombres = {a["nombre"]: a for a in resultado["acls"]}
    assert nombres["redes_sociales"]["cantidad_lineas"] is None
    assert nombres["hagezi_amenazas"]["cantidad_lineas"] == 187666


def test_listar_reglas_acceso_respeta_el_orden():
    db = FakeDB(rules=[FakeRule(1, "deny", "Nacional"), FakeRule(0, "allow", "Nacional uy_domains")])
    resultado = ai_tools.ejecutar_herramienta(db, None, "listar_reglas_acceso", {})
    assert [r["orden"] for r in resultado["reglas"]] == [1, 0]  # tal cual vinieron de la query


def test_listar_grupos_cuenta_miembros_sin_exponer_nombres():
    db = FakeDB(
        groups=[FakeGroup(1, "ventas"), FakeGroup(2, "ad_soporte", source="ldap")],
        members=[FakeMember(1), FakeMember(1), FakeMember(1)],
    )
    resultado = ai_tools.ejecutar_herramienta(db, None, "listar_grupos", {})
    por_nombre = {g["nombre"]: g for g in resultado["grupos"]}
    assert por_nombre["ventas"]["cantidad_miembros"] == 3
    assert por_nombre["ad_soporte"]["cantidad_miembros"] == 0
    assert set(por_nombre["ventas"].keys()) == {"nombre", "origen", "cantidad_miembros", "excluido_de_ssl_bump"}


def test_ver_ajustes_squid():
    db = FakeDB(settings=[FakeSetting("http_port", "3128")])
    resultado = ai_tools.ejecutar_herramienta(db, None, "ver_ajustes_squid", {})
    assert resultado["ajustes"] == [{"clave": "http_port", "valor": "3128", "categoria": "general"}]


def test_ver_estado_aplicacion(monkeypatch):
    monkeypatch.setattr(ai_tools, "is_dirty", lambda: True)
    resultado = ai_tools.ejecutar_herramienta(FakeDB(), None, "ver_estado_aplicacion", {})
    assert resultado["hay_cambios_sin_aplicar"] is True


def test_herramienta_desconocida_lanza_value_error():
    with pytest.raises(ValueError, match="Herramienta desconocida"):
        ai_tools.ejecutar_herramienta(FakeDB(), None, "borrar_todo", {})


def test_proponer_crear_acl_nunca_toca_la_base():
    """La parte que de verdad importa: esto NO debe llamar a db.query ni
    ejecutar nada -solo devolver la propuesta tal cual."""
    class _DBQueRompeSiSeUsa:
        def query(self, model):
            raise AssertionError("proponer_crear_acl no debería consultar la base")

    resultado = ai_tools.ejecutar_herramienta(
        _DBQueRompeSiSeUsa(), None, "proponer_crear_acl",
        {"name": "redes_sociales", "type": "dstdomain", "value": ".facebook.com"},
    )
    assert resultado == {
        "__propuesta__": True,
        "accion": "proponer_crear_acl",
        "argumentos": {"name": "redes_sociales", "type": "dstdomain", "value": ".facebook.com"},
    }


def test_todas_las_herramientas_declaradas_son_ejecutables_o_propuestas():
    """Ancla contra el error de sumar una herramienta al TOOL_DEFS y
    olvidarse de darle una rama en ejecutar_herramienta()."""
    db = FakeDB()
    for tool in ai_tools.TOOL_DEFS:
        nombre = tool["name"]
        argumentos = {k: "x" for k in tool["parameters"].get("required", [])}
        try:
            ai_tools.ejecutar_herramienta(db, None, nombre, argumentos)
        except ValueError:
            pytest.fail(f"'{nombre}' está en TOOL_DEFS pero ejecutar_herramienta() no lo reconoce")
        except Exception:
            pass  # cualquier otro error (ej. de red al buscar documentación) no es lo que este test cubre
