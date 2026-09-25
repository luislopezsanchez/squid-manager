"""Tests de la validación de datos de app/routes/central.py."""

import pytest
from fastapi import HTTPException

import app.routes.central as central
from app.routes.central import _validar_url, _to_response, test_node as _ruta_test_node, NodeTest
from app.models.monitored_node import MonitoredNode
from app.models.central_config import CentralMonitorConfig


def test_url_valida_http():
    assert _validar_url("http://10.0.0.5:8000") == "http://10.0.0.5:8000"


def test_url_valida_https():
    assert _validar_url("https://sucursal.empresa.com") == "https://sucursal.empresa.com"


def test_url_le_quita_la_barra_final():
    assert _validar_url("http://10.0.0.5:8000/") == "http://10.0.0.5:8000"


def test_url_sin_esquema_rechazada():
    with pytest.raises(HTTPException) as exc:
        _validar_url("10.0.0.5:8000")
    assert exc.value.status_code == 400


def test_url_vacia_rechazada():
    with pytest.raises(HTTPException):
        _validar_url("")


def test_respuesta_enmascara_la_contrasena():
    nodo = MonitoredNode(id=1, name="Norte", url="http://10.0.0.5:8000",
                          username="viewer", password="secreta_de_verdad", enabled=True)
    resp = _to_response(nodo)
    assert resp["password"] == "***"
    assert "secreta_de_verdad" not in str(resp)


# --- POST /central/test: resolución de la contraseña enmascarada ----------
#
# Bug real encontrado en revisión de código: probar la conexión de un nodo
# YA GUARDADO sin reescribir la contraseña mandaba el placeholder "***"
# literal como si fuera la contraseña real, y la prueba fallaba siempre por
# "credenciales rechazadas" aunque las guardadas fueran correctas.

class _FakeQueryUnNodo:
    def __init__(self, nodo):
        self._nodo = nodo

    def filter(self, *a, **k):
        return self

    def first(self):
        return self._nodo


# _requerir_habilitado() -que test_node() llama antes de hacer nada más-
# consulta CentralMonitorConfig, no MonitoredNode: sin esto, estos tests
# fallarían con un 403 antes de llegar a lo que en realidad quieren probar
# (la resolución de la contraseña enmascarada). Habilitado a propósito, para
# que esa parte no interfiera con lo que cada test realmente verifica.
_CONFIG_HABILITADA = CentralMonitorConfig(id=1, enabled=True, instance_id="00000000-0000-0000-0000-000000000000")


class FakeDBConNodo:
    def __init__(self, nodo):
        self._nodo = nodo

    def query(self, model):
        if model is CentralMonitorConfig:
            return _FakeQueryUnNodo(_CONFIG_HABILITADA)
        return _FakeQueryUnNodo(self._nodo)


def test_probar_con_mascara_y_id_usa_la_contrasena_guardada(monkeypatch):
    nodo = MonitoredNode(id=7, name="Norte", url="http://10.0.0.5:8000",
                          username="viewer", password="la_de_verdad", enabled=True)
    capturado = {}

    def _consultar_falso(nodo_temporal):
        capturado["password"] = nodo_temporal.password
        return {"status": "ok"}

    monkeypatch.setattr(central, "consultar_nodo", _consultar_falso)
    data = NodeTest(url="http://10.0.0.5:8000", username="viewer", password="***", id=7)
    _ruta_test_node(data=data, db=FakeDBConNodo(nodo), _=None)
    assert capturado["password"] == "la_de_verdad"


def test_probar_con_mascara_sin_id_no_revienta(monkeypatch):
    """Un nodo nuevo (todavía sin guardar) no tiene id -no debería intentar
    resolver nada, solo mandar la máscara tal cual (y que el proveedor
    remoto la rechace, que es el comportamiento correcto ahí)."""
    capturado = {}

    def _consultar_falso(nodo_temporal):
        capturado["password"] = nodo_temporal.password
        return {"status": "error"}

    monkeypatch.setattr(central, "consultar_nodo", _consultar_falso)
    data = NodeTest(url="http://10.0.0.5:8000", username="viewer", password="***", id=None)
    _ruta_test_node(data=data, db=FakeDBConNodo(None), _=None)
    assert capturado["password"] == "***"


def test_probar_con_contrasena_nueva_no_toca_la_guardada(monkeypatch):
    nodo = MonitoredNode(id=7, name="Norte", url="http://10.0.0.5:8000",
                          username="viewer", password="la_vieja", enabled=True)
    capturado = {}

    def _consultar_falso(nodo_temporal):
        capturado["password"] = nodo_temporal.password
        return {"status": "ok"}

    monkeypatch.setattr(central, "consultar_nodo", _consultar_falso)
    data = NodeTest(url="http://10.0.0.5:8000", username="viewer", password="una_nueva", id=7)
    _ruta_test_node(data=data, db=FakeDBConNodo(nodo), _=None)
    assert capturado["password"] == "una_nueva"
