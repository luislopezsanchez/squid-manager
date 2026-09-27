"""Cuota de navegación compartida por un grupo entero (pool compartido)
-ver app/services/quota_service.py y app/models/group_quota.py.

Mismo patrón minimalista de fakes que test_quota_service.py; a diferencia
de ese archivo, acá se monkeypatchea _miembros_actuales/_grupos_con_cuota_de
directamente (en vez de simular el JOIN de SQLAlchemy que usan por
dentro), ya que son funciones propias separadas justo para eso.
"""

from datetime import datetime

from app.services import quota_service as qs


class FakeGroupQuota:
    def __init__(self, id=1, group_name="ventas", quota_bytes=1_000_000, quota_period="daily",
                 quota_action="cut", quota_throttle_bytes_per_sec=None,
                 quota_bytes_used=0, quota_period_started_at=None, quota_action_applied=False):
        self.id = id
        self.group_name = group_name
        self.quota_bytes = quota_bytes
        self.quota_period = quota_period
        self.quota_action = quota_action
        self.quota_throttle_bytes_per_sec = quota_throttle_bytes_per_sec
        self.quota_bytes_used = quota_bytes_used
        self.quota_period_started_at = quota_period_started_at
        self.quota_action_applied = quota_action_applied


class FakeProxyUser:
    def __init__(self, id=1, username="ana", enabled=True):
        self.id = id
        self.username = username
        self.enabled = enabled


class FakeDelayPool:
    def __init__(self, id=1, group_quota_id=None):
        self.id = id
        self.group_quota_id = group_quota_id
        self.acl_name = None
        self.pool_class = None
        self.parameters = None
        self.description = None
        self.enabled = True


class _FakeQuery:
    def __init__(self, items):
        self._items = list(items)

    def filter(self, *a, **k):
        return self

    def all(self):
        return self._items

    def first(self):
        return self._items[0] if self._items else None


class FakeDB:
    def __init__(self, proxy_users=None, delay_pools=None):
        from app.models.proxy_user import ProxyUser
        from app.models.delay_pool import DelayPool
        from app.models.audit_log import AuditLog

        self.proxy_users = proxy_users or []
        self.delay_pools = delay_pools or []
        self.audit_logs = []
        self.commits = 0
        self._model_map = {
            ProxyUser: "proxy_users", DelayPool: "delay_pools", AuditLog: "audit_logs",
        }

    def query(self, model):
        return _FakeQuery(getattr(self, self._model_map.get(model, "audit_logs")))

    def add(self, obj):
        from app.models.delay_pool import DelayPool

        if isinstance(obj, (FakeDelayPool, DelayPool)):
            self.delay_pools.append(obj)
        else:
            self.audit_logs.append(obj)

    def flush(self):
        pass

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass

    def delete(self, obj):
        if obj in self.delay_pools:
            self.delay_pools.remove(obj)


def _sin_efectos_secundarios_reales(monkeypatch):
    import app.services.squid_service as squid_service

    monkeypatch.setattr(squid_service, "write_passwd_file", lambda db: 0)
    monkeypatch.setattr(squid_service, "write_digest_file", lambda db, realm: 0)
    monkeypatch.setattr(squid_service, "realm_actual", lambda db: "SquidManager Proxy")
    monkeypatch.setattr(squid_service, "purge_credentials", lambda: (True, "ok"))
    monkeypatch.setattr(squid_service, "apply_squid_config", lambda db: {"status": "ok", "message": "ok"})


# --- _cortar_grupo / revertir_accion_grupo ----------------------------------

def test_cortar_grupo_deshabilita_a_todos_los_miembros(monkeypatch):
    _sin_efectos_secundarios_reales(monkeypatch)
    monkeypatch.setattr(qs, "_miembros_actuales", lambda db, name: ["ana", "luis"])
    ana, luis = FakeProxyUser(id=1, username="ana"), FakeProxyUser(id=2, username="luis")
    db = FakeDB(proxy_users=[ana, luis])
    quota = FakeGroupQuota(group_name="ventas")

    qs._cortar_grupo(db, quota)

    assert ana.enabled is False
    assert luis.enabled is False


def test_cortar_grupo_no_toca_a_quien_ya_estaba_deshabilitado(monkeypatch):
    """No debería generar una entrada de auditoría de más por alguien que
    un admin ya había deshabilitado a mano."""
    _sin_efectos_secundarios_reales(monkeypatch)
    monkeypatch.setattr(qs, "_miembros_actuales", lambda db, name: ["ana"])
    ana = FakeProxyUser(username="ana", enabled=False)
    db = FakeDB(proxy_users=[ana])

    qs._cortar_grupo(db, FakeGroupQuota(group_name="ventas"))

    assert len(db.audit_logs) == 0


def test_revertir_accion_grupo_reactiva_a_los_cortados(monkeypatch):
    _sin_efectos_secundarios_reales(monkeypatch)
    monkeypatch.setattr(qs, "_miembros_actuales", lambda db, name: ["ana", "luis"])
    ana, luis = FakeProxyUser(id=1, username="ana", enabled=False), FakeProxyUser(id=2, username="luis", enabled=False)
    db = FakeDB(proxy_users=[ana, luis])
    quota = FakeGroupQuota(id=9, group_name="ventas", quota_action="cut")

    qs.revertir_accion_grupo(db, quota)

    assert ana.enabled is True
    assert luis.enabled is True


def test_revertir_accion_grupo_borra_el_pool_de_throttle(monkeypatch):
    _sin_efectos_secundarios_reales(monkeypatch)
    monkeypatch.setattr(qs, "_miembros_actuales", lambda db, name: [])
    pool = FakeDelayPool(id=5, group_quota_id=9)
    db = FakeDB(delay_pools=[pool])
    quota = FakeGroupQuota(id=9, group_name="ventas", quota_action="throttle")

    qs.revertir_accion_grupo(db, quota)

    assert pool not in db.delay_pools


# --- _limitar_grupo: usa la ACL propia del grupo, no crea una nueva ---------

def test_limitar_grupo_apunta_el_pool_a_la_acl_propia_del_grupo(monkeypatch):
    _sin_efectos_secundarios_reales(monkeypatch)
    db = FakeDB()
    quota = FakeGroupQuota(id=3, group_name="ventas", quota_action="throttle",
                             quota_throttle_bytes_per_sec=10_000)

    qs._limitar_grupo(db, quota)

    assert len(db.delay_pools) == 1
    pool = db.delay_pools[0]
    assert pool.group_quota_id == 3
    assert pool.acl_name == "ventas"  # la ACL del grupo, no una sintética
    assert pool.parameters == "10000/10000"


# --- _procesar_cuota_grupo: mismo ciclo que _procesar_cuota -----------------

def test_procesar_cuota_grupo_no_dispara_nada_si_no_llego_al_limite(monkeypatch):
    _sin_efectos_secundarios_reales(monkeypatch)
    monkeypatch.setattr(qs, "_miembros_actuales", lambda db, name: ["ana"])
    quota = FakeGroupQuota(quota_bytes=1_000_000, quota_bytes_used=500_000,
                             quota_period_started_at=datetime(2026, 1, 1))
    db = FakeDB(proxy_users=[FakeProxyUser(username="ana")])

    qs._procesar_cuota_grupo(db, quota, ahora=datetime(2026, 1, 1, 12, 0, 0))

    assert quota.quota_action_applied is False


def test_procesar_cuota_grupo_corta_al_agotarse(monkeypatch):
    _sin_efectos_secundarios_reales(monkeypatch)
    monkeypatch.setattr(qs, "_miembros_actuales", lambda db, name: ["ana"])
    quota = FakeGroupQuota(quota_bytes=1_000_000, quota_bytes_used=2_000_000,
                             quota_period_started_at=datetime(2026, 1, 1))
    ana = FakeProxyUser(username="ana")
    db = FakeDB(proxy_users=[ana])

    qs._procesar_cuota_grupo(db, quota, ahora=datetime(2026, 1, 1, 12, 0, 0))

    assert ana.enabled is False
    assert quota.quota_action_applied is True


def test_procesar_cuota_grupo_reinicia_el_periodo_y_reactiva(monkeypatch):
    _sin_efectos_secundarios_reales(monkeypatch)
    monkeypatch.setattr(qs, "_miembros_actuales", lambda db, name: ["ana"])
    ana = FakeProxyUser(username="ana", enabled=False)
    db = FakeDB(proxy_users=[ana])
    quota = FakeGroupQuota(quota_bytes=1_000_000, quota_bytes_used=1_000_000,
                             quota_period_started_at=datetime(2026, 1, 1), quota_action_applied=True)

    qs._procesar_cuota_grupo(db, quota, ahora=datetime(2026, 1, 2, 0, 0, 1))

    assert ana.enabled is True
    assert quota.quota_bytes_used == 0
    assert quota.quota_action_applied is False


# --- _acumular_consumo: suma por grupo, vía _grupos_con_cuota_de ------------

def test_acumular_consumo_suma_al_pool_del_grupo(monkeypatch):
    from app.models.navigation_quota import NavigationQuota
    from app.models.group_quota import GroupQuota

    quota_ventas = FakeGroupQuota(group_name="ventas", quota_bytes_used=0)

    class _DB:
        def query(self, model):
            if model is GroupQuota:
                return _FakeQuery([quota_ventas])
            return _FakeQuery([])  # NavigationQuota u otra: sin cuotas individuales en este test

        def commit(self):
            pass

    monkeypatch.setattr(
        qs, "_grupos_con_cuota_de",
        lambda db, grupos, usernames: [("ana", "ventas"), ("luis", "ventas")],
    )
    monkeypatch.setattr(
        qs, "parse_line",
        lambda linea: {"user": linea.split()[0], "bytes": int(linea.split()[1])},
    )

    qs._acumular_consumo(_DB(), ["ana 1000", "luis 2000"])

    assert quota_ventas.quota_bytes_used == 3000
