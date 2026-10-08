"""Rutas con poca cobertura (auditoría 04-003): sincronización y grupos de LDAP, exportación de logs y restauración heredada."""

import asyncio
import json
from types import SimpleNamespace as N

import pytest
from fastapi import HTTPException

from app.models.ldap_config import LdapConfig
from app.models.ldap_user import LdapUser
from app.routes import backup as rbackup
from app.routes import ldap as rldap
from app.routes import logs as rlogs


# ---------------------------------------------------------------- LDAP: sincronización y grupos
class _Q:
    def __init__(self, filas): self.filas = filas
    def filter(self, *_): return self
    def options(self, *_): return self
    def order_by(self, *_): return self
    def first(self): return self.filas[0] if self.filas else None
    def all(self): return list(self.filas)
    def delete(self, *a, **k): self.filas.clear(); return 0


class _DB:
    def __init__(self, config=None, usuarios=()):
        self.config, self.usuarios, self.nuevos, self.commits = config, list(usuarios), [], 0
    def query(self, modelo):
        if modelo is LdapConfig:
            return _Q([self.config] if self.config else [])
        if modelo is LdapUser:
            return _Q(self.usuarios)
        return _Q([])
    def add(self, o): self.nuevos.append(o)
    def commit(self): self.commits += 1
    def flush(self): pass
    def rollback(self): pass


def _config(**kw):
    base = dict(enabled=True, server_url="ldap://x", bind_dn="cn=a", bind_password="p", search_base="dc=e,dc=l",
                user_filter="(uid=%s)", sync_filter=None)
    base.update(kw)
    return N(**base)


def _entrada(**attrs):
    return {"type": "searchResEntry", "attributes": attrs}


def _fake_ldap(monkeypatch, entradas):
    class Conn:
        def __init__(self, *a, **k):
            self.extend = N(standard=N(paged_search=lambda **kw: entradas))
        def unbind(self): pass
    import ldap3
    monkeypatch.setattr(ldap3, "Server", lambda *a, **k: object())
    monkeypatch.setattr(ldap3, "Connection", Conn)


def test_sync_ldap_crea_actualiza_y_omite_cuentas_de_maquina(monkeypatch):
    monkeypatch.setattr(rldap, "_sync_ldap_files", lambda db: None)
    existente = N(username="ana", display_name="vieja", email=None, en_directorio=True)
    db = _DB(_config(), [existente])
    _fake_ldap(monkeypatch, [
        _entrada(sAMAccountName="ana", cn="Ana Nueva", mail="ana@e.l"),
        _entrada(sAMAccountName="luis", cn="Luis"),
        _entrada(sAMAccountName="PC01$", cn="maquina"),
        _entrada(sAMAccountName="krbtgt"),
        _entrada(uid=["maria"], cn=["María"]),
        {"type": "searchResRef"},
    ])
    out = rldap.sync_ldap_users(db=db, current_admin=N(id=1, username="admin"))
    assert out == {"status": "ok", "synced": 3, "ausentes": 0}
    assert existente.display_name == "Ana Nueva" and existente.email == "ana@e.l"
    assert sorted(u.username for u in db.nuevos) == ["luis", "maria"]
    assert all(u.enabled for u in db.nuevos) and db.commits == 1


def test_sync_ldap_no_inserta_dos_veces_el_mismo_nombre_del_directorio(monkeypatch):
    monkeypatch.setattr(rldap, "_sync_ldap_files", lambda db: None)
    db = _DB(_config())
    _fake_ldap(monkeypatch, [_entrada(sAMAccountName="ana"), _entrada(sAMAccountName="ana")])
    rldap.sync_ldap_users(db=db, current_admin=N(id=1, username="admin"))
    assert [u.username for u in db.nuevos] == ["ana"]


def test_sync_ldap_sin_configuracion_da_400():
    with pytest.raises(HTTPException) as e:
        rldap.sync_ldap_users(db=_DB(None), current_admin=N(id=1, username="a"))
    assert e.value.status_code == 400


def test_grupos_ldap_devuelve_todos_no_solo_los_primeros_1000(monkeypatch):
    _fake_ldap(monkeypatch, [_entrada(cn=f"g{i:05d}") for i in range(1500)])
    out = rldap.list_ldap_groups(db=_DB(_config()), _=None)
    assert len(out["groups"]) == 1500 and out["total"] == 1500 and out["truncado"] is False


def test_grupos_ldap_avisa_si_supera_el_tope(monkeypatch):
    monkeypatch.setattr(rldap, "MAX_GRUPOS_LDAP", 10)
    _fake_ldap(monkeypatch, [_entrada(cn=f"g{i:03d}") for i in range(25)])
    out = rldap.list_ldap_groups(db=_DB(_config()), _=None)
    assert len(out["groups"]) == 10 and out["total"] == 25 and out["truncado"] is True


# ---------------------------------------------------------------- exportación de logs
def _exportar(monkeypatch, **resultado):
    base = {"entries": [], "has_more": False, "truncated": False}
    base.update(resultado)
    monkeypatch.setattr(rlogs, "get_logs", lambda **k: base)
    resp = asyncio.run(rlogs.export_logs(format="ndjson", user=None, status=None, domain=None, ip=None, denied=False, _=None))
    return resp


def test_export_completa_no_se_marca_parcial(monkeypatch):
    r = _exportar(monkeypatch)
    assert "x-export-parcial" not in {k.lower() for k in r.headers} and "parcial" not in r.headers["content-disposition"]


@pytest.mark.parametrize("clave", ["has_more", "truncated"])
def test_export_parcial_se_nota_en_cabecera_y_en_el_nombre(monkeypatch, clave):
    r = _exportar(monkeypatch, **{clave: True})
    assert r.headers["x-export-parcial"] == "true"
    assert "-parcial." in r.headers["content-disposition"]
    assert "X-Export-Parcial" in r.headers["access-control-expose-headers"]


# ---------------------------------------------------------------- restauración heredada
class _Sub:
    """Cualquier consulta devuelve vacío: sirve para ejercitar la validación de la restauración."""
    def __init__(self): self.nuevos, self.commits = [], 0
    def query(self, *_): return _Q([])
    def add(self, o): self.nuevos.append(o)
    def flush(self): pass
    def commit(self): self.commits += 1
    def rollback(self): pass


class _Subida:
    def __init__(self, datos): self._d, self._pos = datos, 0
    async def read(self, n=-1):
        trozo, self._pos = self._d[self._pos:self._pos + n], self._pos + n
        return trozo


def _restaurar(backup, db=None):
    db = db or _Sub()
    archivo = _Subida(json.dumps(backup).encode())
    return db, asyncio.run(rbackup.restore_backup(file=archivo, db=db, admin=N(id=1, username="a")))


META = {"metadata": {"platform": "squidmanager"}}


def test_restore_rechaza_json_invalido_y_backup_ajeno():
    with pytest.raises(HTTPException) as e:
        asyncio.run(rbackup.restore_backup(file=_Subida(b"{no es json"), db=_Sub(), admin=N(id=1, username="a")))
    assert e.value.status_code == 400
    with pytest.raises(HTTPException) as e:
        _restaurar({"otra": "cosa"})
    assert e.value.status_code == 400


def test_restore_rechaza_un_ajuste_con_salto_de_linea():
    with pytest.raises(HTTPException) as e:
        _restaurar({**META, "squid_settings": [{"key": "cache_mem", "value": "256 MB\nhttp_access allow all"}]})
    assert e.value.status_code == 400


def test_restore_rechaza_nombre_de_acl_con_espacios_o_valor_con_salto():
    with pytest.raises(HTTPException):
        _restaurar({**META, "acls": [{"name": "mala acl", "type": "dstdomain", "value": ".x.com", "enabled": True}]})
    with pytest.raises(HTTPException):
        _restaurar({**META, "acls": [{"name": "ok", "type": "dstdomain", "value": ".x.com\nhttp_access allow all", "enabled": True}]})


def test_restore_rechaza_regla_con_accion_invalida():
    with pytest.raises(HTTPException) as e:
        _restaurar({**META, "access_rules": [{"action": "permitir", "acl_names": "all", "order": 1, "enabled": True}]})
    assert e.value.status_code == 400


def test_restore_valido_cuenta_lo_restaurado_y_crea_usuarios_deshabilitados_sin_clave(monkeypatch):
    monkeypatch.setattr(rbackup, "mark_dirty", lambda: None)
    db, out = _restaurar({**META,
        "squid_settings": [{"key": "cache_mem", "value": "256 MB"}],
        "acls": [{"name": "blog", "type": "dstdomain", "value": ".blog.com", "enabled": True}],
        "proxy_users": [{"username": "ana", "enabled": True}]})
    assert out["status"] == "ok"
    out = out["details"]
    assert out["settings"] == 1 and out["acls"] == 1 and out["users"] == 1
    usuarios = [o for o in db.nuevos if o.__class__.__name__ == "ProxyUser"]
    assert usuarios and usuarios[0].enabled is False and usuarios[0].password_hash == ""
    assert any("sin contraseña" in w for w in out["warnings"])
