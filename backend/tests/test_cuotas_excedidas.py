"""cuotas_excedidas: cuotas (individuales y de grupo) al límite o por
encima -pestaña "Cuota excedida" de Actividad de red y su reporte en PDF.
Ver app/services/quota_service.py.
"""

from app.services.quota_service import cuotas_excedidas


class _FakeQuota:
    def __init__(self, nombre, quota_bytes, quota_bytes_used, quota_action="cut", quota_action_applied=False):
        self.username = nombre  # NavigationQuota
        self.group_name = nombre  # GroupQuota
        self.quota_bytes = quota_bytes
        self.quota_bytes_used = quota_bytes_used
        self.quota_period = "monthly"
        self.quota_action = quota_action
        self.quota_action_applied = quota_action_applied
        self.quota_exceeded_at = None
        self.quota_period_started_at = None


class _FakeQuery:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _FakeDB:
    def __init__(self, usuarios=None, grupos=None):
        self._usuarios = usuarios or []
        self._grupos = grupos or []

    def query(self, model):
        from app.models.navigation_quota import NavigationQuota
        from app.models.group_quota import GroupQuota

        if model is NavigationQuota:
            return _FakeQuery(self._usuarios)
        if model is GroupQuota:
            return _FakeQuery(self._grupos)
        return _FakeQuery([])


def test_no_incluye_cuotas_por_debajo_del_limite():
    db = _FakeDB(usuarios=[_FakeQuota("ana", 1_000_000, 500_000)])
    assert cuotas_excedidas(db) == []


def test_incluye_cuota_de_usuario_justo_en_el_limite():
    db = _FakeDB(usuarios=[_FakeQuota("ana", 1_000_000, 1_000_000)])
    resultado = cuotas_excedidas(db)
    assert len(resultado) == 1
    assert resultado[0]["tipo"] == "usuario"
    assert resultado[0]["nombre"] == "ana"


def test_incluye_cuota_de_grupo_por_encima_del_limite():
    db = _FakeDB(grupos=[_FakeQuota("ventas", 1_000_000, 2_000_000)])
    resultado = cuotas_excedidas(db)
    assert len(resultado) == 1
    assert resultado[0]["tipo"] == "grupo"
    assert resultado[0]["nombre"] == "ventas"


def test_ordena_por_consumo_relativo_descendente():
    db = _FakeDB(usuarios=[
        _FakeQuota("poco_pasado", 1_000_000, 1_000_001),
        _FakeQuota("muy_pasado", 1_000_000, 5_000_000),
    ])
    resultado = cuotas_excedidas(db)
    assert [r["nombre"] for r in resultado] == ["muy_pasado", "poco_pasado"]


def test_estado_cortada_vs_limitada_segun_quota_action():
    db = _FakeDB(usuarios=[
        _FakeQuota("cortada", 1_000_000, 1_000_000, quota_action="cut", quota_action_applied=True),
        _FakeQuota("limitada", 1_000_000, 1_000_000, quota_action="throttle", quota_action_applied=True),
    ])
    resultado = {r["nombre"]: r for r in cuotas_excedidas(db)}
    assert resultado["cortada"]["quota_action"] == "cut"
    assert resultado["limitada"]["quota_action"] == "throttle"
