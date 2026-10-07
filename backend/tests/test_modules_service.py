"""Módulos opcionales del panel (app/services/modules_service.py)."""
from app.services import modules_service as ms


class _Res:
    def __init__(self, filas): self.filas = filas
    def fetchall(self): return self.filas


class _DB:
    def __init__(self, filas=None): self.filas = filas or []; self.ejecutados = []
    def execute(self, sql, params=None):
        self.ejecutados.append((str(sql), params))
        return _Res(self.filas)


def test_por_defecto_analisis_y_asistente_si_panel_central_y_autoservicio_no():
    est = ms.get_all(_DB())
    assert est == {"analisis": True, "panel_central": False, "autoservicio": False, "asistente": True}


def test_lo_guardado_pisa_el_valor_por_defecto():
    est = ms.get_all(_DB([("panel_central", True), ("analisis", False)]))
    assert est["panel_central"] is True and est["analisis"] is False and est["asistente"] is True


def test_is_enabled_de_un_modulo_desconocido_no_bloquea():
    assert ms.is_enabled(_DB(), "no_existe") is True


def test_set_enabled_rechaza_claves_desconocidas():
    import pytest
    with pytest.raises(KeyError):
        ms.set_enabled(_DB(), "no_existe", True)


def test_set_enabled_hace_upsert():
    db = _DB()
    ms.set_enabled(db, "panel_central", True)
    sql, params = db.ejecutados[-1]
    assert "ON CONFLICT (key)" in sql and params["k"] == "panel_central" and params["e"] is True
