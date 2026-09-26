"""Tests de CentralMonitorConfig y el gate _requerir_habilitado() de
app/routes/central.py: el lado SALIENTE (listar/crear/editar/borrar nodos
propios, probarlos, sincronizarlos) se niega mientras el interruptor esté
apagado -apagado por defecto, mismo criterio que LDAP/Kerberos/Syslog/IA.

A propósito, _requerir_habilitado() NO se llama desde central_dashboard():
el lado ENTRANTE (que otro SquidManager consulte a este como nodo) nunca
depende de este interruptor, ver test_central_routes_validacion.py."""

import uuid

import pytest
from fastapi import HTTPException

from app.models.central_config import CentralMonitorConfig
from app.models.squid_settings import SquidSetting
from app.routes.central import _requerir_habilitado, _squid_port


class _FakeQuery:
    def __init__(self, resultado):
        self._resultado = resultado

    def filter(self, *a, **k):
        return self

    def first(self):
        return self._resultado


class FakeDB:
    def __init__(self, config):
        self._config = config

    def query(self, model):
        assert model is CentralMonitorConfig
        return _FakeQuery(self._config)


class FakeDBConSetting:
    def __init__(self, valor):
        self._valor = valor

    def query(self, model):
        assert model is SquidSetting
        setting = SquidSetting(key="http_port", value=self._valor) if self._valor is not None else None
        return _FakeQuery(setting)


def test_requerir_habilitado_sin_fila_de_config_rechaza():
    """Instalación recién hecha, todavía sin ninguna fila en
    central_monitor_config (nadie llamó nunca a GET /config): debe tratarse
    igual que "deshabilitado", no lanzar un error distinto ni asumir que
    está habilitado por default."""
    with pytest.raises(HTTPException) as exc:
        _requerir_habilitado(FakeDB(None))
    assert exc.value.status_code == 403


def test_requerir_habilitado_deshabilitado_rechaza():
    config = CentralMonitorConfig(id=1, enabled=False, instance_id=str(uuid.uuid4()))
    with pytest.raises(HTTPException) as exc:
        _requerir_habilitado(FakeDB(config))
    assert exc.value.status_code == 403


def test_requerir_habilitado_habilitado_no_lanza():
    config = CentralMonitorConfig(id=1, enabled=True, instance_id=str(uuid.uuid4()))
    _requerir_habilitado(FakeDB(config))  # no debe lanzar nada


def test_instance_id_default_genera_un_uuid_valido():
    """El default de la columna (ver el modelo) es lo que usa
    _obtener_o_crear_config() la primera vez que se crea la fila -acá se
    verifica el default en sí, sin depender de una sesión de SQLAlchemy
    real (esta suite no se conecta a ninguna base, ver tests/conftest.py)."""
    columna = CentralMonitorConfig.__table__.c.instance_id
    valor = columna.default.arg(None)
    uuid.UUID(valor)  # no debe lanzar: tiene que parsear como UUID válido


def test_instance_id_default_no_es_constante():
    """Si alguien lo reescribiera como un valor fijo en vez de una lambda,
    todas las instalaciones nuevas terminarían compartiendo el mismo
    instance_id -exactamente lo que este campo existe para evitar."""
    columna = CentralMonitorConfig.__table__.c.instance_id
    assert columna.default.arg(None) != columna.default.arg(None)


def test_squid_port_lee_el_setting():
    assert _squid_port(FakeDBConSetting("3128")) == "3128"


def test_squid_port_sin_setting_devuelve_none():
    assert _squid_port(FakeDBConSetting(None)) is None
