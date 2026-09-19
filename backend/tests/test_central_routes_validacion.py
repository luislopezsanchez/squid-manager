"""Tests de la validación de datos de app/routes/central.py."""

import pytest
from fastapi import HTTPException

from app.routes.central import _validar_url, _to_response
from app.models.monitored_node import MonitoredNode


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
