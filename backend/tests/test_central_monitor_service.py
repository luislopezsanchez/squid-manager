"""Tests de central_monitor_service.py: login + dashboard de un nodo remoto,
con httpx simulado -no hay servidor real en los tests, solo se verifica que
cada combinación de respuesta (éxito, timeout, credenciales rechazadas,
respuesta rara) se traduce al resultado esperado sin lanzar nunca."""

import httpx
import pytest

import app.services.central_monitor_service as central_monitor_service
from app.services.central_monitor_service import (
    consultar_nodo, consultar_todos, sincronizar_configuracion, consultar_arbol,
    consultar_detalle_nodo,
)


class FakeNode:
    def __init__(self, id=1, name="Sucursal Norte", url="http://10.0.0.5:8000",
                 username="viewer", password="secreta", enabled=True):
        self.id = id
        self.name = name
        self.url = url
        self.username = username
        self.password = password
        self.enabled = enabled


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, json_error=False, text=""):
        self.status_code = status_code
        self._json_data = json_data
        self._json_error = json_error
        self.text = text

    def json(self):
        if self._json_error:
            raise ValueError("no es JSON")
        return self._json_data


def test_error_de_conexion_en_el_login(monkeypatch):
    def _falla(*a, **k):
        raise httpx.ConnectError("no se pudo conectar")

    monkeypatch.setattr(central_monitor_service.httpx, "post", _falla)
    resultado = consultar_nodo(FakeNode())
    assert resultado["status"] == "error"
    assert "no se pudo conectar" in resultado["message"].lower()


def test_login_rechazado_401(monkeypatch):
    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: FakeResponse(401))
    resultado = consultar_nodo(FakeNode())
    assert resultado["status"] == "error"
    assert "usuario o contraseña" in resultado["message"].lower()


def test_login_con_codigo_inesperado(monkeypatch):
    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: FakeResponse(500))
    resultado = consultar_nodo(FakeNode())
    assert resultado["status"] == "error"
    assert "500" in resultado["message"]


def test_login_devuelve_json_sin_access_token(monkeypatch):
    monkeypatch.setattr(
        central_monitor_service.httpx, "post",
        lambda *a, **k: FakeResponse(200, json_data={"algo": "raro"}),
    )
    resultado = consultar_nodo(FakeNode())
    assert resultado["status"] == "error"
    assert "SquidManager" in resultado["message"]


def test_login_ok_pero_falla_la_conexion_al_pedir_el_dashboard(monkeypatch):
    monkeypatch.setattr(
        central_monitor_service.httpx, "post",
        lambda *a, **k: FakeResponse(200, json_data={"access_token": "tok123"}),
    )

    def _falla(*a, **k):
        raise httpx.ReadTimeout("tardó demasiado")

    monkeypatch.setattr(central_monitor_service.httpx, "get", _falla)
    resultado = consultar_nodo(FakeNode())
    assert resultado["status"] == "error"
    assert "dashboard" in resultado["message"].lower()


def test_dashboard_responde_con_codigo_de_error(monkeypatch):
    monkeypatch.setattr(
        central_monitor_service.httpx, "post",
        lambda *a, **k: FakeResponse(200, json_data={"access_token": "tok123"}),
    )
    monkeypatch.setattr(central_monitor_service.httpx, "get", lambda *a, **k: FakeResponse(403))
    resultado = consultar_nodo(FakeNode())
    assert resultado["status"] == "error"
    assert "403" in resultado["message"]


def test_exito_de_punta_a_punta(monkeypatch):
    monkeypatch.setattr(
        central_monitor_service.httpx, "post",
        lambda *a, **k: FakeResponse(200, json_data={"access_token": "tok123"}),
    )
    monkeypatch.setattr(
        central_monitor_service.httpx, "get",
        lambda *a, **k: FakeResponse(200, json_data={"traffic": {"total_bytes_per_second": 1000}}),
    )
    resultado = consultar_nodo(FakeNode(name="Sucursal Sur"))
    assert resultado["status"] == "ok"
    assert resultado["name"] == "Sucursal Sur"
    assert resultado["data"]["traffic"]["total_bytes_per_second"] == 1000


def test_el_login_usa_la_url_sin_barra_final(monkeypatch):
    urls_llamadas = []

    def _post(url, **k):
        urls_llamadas.append(url)
        return FakeResponse(200, json_data={"access_token": "tok"})

    def _get(url, **k):
        urls_llamadas.append(url)
        return FakeResponse(200, json_data={})

    monkeypatch.setattr(central_monitor_service.httpx, "post", _post)
    monkeypatch.setattr(central_monitor_service.httpx, "get", _get)
    consultar_nodo(FakeNode(url="http://10.0.0.5:8000/"))
    assert urls_llamadas == [
        "http://10.0.0.5:8000/api/auth/login",
        "http://10.0.0.5:8000/api/metrics/dashboard",
    ]


def test_consultar_todos_omite_los_deshabilitados(monkeypatch):
    monkeypatch.setattr(
        central_monitor_service.httpx, "post",
        lambda *a, **k: FakeResponse(200, json_data={"access_token": "tok"}),
    )
    monkeypatch.setattr(central_monitor_service.httpx, "get", lambda *a, **k: FakeResponse(200, json_data={}))
    nodos = [FakeNode(id=1, enabled=True), FakeNode(id=2, enabled=False)]
    resultados = consultar_todos(nodos)
    assert [r["id"] for r in resultados] == [1]


def test_json_de_login_invalido_no_lanza(monkeypatch):
    monkeypatch.setattr(
        central_monitor_service.httpx, "post",
        lambda *a, **k: FakeResponse(200, json_data=None, json_error=True),
    )
    resultado = consultar_nodo(FakeNode())
    assert resultado["status"] == "error"


# --- sincronizar_configuracion: empujar el backup a un nodo remoto ---------

def _post_login_y_luego(respuesta_restore):
    """login siempre exitoso; la SEGUNDA llamada a httpx.post (el restore
    real) responde lo que se le pida -ambos pasos usan httpx.post, a
    diferencia de consultar_nodo() que usa httpx.get para el segundo."""
    llamadas = {"n": 0}

    def _post(url, **k):
        llamadas["n"] += 1
        if llamadas["n"] == 1:
            return FakeResponse(200, json_data={"access_token": "tok"})
        return respuesta_restore

    return _post


def test_sincronizar_exito(monkeypatch):
    monkeypatch.setattr(
        central_monitor_service.httpx, "post",
        _post_login_y_luego(FakeResponse(200, json_data={"users": 3, "acls": 10})),
    )
    resultado = sincronizar_configuracion(FakeNode(), {"metadata": {}})
    assert resultado["status"] == "ok"
    assert resultado["data"]["users"] == 3


def test_sincronizar_login_rechazado_no_llega_a_restaurar(monkeypatch):
    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: FakeResponse(401))
    resultado = sincronizar_configuracion(FakeNode(), {"metadata": {}})
    assert resultado["status"] == "error"
    assert "contraseña" in resultado["message"].lower()


def test_sincronizar_cuenta_sin_permisos_de_escritura(monkeypatch):
    monkeypatch.setattr(
        central_monitor_service.httpx, "post",
        _post_login_y_luego(FakeResponse(403)),
    )
    resultado = sincronizar_configuracion(FakeNode(), {"metadata": {}})
    assert resultado["status"] == "error"
    assert "permisos de escritura" in resultado["message"]


def test_sincronizar_error_generico_incluye_el_detalle(monkeypatch):
    monkeypatch.setattr(
        central_monitor_service.httpx, "post",
        _post_login_y_luego(FakeResponse(400, text="Archivo JSON inválido")),
    )
    resultado = sincronizar_configuracion(FakeNode(), {"metadata": {}})
    assert resultado["status"] == "error"
    assert "400" in resultado["message"]
    assert "Archivo JSON inválido" in resultado["message"]


def test_sincronizar_respuesta_no_json_no_lanza(monkeypatch):
    monkeypatch.setattr(
        central_monitor_service.httpx, "post",
        _post_login_y_luego(FakeResponse(200, json_data=None, json_error=True)),
    )
    resultado = sincronizar_configuracion(FakeNode(), {"metadata": {}})
    assert resultado["status"] == "error"


# --- consultar_arbol: jerarquía multi-nivel ---------------------------------

def test_arbol_pide_central_dashboard_no_metrics_dashboard(monkeypatch):
    urls_llamadas = []

    def _get(url, **k):
        urls_llamadas.append(url)
        return FakeResponse(200, json_data={"self": {"instance_id": "id-b", "data": {}}, "children": []})

    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: FakeResponse(200, json_data={"access_token": "tok"}))
    monkeypatch.setattr(central_monitor_service.httpx, "get", _get)
    consultar_arbol(FakeNode())
    assert urls_llamadas == ["http://10.0.0.5:8000/api/central/dashboard"]


def test_arbol_pasa_la_profundidad_decrementada_como_parametro(monkeypatch):
    params_recibidos = {}

    def _get(url, params=None, **k):
        params_recibidos.update(params or {})
        return FakeResponse(200, json_data={"self": {"instance_id": "id-b", "data": {}}, "children": []})

    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: FakeResponse(200, json_data={"access_token": "tok"}))
    monkeypatch.setattr(central_monitor_service.httpx, "get", _get)
    consultar_arbol(FakeNode(), profundidad_restante=2)
    assert params_recibidos == {"profundidad": 2}


def test_arbol_nunca_manda_profundidad_negativa(monkeypatch):
    """Aunque a consultar_arbol() se le pida con profundidad_restante
    negativa (no debería pasar con el tope del router, pero por las dudas),
    lo que viaja en la URL nunca es negativo -evita que un nodo remoto mal
    escrito interprete "profundidad: -1" como "sin límite"."""
    params_recibidos = {}

    def _get(url, params=None, **k):
        params_recibidos.update(params or {})
        return FakeResponse(200, json_data={"self": {"instance_id": "id-b", "data": {}}, "children": []})

    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: FakeResponse(200, json_data={"access_token": "tok"}))
    monkeypatch.setattr(central_monitor_service.httpx, "get", _get)
    consultar_arbol(FakeNode(), profundidad_restante=-3)
    assert params_recibidos == {"profundidad": 0}


def test_arbol_extrae_self_e_hijos_de_la_respuesta(monkeypatch):
    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: FakeResponse(200, json_data={"access_token": "tok"}))
    monkeypatch.setattr(
        central_monitor_service.httpx, "get",
        lambda *a, **k: FakeResponse(200, json_data={
            "self": {"instance_id": "id-b", "data": {"traffic": {"total_bytes_per_second": 42}}},
            "children": [{"id": 9, "name": "Nieto", "status": "ok", "data": {}, "children": []}],
        }),
    )
    resultado = consultar_arbol(FakeNode(name="Sucursal Sur"))
    assert resultado["status"] == "ok"
    assert resultado["instance_id"] == "id-b"
    assert resultado["data"]["traffic"]["total_bytes_per_second"] == 42
    assert len(resultado["children"]) == 1
    assert resultado["children"][0]["name"] == "Nieto"


def test_arbol_nodo_viejo_sin_endpoint_cae_a_dashboard_plano(monkeypatch):
    """Un SquidManager anterior a esta función no tiene /api/central/dashboard
    (404): cae a /api/metrics/dashboard y sigue mostrando ese nodo con su
    dashboard plano, sin jerarquía, en vez de romper toda la vista -bug real
    visto en pruebas en vivo contra un nodo viejo, 2026-09-25."""
    def _get(url, **k):
        if "central/dashboard" in url:
            return FakeResponse(404)
        return FakeResponse(200, json_data={"traffic": {"total_bytes_per_second": 500}})

    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: FakeResponse(200, json_data={"access_token": "tok"}))
    monkeypatch.setattr(central_monitor_service.httpx, "get", _get)
    resultado = consultar_arbol(FakeNode())
    assert resultado["status"] == "ok"
    assert resultado["children"] == []
    assert resultado["instance_id"] is None
    assert resultado["data"]["traffic"]["total_bytes_per_second"] == 500


def test_arbol_nodo_viejo_no_se_loguea_dos_veces(monkeypatch):
    """La caída a /api/metrics/dashboard reusa el login ya hecho para pedir
    /api/central/dashboard -antes se loguaba una segunda vez contra el mismo
    nodo en la misma consulta, redundante (encontrado en pruebas en vivo,
    2026-09-25)."""
    logins = {"n": 0}

    def _post(url, **k):
        logins["n"] += 1
        return FakeResponse(200, json_data={"access_token": "tok"})

    def _get(url, **k):
        if "central/dashboard" in url:
            return FakeResponse(404)
        return FakeResponse(200, json_data={})

    monkeypatch.setattr(central_monitor_service.httpx, "post", _post)
    monkeypatch.setattr(central_monitor_service.httpx, "get", _get)
    consultar_arbol(FakeNode())
    assert logins["n"] == 1


def test_arbol_nodo_viejo_realmente_caido_no_es_falso_ok(monkeypatch):
    """Si /api/metrics/dashboard TAMBIÉN falla (nodo viejo pero además
    caído), el resultado debe seguir siendo un error de verdad, no un "ok"
    fabricado solo porque hubo una caída de endpoint."""
    def _get(url, **k):
        return FakeResponse(404)  # también 404 en el plano, no solo en central

    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: FakeResponse(200, json_data={"access_token": "tok"}))
    monkeypatch.setattr(central_monitor_service.httpx, "get", _get)
    resultado = consultar_arbol(FakeNode())
    assert resultado["status"] == "error"
    assert resultado["children"] == []


def test_arbol_login_fallido_incluye_children_vacio(monkeypatch):
    """El resultado de un nodo caído tiene que tener siempre la misma forma
    (con 'children'), para que el frontend no tenga que distinguir casos al
    recorrer el árbol."""
    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: FakeResponse(401))
    resultado = consultar_arbol(FakeNode())
    assert resultado["status"] == "error"
    assert resultado["children"] == []


def test_arbol_error_al_pedir_el_dashboard_incluye_children_vacio(monkeypatch):
    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: FakeResponse(200, json_data={"access_token": "tok"}))
    monkeypatch.setattr(central_monitor_service.httpx, "get", lambda *a, **k: FakeResponse(500))
    resultado = consultar_arbol(FakeNode())
    assert resultado["status"] == "error"
    assert resultado["children"] == []


# --- consultar_detalle_nodo: datos del modal "Ver más" ----------------------

def test_detalle_nodo_pide_los_tres_endpoints_con_el_mismo_token(monkeypatch):
    urls_llamadas = []

    def _get(url, **k):
        urls_llamadas.append(url)
        return FakeResponse(200, json_data=[])

    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: FakeResponse(200, json_data={"access_token": "tok"}))
    monkeypatch.setattr(central_monitor_service.httpx, "get", _get)
    consultar_detalle_nodo(FakeNode())
    assert len(urls_llamadas) == 3
    assert all(u.startswith("http://10.0.0.5:8000/api/metrics/") for u in urls_llamadas)


def test_detalle_nodo_exito(monkeypatch):
    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: FakeResponse(200, json_data={"access_token": "tok"}))
    monkeypatch.setattr(
        central_monitor_service.httpx, "get",
        lambda url, **k: FakeResponse(200, json_data=[{"user": "llopez"}] if "top-users" in url else [{"domain": "github.com"}] if "top-domains" in url else [{"ip": "10.0.0.9"}]),
    )
    resultado = consultar_detalle_nodo(FakeNode())
    assert resultado["status"] == "ok"
    assert resultado["top_users"] == [{"user": "llopez"}]
    assert resultado["top_domains"] == [{"domain": "github.com"}]
    assert resultado["connections"] == [{"ip": "10.0.0.9"}]


def test_detalle_nodo_login_fallido_no_lanza(monkeypatch):
    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: FakeResponse(401))
    resultado = consultar_detalle_nodo(FakeNode())
    assert resultado["status"] == "error"
    assert resultado["top_users"] is None
    assert resultado["top_domains"] is None
    assert resultado["connections"] is None


def test_detalle_nodo_un_endpoint_caido_no_tumba_los_otros(monkeypatch):
    """Un nodo tan viejo que le falta uno de los tres endpoints (o que
    responde mal en ese instante) no debe perder los otros dos."""
    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: FakeResponse(200, json_data={"access_token": "tok"}))
    monkeypatch.setattr(
        central_monitor_service.httpx, "get",
        lambda url, **k: FakeResponse(404) if "top-domains" in url else FakeResponse(200, json_data=[{"ok": True}]),
    )
    resultado = consultar_detalle_nodo(FakeNode())
    assert resultado["status"] == "ok"
    assert resultado["top_domains"] is None
    assert resultado["top_users"] == [{"ok": True}]
    assert resultado["connections"] == [{"ok": True}]
