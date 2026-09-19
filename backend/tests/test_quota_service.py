"""Cuotas de navegación (por nombre de usuario, local o LDAP) — ver
app/services/quota_service.py."""

from datetime import datetime

from app.services import quota_service as qs


# --- siguiente_inicio_periodo: la parte más fácil de arruinar con fechas ----

def test_periodo_diario_suma_un_dia():
    inicio = datetime(2026, 3, 10, 8, 0, 0)
    assert qs.siguiente_inicio_periodo(inicio, "daily") == datetime(2026, 3, 11, 8, 0, 0)


def test_periodo_semanal_suma_siete_dias():
    inicio = datetime(2026, 3, 10, 8, 0, 0)
    assert qs.siguiente_inicio_periodo(inicio, "weekly") == datetime(2026, 3, 17, 8, 0, 0)


def test_periodo_mensual_mes_simple():
    inicio = datetime(2026, 3, 10, 8, 0, 0)
    assert qs.siguiente_inicio_periodo(inicio, "monthly") == datetime(2026, 4, 10, 8, 0, 0)


def test_periodo_mensual_diciembre_a_enero_cambia_de_anio():
    inicio = datetime(2026, 12, 15, 0, 0, 0)
    siguiente = qs.siguiente_inicio_periodo(inicio, "monthly")
    assert siguiente == datetime(2027, 1, 15, 0, 0, 0)


def test_periodo_mensual_31_de_enero_cae_en_28_de_febrero_no_bisiesto():
    inicio = datetime(2026, 1, 31, 12, 0, 0)  # 2026 no es bisiesto
    siguiente = qs.siguiente_inicio_periodo(inicio, "monthly")
    assert siguiente == datetime(2026, 2, 28, 12, 0, 0)


def test_periodo_mensual_31_de_enero_cae_en_29_de_febrero_bisiesto():
    inicio = datetime(2028, 1, 31, 12, 0, 0)  # 2028 sí es bisiesto
    siguiente = qs.siguiente_inicio_periodo(inicio, "monthly")
    assert siguiente == datetime(2028, 2, 29, 12, 0, 0)


def test_acl_name_cuota_usa_el_id_de_la_cuota_no_el_nombre_de_usuario():
    # Los nombres de usuario admiten '.', las ACLs de Squid no.
    quota = FakeQuota(id=42, username="juan.perez")
    assert qs._acl_name_cuota(quota) == "cuota_usuario_42"


# --- Fakes, mismo patrón minimalista que el resto de la suite --------------

class FakeQuota:
    def __init__(self, id=1, username="ana", quota_bytes=1_000_000, quota_period="daily",
                 quota_action="cut", quota_throttle_bytes_per_sec=None,
                 quota_bytes_used=0, quota_period_started_at=None, quota_action_applied=False):
        self.id = id
        self.username = username
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


class FakeLdapUser:
    def __init__(self, id=1, username="ana", enabled=True):
        self.id = id
        self.username = username
        self.enabled = enabled


class FakeAcl:
    def __init__(self, name, acl_type="proxy_auth", value=None):
        self.id = 1
        self.name = name
        self.type = acl_type
        self.value = value
        self.enabled = True


class FakeDelayPool:
    def __init__(self, id=1, quota_id=None):
        self.id = id
        self.quota_id = quota_id
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
    def __init__(self, proxy_users=None, ldap_users=None, acls=None, delay_pools=None):
        from app.models.proxy_user import ProxyUser
        from app.models.ldap_user import LdapUser
        from app.models.acl import Acl
        from app.models.delay_pool import DelayPool
        from app.models.audit_log import AuditLog

        self.proxy_users = proxy_users or []
        self.ldap_users = ldap_users or []
        self.acls = acls or []
        self.delay_pools = delay_pools or []
        self.audit_logs = []
        self.commits = 0
        self._model_map = {
            ProxyUser: "proxy_users", LdapUser: "ldap_users",
            Acl: "acls", DelayPool: "delay_pools", AuditLog: "audit_logs",
        }

    def query(self, model):
        return _FakeQuery(getattr(self, self._model_map.get(model, "audit_logs")))

    def add(self, obj):
        from app.models.acl import Acl
        from app.models.delay_pool import DelayPool

        if isinstance(obj, (FakeAcl, Acl)):
            self.acls.append(obj)
        elif isinstance(obj, (FakeDelayPool, DelayPool)):
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
    """Los pasos que de verdad tocan el sistema (passwd/digest, LDAP,
    reiniciar Squid, aplicar squid.conf) quedan como no-op: acá solo se
    prueba la lógica de cuándo se dispara cada cosa."""
    import app.services.squid_service as squid_service

    monkeypatch.setattr(squid_service, "write_passwd_file", lambda db: 0)
    monkeypatch.setattr(squid_service, "write_digest_file", lambda db, realm: 0)
    monkeypatch.setattr(squid_service, "realm_actual", lambda db: "SquidManager Proxy")
    monkeypatch.setattr(squid_service, "purge_credentials", lambda: (True, "ok"))
    monkeypatch.setattr(squid_service, "apply_squid_config", lambda db: {"status": "ok", "message": "ok"})
    monkeypatch.setattr(squid_service, "write_ldap_aux_files", lambda config, allowed: True)
    monkeypatch.setattr(squid_service, "reload_squid", lambda: (True, "ok"))


# --- _procesar_cuota: disparo de la acción, usuario local -------------------

def test_no_dispara_nada_si_no_llego_al_limite(monkeypatch):
    _sin_efectos_secundarios_reales(monkeypatch)
    quota = FakeQuota(quota_bytes=1_000_000, quota_bytes_used=500_000,
                       quota_period_started_at=datetime(2026, 1, 1))
    db = FakeDB(proxy_users=[FakeProxyUser(username=quota.username)])

    qs._procesar_cuota(db, quota, ahora=datetime(2026, 1, 1, 12, 0, 0))

    assert quota.quota_action_applied is False


def test_corta_la_navegacion_de_un_usuario_local_al_agotar_la_cuota(monkeypatch):
    _sin_efectos_secundarios_reales(monkeypatch)
    quota = FakeQuota(quota_bytes=1_000_000, quota_bytes_used=1_500_000,
                       quota_period_started_at=datetime(2026, 1, 1))
    user = FakeProxyUser(username=quota.username, enabled=True)
    db = FakeDB(proxy_users=[user])

    qs._procesar_cuota(db, quota, ahora=datetime(2026, 1, 1, 12, 0, 0))

    assert user.enabled is False
    assert quota.quota_action_applied is True


def test_corta_a_un_usuario_ldap_si_no_hay_local_con_ese_nombre(monkeypatch):
    _sin_efectos_secundarios_reales(monkeypatch)
    quota = FakeQuota(username="ana.ldap", quota_bytes=1_000_000, quota_bytes_used=2_000_000,
                       quota_period_started_at=datetime(2026, 1, 1))
    ldap_user = FakeLdapUser(username="ana.ldap", enabled=True)
    db = FakeDB(ldap_users=[ldap_user])

    qs._procesar_cuota(db, quota, ahora=datetime(2026, 1, 1, 12, 0, 0))

    assert ldap_user.enabled is False
    assert quota.quota_action_applied is True


def test_local_gana_si_existen_los_dos_con_el_mismo_nombre(monkeypatch):
    _sin_efectos_secundarios_reales(monkeypatch)
    quota = FakeQuota(username="mismo", quota_bytes=1_000_000, quota_bytes_used=2_000_000,
                       quota_period_started_at=datetime(2026, 1, 1))
    local = FakeProxyUser(username="mismo", enabled=True)
    ldap_user = FakeLdapUser(username="mismo", enabled=True)
    db = FakeDB(proxy_users=[local], ldap_users=[ldap_user])

    qs._procesar_cuota(db, quota, ahora=datetime(2026, 1, 1, 12, 0, 0))

    assert local.enabled is False
    assert ldap_user.enabled is True  # no se toca


def test_usuario_borrado_no_revienta_solo_no_hace_nada(monkeypatch):
    _sin_efectos_secundarios_reales(monkeypatch)
    quota = FakeQuota(username="fantasma", quota_bytes=1_000_000, quota_bytes_used=2_000_000,
                       quota_period_started_at=datetime(2026, 1, 1))
    db = FakeDB()  # ni local ni ldap

    qs._procesar_cuota(db, quota, ahora=datetime(2026, 1, 1, 12, 0, 0))

    # No lanza excepción; simplemente no aplica nada (queda para revisar
    # a mano, no hay a quién cortarle el acceso).


def test_no_reaplica_el_corte_si_ya_estaba_aplicado(monkeypatch):
    _sin_efectos_secundarios_reales(monkeypatch)
    quota = FakeQuota(quota_bytes=1_000_000, quota_bytes_used=2_000_000,
                       quota_period_started_at=datetime(2026, 1, 1), quota_action_applied=True)
    db = FakeDB(proxy_users=[FakeProxyUser(username=quota.username, enabled=False)])

    qs._procesar_cuota(db, quota, ahora=datetime(2026, 1, 1, 12, 0, 0))

    assert db.commits == 0


def test_limita_la_velocidad_en_vez_de_cortar(monkeypatch):
    _sin_efectos_secundarios_reales(monkeypatch)
    quota = FakeQuota(id=7, username="carla", quota_bytes=1_000_000, quota_action="throttle",
                       quota_throttle_bytes_per_sec=20_000, quota_bytes_used=1_200_000,
                       quota_period_started_at=datetime(2026, 1, 1))
    user = FakeProxyUser(username="carla")
    db = FakeDB(proxy_users=[user])

    qs._procesar_cuota(db, quota, ahora=datetime(2026, 1, 1, 12, 0, 0))

    assert user.enabled is True  # "throttle" no deshabilita
    assert quota.quota_action_applied is True
    assert len(db.delay_pools) == 1
    pool = db.delay_pools[0]
    assert pool.quota_id == 7
    assert pool.parameters == "20000/20000"
    assert len(db.acls) == 1
    assert db.acls[0].name == "cuota_usuario_7"
    assert db.acls[0].value == "carla"


# --- Reinicio de periodo ----------------------------------------------------

def test_reinicia_el_periodo_y_reactiva_al_usuario_cortado(monkeypatch):
    _sin_efectos_secundarios_reales(monkeypatch)
    quota = FakeQuota(quota_bytes=1_000_000, quota_bytes_used=2_000_000,
                       quota_period_started_at=datetime(2026, 1, 1), quota_action_applied=True)
    user = FakeProxyUser(username=quota.username, enabled=False)
    db = FakeDB(proxy_users=[user])

    qs._procesar_cuota(db, quota, ahora=datetime(2026, 1, 2, 1, 0, 0))

    assert user.enabled is True
    assert quota.quota_bytes_used == 0
    assert quota.quota_action_applied is False
    assert quota.quota_period_started_at == datetime(2026, 1, 2, 1, 0, 0)


def test_reinicio_de_periodo_borra_el_delay_pool_de_la_limitacion_anterior(monkeypatch):
    _sin_efectos_secundarios_reales(monkeypatch)
    quota = FakeQuota(id=9, quota_bytes=1_000_000, quota_action="throttle",
                       quota_throttle_bytes_per_sec=20_000, quota_bytes_used=2_000_000,
                       quota_period_started_at=datetime(2026, 1, 1), quota_action_applied=True)
    pool_viejo = FakeDelayPool(id=5, quota_id=9)
    db = FakeDB(proxy_users=[FakeProxyUser(username=quota.username)], delay_pools=[pool_viejo])

    qs._procesar_cuota(db, quota, ahora=datetime(2026, 1, 2, 1, 0, 0))

    assert db.delay_pools == []
    assert quota.quota_action_applied is False


def test_primer_uso_solo_marca_el_inicio_del_periodo_sin_disparar_nada(monkeypatch):
    _sin_efectos_secundarios_reales(monkeypatch)
    quota = FakeQuota(quota_bytes=1_000_000, quota_bytes_used=0, quota_period_started_at=None)
    db = FakeDB(proxy_users=[FakeProxyUser(username=quota.username)])

    qs._procesar_cuota(db, quota, ahora=datetime(2026, 1, 1, 12, 0, 0))

    assert quota.quota_period_started_at == datetime(2026, 1, 1, 12, 0, 0)
    assert quota.quota_action_applied is False


# --- revertir_accion desde afuera (ej. el admin quita la cuota a mano) -----

def test_revertir_accion_no_toca_nada_si_el_admin_ya_reactivo_al_usuario(monkeypatch):
    _sin_efectos_secundarios_reales(monkeypatch)
    quota = FakeQuota(quota_action="cut")
    db = FakeDB(proxy_users=[FakeProxyUser(username=quota.username, enabled=True)])

    qs.revertir_accion(db, quota)

    assert db.commits == 0


def test_revertir_accion_de_limitacion_borra_el_pool(monkeypatch):
    _sin_efectos_secundarios_reales(monkeypatch)
    quota = FakeQuota(id=3, quota_action="throttle")
    pool = FakeDelayPool(id=1, quota_id=3)
    db = FakeDB(proxy_users=[FakeProxyUser(username=quota.username)], delay_pools=[pool])

    qs.revertir_accion(db, quota)

    assert db.delay_pools == []


def test_revertir_accion_reactiva_a_un_usuario_ldap_cortado(monkeypatch):
    _sin_efectos_secundarios_reales(monkeypatch)
    quota = FakeQuota(username="pedro.ldap", quota_action="cut")
    ldap_user = FakeLdapUser(username="pedro.ldap", enabled=False)
    db = FakeDB(ldap_users=[ldap_user])

    qs.revertir_accion(db, quota)

    assert ldap_user.enabled is True


# --- Acumulación de consumo desde el access.log -----------------------------

def test_acumula_bytes_solo_de_usuarios_con_cuota_configurada(monkeypatch):
    con_cuota = FakeQuota(username="con_cuota", quota_bytes_used=100)
    db = FakeDB()
    # La query real filtra por username IN (...); acá se simula devolviendo
    # directo la cuota relevante, como en el resto de la suite.
    monkeypatch.setattr(qs, "parse_line", lambda linea: {
        "con_cuota": {"user": "con_cuota", "bytes": 500},
        "sin_cuota": {"user": "sin_cuota", "bytes": 999},
    }.get(linea))

    from app.models.navigation_quota import NavigationQuota
    db._model_map[NavigationQuota] = "quotas"
    db.quotas = [con_cuota]

    qs._acumular_consumo(db, ["con_cuota", "sin_cuota", "con_cuota"])

    assert con_cuota.quota_bytes_used == 100 + 500 + 500
