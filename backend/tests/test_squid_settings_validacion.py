"""Bug real encontrado en la auditoría QA del 2026-09-20: `PUT
/squid/settings` aceptaba `http_port="abc"` y `cache_mem="abc"` sin ningún
error -se guardaban en la BD tal cual, y el problema recién se notaba al
aplicar cambios (fallo de `squid -k parse` sin apuntar a qué campo lo
causó). Se agregó validación de formato al guardar para estos dos campos.
"""

import pytest
from fastapi import HTTPException

import app.routes.squid_config as squid_config
from app.routes.squid_config import SettingUpdate, update_setting


class _FakeQuery:
    def __init__(self, existente=None):
        self._existente = existente

    def filter(self, *a, **k):
        return self

    def first(self):
        return self._existente


class _FakeDB:
    def __init__(self, existente=None):
        self._existente = existente
        self.agregados = []

    def query(self, *a, **k):
        return _FakeQuery(self._existente)

    def add(self, obj):
        self.agregados.append(obj)

    def flush(self):
        pass

    def commit(self):
        pass


class _FakeAdmin:
    id = 1
    username = "admin"


def _guardar(key, value):
    # update_setting() es sync (ver app/routes/squid_config.py): se llama
    # directo, sin asyncio.run().
    return update_setting(
        SettingUpdate(key=key, value=value),
        db=_FakeDB(),
        current_admin=_FakeAdmin(),
    )


@pytest.mark.parametrize("valor", ["abc", "", "-1", "0", "70000", "3128.5"])
def test_http_port_invalido_es_rechazado(valor):
    with pytest.raises(HTTPException) as exc:
        _guardar("http_port", valor)
    assert exc.value.status_code == 400


@pytest.mark.parametrize("valor", ["1", "3128", "65535"])
def test_http_port_valido_se_guarda(valor):
    resultado = _guardar("http_port", valor)
    assert resultado["value"] == valor


@pytest.mark.parametrize("valor", ["abc", "128 megas", "-128 MB"])
def test_cache_mem_invalido_es_rechazado(valor):
    with pytest.raises(HTTPException) as exc:
        _guardar("cache_mem", valor)
    assert exc.value.status_code == 400


@pytest.mark.parametrize("valor", ["128 MB", "4 MB", "0", "512KB", "1 GB"])
def test_cache_mem_valido_se_guarda(valor):
    resultado = _guardar("cache_mem", valor)
    assert resultado["value"] == valor


def test_maximum_object_size_invalido_es_rechazado():
    with pytest.raises(HTTPException):
        _guardar("maximum_object_size", "abc")
