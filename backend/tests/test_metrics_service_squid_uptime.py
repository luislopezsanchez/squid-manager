"""_get_squid_uptime(db): reintenta una vez antes de reportar a Squid como
caído -una sola falla de la consulta al Cache Manager (timeout puntual,
Squid recargando su config en ese instante) no alcanza para confiar en que
Squid está realmente caído. Si ambos intentos fallan, se registra el motivo
real en el log -antes se tragaba en silencio, sin dejar rastro para
diagnosticar por qué. Bug real reportado en vivo, 2026-09-26: un Squid
corriendo se veía "Squid caído" en el árbol de Monitoreo Centralizado.
"""

from app.services import metrics_service
from app.services.cache_manager_service import CacheManagerError


def test_exito_al_primer_intento_no_reintenta(monkeypatch):
    llamadas = []

    def _pedir_reporte(db, reporte):
        llamadas.append(reporte)
        return "UP Time:\t123.4 seconds"

    monkeypatch.setattr("app.services.cache_manager_service._pedir_reporte", _pedir_reporte)
    monkeypatch.setattr(metrics_service.time, "sleep", lambda s: (_ for _ in ()).throw(AssertionError("no debería dormir si el primer intento ya funcionó")))

    assert metrics_service._get_squid_uptime(db=None) == 123.4
    assert llamadas == ["info"]


def test_falla_una_vez_y_se_recupera_en_el_reintento(monkeypatch):
    llamadas = {"n": 0}

    def _pedir_reporte(db, reporte):
        llamadas["n"] += 1
        if llamadas["n"] == 1:
            raise CacheManagerError("timeout puntual")
        return "UP Time:\t500 seconds"

    monkeypatch.setattr("app.services.cache_manager_service._pedir_reporte", _pedir_reporte)
    monkeypatch.setattr(metrics_service.time, "sleep", lambda s: None)

    assert metrics_service._get_squid_uptime(db=None) == 500.0
    assert llamadas["n"] == 2


def test_falla_los_dos_intentos_devuelve_none_y_deja_rastro_en_el_log(monkeypatch, caplog):
    def _pedir_reporte(db, reporte):
        raise CacheManagerError("Squid no respondió")

    monkeypatch.setattr("app.services.cache_manager_service._pedir_reporte", _pedir_reporte)
    monkeypatch.setattr(metrics_service.time, "sleep", lambda s: None)

    with caplog.at_level("WARNING"):
        assert metrics_service._get_squid_uptime(db=None) is None

    assert any("Squid no respondió" in r.message for r in caplog.records)
