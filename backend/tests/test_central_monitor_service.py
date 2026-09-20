"""Tests de central_monitor_service.py: login + dashboard de un nodo remoto,
con httpx simulado -no hay servidor real en los tests, solo se verifica que
cada combinación de respuesta (éxito, timeout, credenciales rechazadas,
respuesta rara) se traduce al resultado esperado sin lanzar nunca."""

import httpx
import pytest

import app.services.central_monitor_service as central_monitor_service
from app.services.central_monitor_service import consultar_nodo, consultar_todos, sincronizar_configuracion


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
