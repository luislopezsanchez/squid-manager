"""Mejoras de la auditoría (1.0.11): rutas de usuarios y ACLs, búsqueda de usuarios, estado de canales de notificación,
sincronización LDAP con ausentes y restauración heredada con archivos mal formados."""

import asyncio
import json
import time
from types import SimpleNamespace as N

import pytest
from fastapi import HTTPException

from app.models.access_rule import AccessRule  # noqa: F401  (registra el modelo)
from app.models.acl import Acl
from app.models.admin import Admin
from app.models.ldap_config import LdapConfig
from app.models.ldap_user import LdapUser
from app.models.proxy_user import ProxyUser
from app.models.user_group import UserGroupMember
from app.routes import acls as racls
from app.routes import backup as rbackup
from app.routes import ldap as rldap
from app.routes import proxy_users as rusers
from app.routes import usuarios_busqueda as rbusq
from app.services import notification_service as ns

ADMIN = N(id=1, username="admin")


class _Q:
    def __init__(self, db, modelo): self.db, self.modelo = db, modelo
    def filter(self, *_): return self
    def options(self, *_): return self
    def order_by(self, *_): return self
    def limit(self, *_): return self
    def first(self):
        v = self.db.primero.get(self.modelo)
        return v
    def all(self): return list(self.db.todos.get(self.modelo, []))
    def delete(self, *a, **k): return self.db.borrados.get(self.modelo, 0)


class _DB:
    def __init__(self, primero=None, todos=None, borrados=None):
        self.primero, self.todos, self.borrados = primero or {}, todos or {}, borrados or {}
        self.nuevos, self.eliminados, self.commits, self.flushes = [], [], 0, 0
    def query(self, *args): return _Q(self, args[0])
    def add(self, o): self.nuevos.append(o)
    def delete(self, o): self.eliminados.append(o)
    def flush(self):
        from datetime import datetime
        for i, o in enumerate(self.nuevos, 1):
            if getattr(o, "id", None) is None:
                try: o.id = i
                except Exception: pass
            # Los valores por defecto que la base de datos pondría al insertar (la ACL de respuesta los exige).
            for campo, valor in (("created_at", datetime.now()), ("updated_at", datetime.now())):
                if hasattr(o, campo) and getattr(o, campo) is None:
                    setattr(o, campo, valor)
            if hasattr(o, "source") and getattr(o, "source") is None:
                o.source = "inline"
        self.flushes += 1
    def commit(self): self.commits += 1
    def rollback(self): pass
    def refresh(self, o): pass


# ------------------------------------------------------------------------------------ usuarios del proxy
@pytest.fixture
def usuarios_parcheado(monkeypatch):
    llamadas = {"sync": 0, "revocar": 0}
    monkeypatch.setattr(rusers, "_sync_passwd", lambda db: llamadas.__setitem__("sync", llamadas["sync"] + 1))
    monkeypatch.setattr(rusers, "_revocar", lambda bt: llamadas.__setitem__("revocar", llamadas["revocar"] + 1))
    monkeypatch.setattr(rusers, "queue_notification", lambda *a, **k: None)
    monkeypatch.setattr(rusers, "realm_actual", lambda db: "Squid")
    monkeypatch.setattr(rusers, "_generate_htpasswd_hash", lambda u, p: f"{u}:hash")
    monkeypatch.setattr(rusers, "get_password_hash", lambda p: "bcrypt-" + p)
    monkeypatch.setattr(rusers, "mark_dirty", lambda: None)
    monkeypatch.setattr(rusers, "active_proxy_users", lambda db: [])
    return llamadas


def test_crear_usuario_guarda_audita_y_regenera_el_htpasswd(usuarios_parcheado):
    from app.schemas.proxy_user import ProxyUserCreate
    db = _DB()
    u = rusers.create_proxy_user(ProxyUserCreate(username="ana", password="ClaveSegura1"), db=db, current_admin=ADMIN)
    assert u.username == "ana" and u.password_hash == "bcrypt-ClaveSegura1" and u.htpasswd_hash == "ana:hash"
    assert any(o.__class__.__name__ == "AuditLog" for o in db.nuevos)
    assert usuarios_parcheado["sync"] == 1 and db.commits == 1


def test_crear_usuario_repetido_o_homonimo_de_admin_da_400(usuarios_parcheado):
    from app.schemas.proxy_user import ProxyUserCreate
    datos = ProxyUserCreate(username="ana", password="ClaveSegura1")
    with pytest.raises(HTTPException) as e:
        rusers.create_proxy_user(datos, db=_DB(primero={ProxyUser: N(id=3)}), current_admin=ADMIN)
    assert e.value.status_code == 400 and "ya existe" in e.value.detail.lower()
    with pytest.raises(HTTPException) as e:
        rusers.create_proxy_user(datos, db=_DB(primero={Admin: N(id=1)}), current_admin=ADMIN)
    assert e.value.status_code == 400 and "administrador" in e.value.detail


def test_editar_usuario_inexistente_404_y_deshabilitar_purga_credenciales(usuarios_parcheado):
    from app.schemas.proxy_user import ProxyUserUpdate
    with pytest.raises(HTTPException) as e:
        rusers.update_proxy_user(1, ProxyUserUpdate(enabled=False), db=_DB(), current_admin=ADMIN)
    assert e.value.status_code == 404
    usuario = N(id=5, username="ana", enabled=True, display_name=None, email=None, password_hash="x", htpasswd_hash="x",
                digest_ha1="x", digest_ha1_realm="Squid", expires_at=None)
    rusers.update_proxy_user(5, ProxyUserUpdate(enabled=False), db=_DB(primero={ProxyUser: usuario}), current_admin=ADMIN)
    assert usuario.enabled is False and usuarios_parcheado["revocar"] == 1


def test_cambiar_la_clave_recalcula_los_tres_hashes_y_purga(usuarios_parcheado):
    from app.schemas.proxy_user import ProxyUserUpdate
    usuario = N(id=5, username="ana", enabled=True, display_name=None, email=None, password_hash="viejo", htpasswd_hash="viejo",
                digest_ha1="viejo", digest_ha1_realm="Squid", expires_at=None)
    rusers.update_proxy_user(5, ProxyUserUpdate(password="OtraClave99"), db=_DB(primero={ProxyUser: usuario}), current_admin=ADMIN)
    assert usuario.password_hash == "bcrypt-OtraClave99" and usuario.htpasswd_hash == "ana:hash"
    assert usuario.digest_ha1 != "viejo" and usuarios_parcheado["revocar"] == 1


def test_borrar_usuario_lo_quita_de_sus_grupos_y_purga(usuarios_parcheado):
    usuario = N(id=5, username="ana")
    db = _DB(primero={ProxyUser: usuario}, borrados={UserGroupMember: 2})
    rusers.delete_proxy_user(5, db=db, current_admin=ADMIN)
    assert db.eliminados == [usuario] and usuarios_parcheado["revocar"] == 1 and usuarios_parcheado["sync"] == 1
    with pytest.raises(HTTPException) as e:
        rusers.delete_proxy_user(9, db=_DB(), current_admin=ADMIN)
    assert e.value.status_code == 404


def test_aplicar_importacion_crea_audita_y_avisa_el_progreso(usuarios_parcheado, monkeypatch):
    monkeypatch.setattr(rusers, "_hashes", lambda u, p, r: ("ph", f"{u}:lh", "ha1"))
    avisos = []
    monkeypatch.setattr("app.services.notification_service.notify_now", lambda *a: avisos.append(a))
    db = _DB()
    fila = lambda n, pw="": {"username": n, "password": pw, "display_name": None, "email": None, "enabled": None, "expires_at": None}
    progreso = []
    informe = rusers._aplicar_importacion(db, {"total_filas": 2}, [fila("a", "ClaveSegura1"), fila("b")], [], 1, "admin", "u.csv",
                                          progreso=lambda h, f="calculando": progreso.append((h, f)), background_tasks=None)
    assert informe["creados"] == 2
    generadas = {c["usuario"] for c in informe["credenciales"]}
    assert generadas == {"b"}  # solo se devuelve la contraseña que se generó; la que venía en el archivo no
    assert [o.username for o in db.nuevos if isinstance(o, ProxyUser)] == ["a", "b"]
    assert progreso[-1] == (2, "guardando") and db.commits == 1 and len(avisos) == 1


# ------------------------------------------------------------------------------------------------ ACLs
@pytest.fixture
def acls_parcheado(monkeypatch):
    monkeypatch.setattr(racls, "mark_dirty", lambda: None)
    monkeypatch.setattr(racls, "queue_notification", lambda *a, **k: None)


def test_crear_acl_valida_y_rechaza_repetidas(acls_parcheado):
    from app.schemas.acl import AclCreate
    ok = racls.create_acl(AclCreate(name="blog", type="dstdomain", value=".blog.com"), db=_DB(), current_admin=ADMIN)
    assert ok.name == "blog"
    with pytest.raises(HTTPException) as e:
        racls.create_acl(AclCreate(name="blog", type="dstdomain", value=".x.com"), db=_DB(primero={Acl: N(id=1)}), current_admin=ADMIN)
    assert e.value.status_code == 400
    for malo in ({"name": "mala acl", "type": "dstdomain", "value": ".x.com"},
                 {"name": "ok", "type": "dstdomain", "value": ".x.com\nhttp_access allow all"},
                 {"name": "ok", "type": "inventado", "value": ".x.com"}):
        with pytest.raises(HTTPException) as e:
            racls.create_acl(AclCreate(**malo), db=_DB(), current_admin=ADMIN)
        assert e.value.status_code == 400


def test_borrar_acl_en_uso_da_409_y_sin_uso_la_elimina(acls_parcheado, monkeypatch):
    acl = N(id=1, name="blog", source="inline", type="src")
    monkeypatch.setattr(racls, "ensure_not_referenced", lambda db, n, a="eliminar": (_ for _ in ()).throw(HTTPException(409, "en uso")))
    with pytest.raises(HTTPException) as e:
        racls.delete_acl(1, db=_DB(primero={Acl: acl}), current_admin=ADMIN)
    assert e.value.status_code == 409
    monkeypatch.setattr(racls, "ensure_not_referenced", lambda *a, **k: None)
    db = _DB(primero={Acl: acl})
    racls.delete_acl(1, db=db, current_admin=ADMIN)
    assert db.eliminados == [acl]
    with pytest.raises(HTTPException) as e:
        racls.delete_acl(2, db=_DB(), current_admin=ADMIN)
    assert e.value.status_code == 404


# -------------------------------------------------------------------------- búsqueda de usuarios (09-002)
class _QB:
    def __init__(self, nombres): self.n = nombres
    def filter(self, *_): return self
    def order_by(self, *_): return self
    def limit(self, k): self.n = self.n[:k]; return self
    def all(self): return [(x,) for x in self.n]
    def scalar(self): return len(self.n)


class _DBBusqueda:
    def __init__(self, locales, ldap): self.m = {ProxyUser: locales, LdapUser: ldap}
    def query(self, col):
        modelo = ProxyUser if getattr(col, "class_", None) is ProxyUser or "ProxyUser" in str(col) else LdapUser
        return _QB(self.m[modelo])


def test_buscar_usuarios_mezcla_sin_duplicar_y_marca_si_hay_mas():
    db = _DBBusqueda(["ana", "luis"], ["ana", "zoe"])
    out = rbusq.buscar_usuarios(q="", limit=50, db=db, _=None)
    assert [u["username"] for u in out["usuarios"]] == ["ana", "luis", "zoe"] and out["hay_mas"] is False
    out = rbusq.buscar_usuarios(q="", limit=2, db=db, _=None)
    assert len(out["usuarios"]) == 2 and out["hay_mas"] is True


def test_los_comodines_del_usuario_no_actuan_como_tales():
    assert rbusq._patron("a%b_c") == "%a\\%b\\_c%"


# ------------------------------------------------------------------ canales de notificación (10-005)
@pytest.fixture
def canales_limpios():
    ns._estado.clear()
    yield
    ns._estado.clear()


def test_tras_tres_fallos_el_canal_se_pausa_y_descarta(canales_limpios):
    intentos = []
    def roto():
        intentos.append(1)
        return False, "servidor caído"
    for _ in range(ns.FALLOS_PARA_PAUSAR):
        assert ns._por_canal("telegram", roto) is False
    assert ns.estado_canales()["telegram"]["estado"] == "pausado"
    assert ns._por_canal("telegram", roto) is False and len(intentos) == ns.FALLOS_PARA_PAUSAR  # no volvió a intentar
    e = ns.estado_canales()["telegram"]
    assert e["descartados"] == 1 and e["ultimo_error"] == "servidor caído" and e["pausado_segundos"] > 0


def test_un_exito_reactiva_el_canal_y_otros_canales_no_se_afectan(canales_limpios):
    for _ in range(ns.FALLOS_PARA_PAUSAR):
        ns._por_canal("xmpp", lambda: (False, "mal"))
    assert ns.estado_canales()["xmpp"]["estado"] == "pausado"
    assert ns.estado_canales()["email"]["estado"] == "sin_actividad"
    ns.reiniciar_canal("xmpp")
    assert ns._por_canal("xmpp", lambda: (True, "ok")) is True
    assert ns.estado_canales()["xmpp"]["estado"] == "ok"


def test_una_excepcion_del_canal_no_rompe_a_quien_notifica(canales_limpios):
    def explota():
        raise RuntimeError("boom")
    assert ns._por_canal("email", explota) is False
    assert "boom" in ns.estado_canales()["email"]["ultimo_error"]


def test_tope_de_envios_simultaneos(canales_limpios):
    import threading
    dentro, liberar = threading.Semaphore(0), threading.Event()
    def lento():
        dentro.release(); liberar.wait(5); return True, "ok"
    hilos = [threading.Thread(target=ns._por_canal, args=("email", lento)) for _ in range(ns.ENVIOS_SIMULTANEOS)]
    for h in hilos: h.start()
    for _ in range(ns.ENVIOS_SIMULTANEOS): assert dentro.acquire(timeout=3)
    assert ns._por_canal("email", lambda: (True, "ok")) is False  # sin hueco: se descarta en vez de acumularse
    assert ns.estado_canales()["email"]["descartados"] == 1
    liberar.set()
    for h in hilos: h.join(3)


def test_una_prueba_correcta_reactiva_y_una_fallida_deja_el_motivo(canales_limpios):
    for _ in range(ns.FALLOS_PARA_PAUSAR):
        ns._por_canal("telegram", lambda: (False, "mal"))
    ns._resultado_prueba("telegram", True, "ok")
    assert ns.estado_canales()["telegram"]["estado"] == "ok"
    ns._resultado_prueba("xmpp", False, "certificado no confiable")
    assert ns.estado_canales()["xmpp"]["ultimo_error"] == "certificado no confiable"


# ------------------------------------------------------------------------ LDAP: ausentes (07-N01)
def _fake_ldap(monkeypatch, entradas):
    import ldap3
    class Conn:
        def __init__(self, *a, **k): self.extend = N(standard=N(paged_search=lambda **kw: entradas))
        def unbind(self): pass
    monkeypatch.setattr(ldap3, "Server", lambda *a, **k: object())
    monkeypatch.setattr(ldap3, "Connection", Conn)


def _cfg():
    return N(enabled=True, server_url="ldap://x", bind_dn="cn=a", bind_password="p", search_base="dc=e", user_filter="(uid=%s)", sync_filter=None)


def _e(nombre): return {"type": "searchResEntry", "attributes": {"sAMAccountName": nombre, "cn": nombre}}


def test_sync_marca_ausentes_sin_borrarlos_ni_deshabilitarlos(monkeypatch):
    monkeypatch.setattr(rldap, "_sync_ldap_files", lambda db: None)
    ana = N(username="Ana", display_name="", email=None, enabled=True, en_directorio=True)
    baja = N(username="baja", display_name="", email=None, enabled=True, en_directorio=True)
    db = _DB(primero={LdapConfig: _cfg()}, todos={LdapUser: [ana, baja]})
    _fake_ldap(monkeypatch, [_e("ana")])  # el directorio dice «ana»; la base tenía «Ana»: es la misma cuenta
    out = rldap.sync_ldap_users(db=db, current_admin=ADMIN)
    assert out["synced"] == 1 and out["ausentes"] == 1 and db.nuevos == []
    assert ana.en_directorio is True and baja.en_directorio is False and baja.enabled is True


def test_sync_que_no_devuelve_a_nadie_no_marca_a_todos_como_ausentes(monkeypatch):
    monkeypatch.setattr(rldap, "_sync_ldap_files", lambda db: None)
    u = N(username="ana", display_name="", email=None, enabled=True, en_directorio=True)
    db = _DB(primero={LdapConfig: _cfg()}, todos={LdapUser: [u]})
    _fake_ldap(monkeypatch, [])
    out = rldap.sync_ldap_users(db=db, current_admin=ADMIN)
    assert out == {"status": "ok", "synced": 0, "ausentes": 0} and u.en_directorio is True


def test_deshabilitar_ausentes(monkeypatch):
    monkeypatch.setattr(rldap, "_sync_ldap_files", lambda db: None)
    purgas = []
    monkeypatch.setattr(rldap, "purge_credentials", lambda: purgas.append(1))
    a, b = N(username="a", enabled=True), N(username="b", enabled=True)
    db = _DB(todos={LdapUser: [a, b]})
    out = rldap.deshabilitar_ausentes(db=db, current_admin=ADMIN)
    assert out["deshabilitados"] == 2 and not a.enabled and not b.enabled and purgas == [1]


# ------------------------------------------------------------------- restauración heredada (02-N02)
class _Subida:
    def __init__(self, datos): self._d, self._p = datos, 0
    async def read(self, n=-1):
        t, self._p = self._d[self._p:self._p + n], self._p + n
        return t


@pytest.mark.parametrize("backup", [
    {"metadata": {"platform": "x"}, "acls": [{"type": "dstdomain", "value": ".a.com", "enabled": True}]},  # sin «name»
    {"metadata": {"platform": "x"}, "proxy_users": [{"enabled": True}]},                                    # sin «username»
    {"metadata": {"platform": "x"}, "access_rules": [{"action": "allow"}]},                                 # sin «acl_names»
    {"metadata": {"platform": "x"}, "user_groups": ["no-es-un-objeto"]},                                      # tipo equivocado
])
def test_un_backup_mal_formado_da_400_y_no_500(backup):
    db = _DB()
    with pytest.raises(HTTPException) as e:
        asyncio.run(rbackup.restore_backup(file=_Subida(json.dumps(backup).encode()), db=db, admin=ADMIN))
    assert e.value.status_code == 400 and "mal formado" in e.value.detail.lower()
