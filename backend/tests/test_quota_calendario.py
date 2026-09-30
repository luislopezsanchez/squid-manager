"""Periodos de cuota alineados al calendario (quota_service.proximo_reinicio)."""
import os
import time
from datetime import datetime

import pytest

from app.services import quota_service as qs


@pytest.fixture(autouse=True)
def _zona_utc():
    anterior = os.environ.get("TZ")
    os.environ["TZ"] = "UTC"
    time.tzset()
    yield
    if anterior is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = anterior
    time.tzset()


def test_diaria_se_restablece_a_la_medianoche_no_24h_despues():
    # Creada a las 15:00: antes reiniciaba a las 15:00 del día siguiente.
    assert qs.proximo_reinicio(datetime(2026, 3, 10, 15, 0), "daily") == datetime(2026, 3, 11, 0, 0)


def test_diaria_creada_justo_despues_de_medianoche():
    assert qs.proximo_reinicio(datetime(2026, 3, 10, 0, 0, 1), "daily") == datetime(2026, 3, 11, 0, 0)


def test_semanal_se_restablece_el_lunes():
    # 2026-03-10 es martes -> lunes 16
    assert qs.proximo_reinicio(datetime(2026, 3, 10, 8, 0), "weekly") == datetime(2026, 3, 16, 0, 0)
    # un lunes cualquiera -> el lunes siguiente, no el mismo día
    assert qs.proximo_reinicio(datetime(2026, 3, 16, 9, 0), "weekly") == datetime(2026, 3, 23, 0, 0)


def test_mensual_se_restablece_el_dia_uno():
    assert qs.proximo_reinicio(datetime(2026, 1, 31, 23, 0), "monthly") == datetime(2026, 2, 1, 0, 0)
    assert qs.proximo_reinicio(datetime(2026, 12, 15, 8, 0), "monthly") == datetime(2027, 1, 1, 0, 0)
    assert qs.proximo_reinicio(datetime(2026, 2, 28, 8, 0), "monthly") == datetime(2026, 3, 1, 0, 0)


def test_respeta_la_zona_horaria_del_servidor():
    os.environ["TZ"] = "America/Montevideo"  # UTC-3 todo el año
    time.tzset()
    # 02:00 UTC del 11 = 23:00 del 10 en Montevideo -> medianoche local = 03:00 UTC del 11
    assert qs.proximo_reinicio(datetime(2026, 3, 11, 2, 0), "daily") == datetime(2026, 3, 11, 3, 0)


def test_anotar_reinicio_deja_el_campo_en_la_fila():
    class Fila:
        quota_period = "daily"
        quota_period_started_at = datetime(2026, 3, 10, 15, 0)
    f = Fila()
    qs.anotar_reinicio(f)
    assert f.quota_next_reset == datetime(2026, 3, 11, 0, 0)
    f.quota_period_started_at = None
    qs.anotar_reinicio(f)
    assert f.quota_next_reset is None
