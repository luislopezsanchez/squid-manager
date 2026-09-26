"""Tests de la validación de datos de app/routes/central.py."""

import pytest
from fastapi import HTTPException

import app.routes.central as central
from app.routes.central import (
    _validar_url, _to_response, test_node as _ruta_test_node, NodeTest,
    node_detalle_por_ruta as _ruta_detalle_por_ruta,
)
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


# --- GET /central/nodes/detalle-por-ruta: detalle a cualquier nivel --------
#
# Reemplaza a la vieja GET /nodes/{id}/detalle (un id suelto, que solo podía
# alcanzar un hijo DIRECTO): un nieto o bisnieto llega con un id que
# pertenece a la tabla de OTRO servidor, y pedirle el detalle a este backend
# con ese id daba 404 -bug real, visto en pruebas en vivo con una jerarquía
# de 4 niveles, 2026-09-26.

def test_ruta_vacia_rechazada():
    with pytest.raises(HTTPException) as exc:
        _ruta_detalle_por_ruta(ruta="", db=FakeDBConNodo(None), _=None)
    assert exc.value.status_code == 400


def test_ruta_no_numerica_rechazada():
    with pytest.raises(HTTPException) as exc:
        _ruta_detalle_por_ruta(ruta="7,abc", db=FakeDBConNodo(None), _=None)
    assert exc.value.status_code == 400


def test_ruta_con_demasiados_saltos_rechazada():
    ruta = ",".join(str(i) for i in range(central.PROFUNDIDAD_MAXIMA + 1))
    with pytest.raises(HTTPException) as exc:
        _ruta_detalle_por_ruta(ruta=ruta, db=FakeDBConNodo(None), _=None)
    assert exc.value.status_code == 400


def test_ruta_primer_id_no_encontrado_da_404():
    with pytest.raises(HTTPException) as exc:
        _ruta_detalle_por_ruta(ruta="7,1", db=FakeDBConNodo(None), _=None)
    assert exc.value.status_code == 404


def test_ruta_de_un_solo_id_resuelve_directo(monkeypatch):
    """Un hijo directo (ruta de un solo id) se resuelve con
    consultar_detalle_nodo, sin reenviar nada -mismo comportamiento que
    tenía la vieja ruta de un solo salto."""
    nodo = MonitoredNode(id=7, name="Norte", url="http://10.0.0.5:8000",
                          username="viewer", password="secreta", enabled=True)
    capturado = {}

    def _detalle_falso(n):
        capturado["node"] = n
        return {"status": "ok"}

    monkeypatch.setattr(central, "consultar_detalle_nodo", _detalle_falso)
    resultado = _ruta_detalle_por_ruta(ruta="7", db=FakeDBConNodo(nodo), _=None)
    assert resultado == {"status": "ok"}
    assert capturado["node"] is nodo


def test_ruta_de_varios_ids_reenvia_el_resto(monkeypatch):
    """Un nieto/bisnieto (ruta de más de un id) se resuelve con
    consultar_detalle_relay, pasándole el resto de la ruta sin el primer
    id (que este salto ya consumió)."""
    nodo = MonitoredNode(id=7, name="Norte", url="http://10.0.0.5:8000",
                          username="viewer", password="secreta", enabled=True)
    capturado = {}

    def _relay_falso(n, resto):
        capturado["node"] = n
        capturado["resto"] = resto
        return {"status": "ok"}

    monkeypatch.setattr(central, "consultar_detalle_relay", _relay_falso)
    resultado = _ruta_detalle_por_ruta(ruta="7,1,2", db=FakeDBConNodo(nodo), _=None)
    assert resultado == {"status": "ok"}
    assert capturado["node"] is nodo
    assert capturado["resto"] == [1, 2]
