"""sync_ronda: la sincronización diaria de categorías se aplica sola solo si
el panel estaba limpio (app/services/category_sync_service.py)."""
import types

from app.services import category_sync_service as svc
from app.services import config_state, squid_service


class _Q:
    def __init__(self, filas): self.filas = filas
    def filter(self, *a, **k): return self
    def all(self): return self.filas


class _DB:
    def __init__(self, filas): self.filas = filas
    def query(self, *_): return _Q(self.filas)


def _preparar(monkeypatch, dirty_antes, la_sync_marca_dirty):
    config_state.mark_clean()
    if dirty_antes:
        config_state.mark_dirty()
    llamadas = []

    def sync_falso(db, acl):
        if la_sync_marca_dirty:
            config_state.mark_dirty()
        return {"ok": True}

    def apply_falso(db):
        llamadas.append(1)
        config_state.mark_clean()
        return {"status": "ok"}

    monkeypatch.setattr(svc, "sync_one", sync_falso)
    monkeypatch.setattr(squid_service, "apply_squid_config", apply_falso)
    return llamadas


def test_panel_limpio_y_la_sync_cambia_algo_se_aplica_sola(monkeypatch):
    llamadas = _preparar(monkeypatch, dirty_antes=False, la_sync_marca_dirty=True)
    r = svc.sync_ronda(_DB([types.SimpleNamespace(name="c1")]))
    assert llamadas == [1] and r["aplicado"] == {"status": "ok"}
    assert not config_state.is_dirty()


def test_si_habia_cambios_pendientes_del_admin_no_se_aplican(monkeypatch):
    llamadas = _preparar(monkeypatch, dirty_antes=True, la_sync_marca_dirty=True)
    r = svc.sync_ronda(_DB([types.SimpleNamespace(name="c1")]))
    assert llamadas == [] and r["aplicado"] is None
    assert config_state.is_dirty()


def test_sin_cambios_no_se_aplica_nada(monkeypatch):
    llamadas = _preparar(monkeypatch, dirty_antes=False, la_sync_marca_dirty=False)
    svc.sync_ronda(_DB([types.SimpleNamespace(name="c1")]))
    assert llamadas == []
