"""Validación de la cuota de navegación — ver app/routes/quotas.py:_validar."""

import pytest
from fastapi import HTTPException

from app.routes.quotas import QuotaSet, _validar


def _cuota(**kwargs) -> QuotaSet:
    base = {"quota_bytes": 1_000_000, "quota_period": "daily", "quota_action": "cut",
            "quota_throttle_bytes_per_sec": None}
    base.update(kwargs)
    return QuotaSet(**base)


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
