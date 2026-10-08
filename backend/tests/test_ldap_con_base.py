"""LDAP contra una base SQLite en memoria y un servidor ldap3 simulado: configuración, prueba, grupos, sincronización."""
from types import SimpleNamespace as N

import pytest
from fastapi import HTTPException

import ldap3

from app.models.audit_log import AuditLog
from app.models.ldap_config import LdapConfig
from app.models.ldap_user import LdapUser
from app.models.squid_settings import SquidSetting
from app.routes import ldap as L
from tests.bd_sqlite import nueva_sesion

ADMIN = N(id=1, username="admin")


class _Servidor:
    """Directorio simulado: el estado se fija desde cada prueba."""
    entradas_busqueda: list = []          # resultado de conn.search / conn.entries
    paginadas: list = []                  # resultado de paged_search
    falla_bind: bool = False
    falla_busqueda: bool = False
    bind_usuario_ok: bool = True
    ligados: list = []


class _Conn:
    def __init__(self, server, user=None, password=None, auto_bind=False, receive_timeout=None):
        if _Servidor.falla_bind and user != "cn=ana,dc=x":
            raise RuntimeError("bind fallido")
        if user == "cn=ana,dc=x" and not _Servidor.bind_usuario_ok:
            raise RuntimeError("invalidCredentials")
        self.bound = True
        self.entries = []
        self.user = user
        _Servidor.ligados.append(user)
        outer = self

        class _Std:
            def paged_search(self, **kw):
                if _Servidor.falla_busqueda:
                    raise RuntimeError("fallo de búsqueda")
                outer.ultima = kw
                return list(_Servidor.paginadas)
        self.extend = N(standard=_Std())

    def search(self, **kw):
        if _Servidor.falla_busqueda:
            raise RuntimeError("fallo de búsqueda")
        self.ultimo_filtro = kw["search_filter"]
        self.entries = list(_Servidor.entradas_busqueda)

    def unbind(self):
        pass


@pytest.fixture
def ctx(monkeypatch):
    db = nueva_sesion()
    ev = {"archivos": [], "recargas": 0, "purgas": 0}
    _Servidor.entradas_busqueda, _Servidor.paginadas = [], []
    _Servidor.falla_bind = _Servidor.falla_busqueda = False
    _Servidor.bind_usuario_ok = True
    _Servidor.ligados = []
    monkeypatch.setattr(ldap3, "Server", lambda url, connect_timeout=None: N(url=url))
    monkeypatch.setattr(ldap3, "Connection", _Conn)
    monkeypatch.setattr(L, "write_ldap_aux_files", lambda cfg, permitidos: ev["archivos"].append(list(permitidos)))
    monkeypatch.setattr(L, "reload_squid", lambda: ev.__setitem__("recargas", ev["recargas"] + 1) or (True, "ok"))
    monkeypatch.setattr(L, "purge_credentials", lambda: ev.__setitem__("purgas", ev["purgas"] + 1))
    yield db, ev
    db.close()


def _config(db, habilitado=True, **kw):
    c = LdapConfig(id=1, server_url="ldap://dc", bind_dn="cn=svc,dc=x", bind_password="secreta", search_base="cn=Users,dc=test,dc=com",
                   user_filter="(uid=%s)", sync_filter="(objectClass=user)", enabled=habilitado, **kw)
    db.add(c); db.commit()
    return c


def _entrada(usuario=None, uid=None, cn=None, mail=None, tipo="searchResEntry"):
    attrs = {}
    if usuario is not None: attrs["sAMAccountName"] = usuario
    if uid is not None: attrs["uid"] = [uid]
    if cn is not None: attrs["cn"] = [cn]
    if mail is not None: attrs["mail"] = mail
    return {"type": tipo, "attributes": attrs}


def _datos(**kw):
    base = dict(server_url="ldap://dc", bind_dn="cn=svc,dc=x", bind_password="secreta", search_base="dc=test,dc=com")
    base.update(kw)
    return L.LdapConfigUpdate(**base)


# ---------------------------------------------------------------- configuración

def test_config_sin_guardar_devuelve_valores_por_defecto(ctx):
    db, _ = ctx
    out = L.get_ldap_config(db=db, _=ADMIN)
    assert out["enabled"] is False and out["user_filter"] == "(uid=%s)" and out["server_url"] == ""


def test_config_nunca_devuelve_la_contrasena(ctx):
    db, _ = ctx
    _config(db)
    out = L.get_ldap_config(db=db, _=ADMIN)
    assert out["bind_password"] == "***" and "secreta" not in str(out)


def test_guardar_config_nueva_y_conservar_la_contrasena_si_llega_asteriscos(ctx):
    db, ev = ctx
    L.update_ldap_config(_datos(), db=db, current_admin=ADMIN)
    assert db.query(LdapConfig).one().bind_password == "secreta" and ev["recargas"] == 1 and ev["archivos"] == [[]]
    L.update_ldap_config(_datos(bind_password="***", search_base="dc=otro,dc=com"), db=db, current_admin=ADMIN)
    c = db.query(LdapConfig).one()
    assert c.bind_password == "secreta" and c.search_base == "dc=otro,dc=com"
    L.update_ldap_config(_datos(bind_password="nueva-clave"), db=db, current_admin=ADMIN)
    assert db.query(LdapConfig).one().bind_password == "nueva-clave"
    assert "secreta" not in " ".join(a.new_value for a in db.query(AuditLog)) and "(cambiada)" in db.query(AuditLog).all()[-1].new_value


def test_primera_config_con_asteriscos_no_guarda_asteriscos_como_clave(ctx):
    db, _ = ctx
    L.update_ldap_config(_datos(bind_password="***"), db=db, current_admin=ADMIN)
    assert db.query(LdapConfig).one().bind_password == ""


@pytest.mark.parametrize("campo", ["server_url", "bind_dn", "search_base", "user_filter", "bind_password"])
def test_config_rechaza_saltos_de_linea(ctx, campo):
    db, _ = ctx
    with pytest.raises(HTTPException) as e:
        L.update_ldap_config(_datos(**{campo: "a\nb"}), db=db, current_admin=ADMIN)
    assert e.value.status_code == 400 and db.query(LdapConfig).count() == 0


def test_no_se_habilita_ldap_con_digest(ctx):
    db, _ = ctx
    db.add(SquidSetting(key="proxy_auth_scheme", value="digest")); db.commit()
    with pytest.raises(HTTPException) as e:
        L.update_ldap_config(_datos(enabled=True), db=db, current_admin=ADMIN)
    assert "Digest" in e.value.detail
    L.update_ldap_config(_datos(enabled=False), db=db, current_admin=ADMIN)       # guardarla apagada sí se puede


def test_los_archivos_auxiliares_solo_llevan_a_los_habilitados(ctx):
    db, ev = ctx
    db.add_all([LdapUser(username="ana", enabled=True), LdapUser(username="luis", enabled=False)]); db.commit()
    L.update_ldap_config(_datos(), db=db, current_admin=ADMIN)
    assert ev["archivos"][-1] == ["ana"]


# ---------------------------------------------------------------- prueba de conexión

def _prueba(db, **kw):
    base = dict(server_url="ldap://dc", bind_dn="cn=svc,dc=x", bind_password="secreta", search_base="dc=x",
                user_filter="(uid=%s)", username="ana", password="clave")
    base.update(kw)
    return L.test_ldap_connection(L.LdapTestRequest(**base), db=db, _=ADMIN)


def test_prueba_completa_correcta(ctx):
    db, _ = ctx
    _Servidor.entradas_busqueda = [N(entry_dn="cn=ana,dc=x")]
    out = _prueba(db)
    assert out["success"] is True and [r["status"] for r in out["results"]] == ["ok", "ok", "ok"]
    assert "cn=ana,dc=x" in _Servidor.ligados


def test_prueba_escapa_el_nombre_en_el_filtro(ctx, monkeypatch):
    db, _ = ctx
    vistos = []
    original = _Conn.search
    monkeypatch.setattr(_Conn, "search", lambda self, **kw: vistos.append(kw["search_filter"]) or original(self, **kw))
    _Servidor.entradas_busqueda = [N(entry_dn="cn=ana,dc=x")]
    _prueba(db, username="*)(uid=*")
    assert vistos and "*)(" not in vistos[0] and "\\2a" in vistos[0]


def test_prueba_falla_en_cada_paso_con_un_mensaje_claro(ctx):
    db, _ = ctx
    _Servidor.falla_bind = True
    out = _prueba(db)
    assert out["success"] is False and out["results"][0]["step"] == "Conexión LDAP" and out["results"][0]["status"] == "error"
    _Servidor.falla_bind = False
    out = _prueba(db)                                                           # el usuario no existe
    assert out["success"] is False and out["results"][-1]["step"] == "Búsqueda de usuario"
    _Servidor.entradas_busqueda = [N(entry_dn="cn=ana,dc=x")]
    _Servidor.bind_usuario_ok = False
    out = _prueba(db)
    assert out["success"] is False and out["results"][-1]["step"] == "Autenticación"
    _Servidor.falla_busqueda = True
    out = _prueba(db)
    assert out["success"] is False and "búsqueda" in out["results"][-1]["detail"]


def test_prueba_con_asteriscos_usa_la_clave_guardada_solo_para_el_mismo_servidor(ctx):
    db, _ = ctx
    _config(db)
    _Servidor.entradas_busqueda = [N(entry_dn="cn=ana,dc=x")]
    assert _prueba(db, bind_password="***")["success"] is True
    with pytest.raises(HTTPException) as e:                                      # otro servidor: no se reutiliza la clave
        _prueba(db, bind_password="***", server_url="ldap://otro")
    assert e.value.status_code == 400


# ---------------------------------------------------------------- grupos

def test_grupos_requiere_ldap_habilitado(ctx):
    db, _ = ctx
    with pytest.raises(HTTPException):
        L.list_ldap_groups(db=db, _=ADMIN)
    _config(db, habilitado=False)
    with pytest.raises(HTTPException):
        L.list_ldap_groups(db=db, _=ADMIN)


def test_grupos_ordena_deduplica_y_busca_desde_la_raiz_del_dominio(ctx):
    db, _ = ctx
    _config(db)
    _Servidor.paginadas = [
        {"type": "searchResEntry", "attributes": {"cn": ["Ventas"]}},
        {"type": "searchResEntry", "attributes": {"cn": "Admins"}},
        {"type": "searchResEntry", "attributes": {"cn": ["Ventas"]}},
        {"type": "searchResRef", "attributes": {}},
        {"type": "searchResEntry", "attributes": {"cn": []}},
    ]
    out = L.list_ldap_groups(db=db, _=ADMIN)
    assert out == {"groups": ["Admins", "Ventas"], "total": 2, "truncado": False}


def test_grupos_trunca_cuando_hay_demasiados(ctx, monkeypatch):
    db, _ = ctx
    _config(db)
    monkeypatch.setattr(L, "MAX_GRUPOS_LDAP", 3)
    _Servidor.paginadas = [{"type": "searchResEntry", "attributes": {"cn": [f"g{i}"]}} for i in range(5)]
    out = L.list_ldap_groups(db=db, _=ADMIN)
    assert len(out["groups"]) == 3 and out["total"] == 5 and out["truncado"] is True


def test_grupos_errores_de_conexion_y_de_busqueda(ctx):
    db, _ = ctx
    _config(db)
    _Servidor.falla_bind = True
    with pytest.raises(HTTPException) as e:
        L.list_ldap_groups(db=db, _=ADMIN)
    assert "conectando" in e.value.detail
    _Servidor.falla_bind = False; _Servidor.falla_busqueda = True
    with pytest.raises(HTTPException) as e:
        L.list_ldap_groups(db=db, _=ADMIN)
    assert "buscando" in e.value.detail


def test_raiz_del_dominio():
    assert L._raiz_dominio("cn=Users,dc=test,dc=com") == "dc=test,dc=com"
    assert L._raiz_dominio("DC=a, DC=b") == "DC=a,DC=b"
    assert L._raiz_dominio("o=empresa") == "o=empresa"


# ---------------------------------------------------------------- sincronización

def test_sincronizar_requiere_ldap_habilitado_y_conexion(ctx):
    db, _ = ctx
    with pytest.raises(HTTPException):
        L.sync_ldap_users(db=db, current_admin=ADMIN)
    _config(db)
    _Servidor.falla_bind = True
    with pytest.raises(HTTPException) as e:
        L.sync_ldap_users(db=db, current_admin=ADMIN)
    assert "conectando" in e.value.detail
    _Servidor.falla_bind = False; _Servidor.falla_busqueda = True
    with pytest.raises(HTTPException) as e:
        L.sync_ldap_users(db=db, current_admin=ADMIN)
    assert "buscando" in e.value.detail


def test_sincronizar_crea_habilitados_y_omite_cuentas_de_sistema(ctx):
    db, ev = ctx
    _config(db)
    _Servidor.paginadas = [
        _entrada("ana", cn="Ana Pérez", mail="ana@x.com"), _entrada(uid="luis", cn="Luis"),
        _entrada("PC-01$"), _entrada("krbtgt"), _entrada("Guest"), _entrada("Invitado"),
        _entrada(None), _entrada("ref", tipo="searchResRef"),
    ]
    out = L.sync_ldap_users(db=db, current_admin=ADMIN)
    assert out == {"status": "ok", "synced": 2, "ausentes": 0}
    filas = {u.username: u for u in db.query(LdapUser)}
    assert set(filas) == {"ana", "luis"} and filas["ana"].enabled and filas["ana"].email == "ana@x.com" and filas["ana"].en_directorio
    assert ev["archivos"][-1] == ["ana", "luis"]


def test_sincronizar_sin_distinguir_mayusculas_ni_duplicar(ctx):
    db, _ = ctx
    _config(db)
    db.add(LdapUser(username="Ana", enabled=False, display_name="vieja")); db.commit()
    _Servidor.paginadas = [_entrada("ANA", cn="Ana Nueva"), _entrada("ana", cn="Ana Repetida"), _entrada("luis"), _entrada("LUIS")]
    out = L.sync_ldap_users(db=db, current_admin=ADMIN)
    assert db.query(LdapUser).count() == 2 and out["synced"] == 4
    ana = db.query(LdapUser).filter(LdapUser.username == "Ana").one()
    assert ana.enabled is False                            # no se habilita sola a quien el admin deshabilitó


def test_sincronizar_marca_ausentes_sin_borrarlos_y_los_recupera(ctx):
    db, _ = ctx
    _config(db)
    db.add_all([LdapUser(username="ana", enabled=True), LdapUser(username="baja", enabled=True)]); db.commit()
    _Servidor.paginadas = [_entrada("ana")]
    assert L.sync_ldap_users(db=db, current_admin=ADMIN)["ausentes"] == 1
    baja = db.query(LdapUser).filter_by(username="baja").one()
    assert baja.en_directorio is False and baja.enabled is True
    _Servidor.paginadas = [_entrada("ana"), _entrada("baja")]
    assert L.sync_ldap_users(db=db, current_admin=ADMIN)["ausentes"] == 0
    assert db.query(LdapUser).filter_by(username="baja").one().en_directorio is True


def test_un_directorio_vacio_no_marca_a_nadie_como_ausente(ctx):
    db, _ = ctx
    _config(db)
    db.add(LdapUser(username="ana", enabled=True)); db.commit()
    _Servidor.paginadas = []
    out = L.sync_ldap_users(db=db, current_admin=ADMIN)
    assert out["synced"] == 0 and out["ausentes"] == 0 and db.query(LdapUser).one().en_directorio is True


def test_deshabilitar_ausentes(ctx):
    db, ev = ctx
    db.add_all([LdapUser(username="a", enabled=True, en_directorio=False), LdapUser(username="b", enabled=True, en_directorio=True),
                LdapUser(username="c", enabled=False, en_directorio=False)]); db.commit()
    assert L.deshabilitar_ausentes(db=db, current_admin=ADMIN)["deshabilitados"] == 1
    assert {u.username: u.enabled for u in db.query(LdapUser)} == {"a": False, "b": True, "c": False}
    assert ev["purgas"] == 1 and any(a.action == "disable_missing" for a in db.query(AuditLog))
    assert L.deshabilitar_ausentes(db=db, current_admin=ADMIN)["deshabilitados"] == 0 and ev["purgas"] == 1


def test_listar_y_alternar_usuarios_ldap(ctx):
    db, ev = ctx
    db.add_all([LdapUser(username="b", enabled=True), LdapUser(username="a", enabled=False)]); db.commit()
    assert [u.username for u in L.list_ldap_users(limit=1, offset=1, db=db, _=ADMIN)] == ["b"]
    u = L.toggle_ldap_user(db.query(LdapUser).filter_by(username="b").one().id, db=db, current_admin=ADMIN)
    assert u.enabled is False and ev["purgas"] == 1                  # deshabilitar purga la caché de credenciales
    L.toggle_ldap_user(u.id, db=db, current_admin=ADMIN)
    assert ev["purgas"] == 1
    with pytest.raises(HTTPException) as e:
        L.toggle_ldap_user(999, db=db, current_admin=ADMIN)
    assert e.value.status_code == 404
