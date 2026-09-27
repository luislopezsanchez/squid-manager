"""Validación de la cuota de navegación por grupo — ver
app/routes/group_quotas.py:_validar/_grupo_local."""

import pytest
from fastapi import HTTPException

from app.routes.group_quotas import GroupQuotaSet, _grupo_local, _validar


def _cuota(**kwargs) -> GroupQuotaSet:
    base = {"quota_bytes": 1_000_000, "quota_period": "daily", "quota_action": "cut",
            "quota_throttle_bytes_per_sec": None}
    base.update(kwargs)
    return GroupQuotaSet(**base)


def test_periodo_invalido_rechazado():
    with pytest.raises(HTTPException) as exc:
        _validar(_cuota(quota_period="yearly"))
    assert exc.value.status_code == 400


def test_accion_invalida_rechazada():
    with pytest.raises(HTTPException) as exc:
        _validar(_cuota(quota_action="delete_everything"))
    assert exc.value.status_code == 400


def test_accion_por_defecto_es_cortar():
    _validar(_cuota())  # no debe lanzar: 'cut' no necesita velocidad


def test_limitar_velocidad_sin_velocidad_es_rechazado():
    with pytest.raises(HTTPException) as exc:
        _validar(_cuota(quota_action="throttle"))
    assert "velocidad" in exc.value.detail.lower()


def test_limitar_velocidad_con_velocidad_valida():
    _validar(_cuota(quota_action="throttle", quota_throttle_bytes_per_sec=51200))  # no debe lanzar


class _FakeGrupo:
    def __init__(self, name="ventas", source="local"):
        self.name = name
        self.source = source


class _FakeQuery:
    def __init__(self, item):
        self._item = item

    def filter(self, *a, **k):
        return self

    def first(self):
        return self._item


class _FakeDB:
    def __init__(self, grupo):
        self._grupo = grupo

    def query(self, model):
        return _FakeQuery(self._grupo)


def test_grupo_inexistente_es_rechazado():
    with pytest.raises(HTTPException) as exc:
        _grupo_local(_FakeDB(None), "ventas")
    assert exc.value.status_code == 404


def test_grupo_ldap_es_rechazado():
    with pytest.raises(HTTPException) as exc:
        _grupo_local(_FakeDB(_FakeGrupo(source="ldap")), "ventas")
    assert exc.value.status_code == 400
    assert "ldap" in exc.value.detail.lower()


def test_grupo_local_es_aceptado():
    grupo = _FakeGrupo(source="local")
    assert _grupo_local(_FakeDB(grupo), "ventas") is grupo
