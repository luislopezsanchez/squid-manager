"""Usuarios del proxy contra una base SQLite en memoria: alta, edición, baja, acciones en bloque, exportar e importar."""
import asyncio  # noqa: F401
import csv
import io
from datetime import timedelta
from types import SimpleNamespace as N

import pytest
from fastapi import BackgroundTasks, HTTPException, UploadFile

from app.config import settings
from app.models.admin import Admin
from app.models.audit_log import AuditLog
from app.models.ldap_user import LdapUser
from app.models.proxy_user import ProxyUser
from app.models.user_group import UserGroup, UserGroupMember
from app.routes import proxy_users as pu
from app.schemas.proxy_user import ProxyUserCreate, ProxyUserUpdate
from app.utils import utcnow
from tests.bd_sqlite import nueva_sesion

ADMIN = N(id=1, username="admin")
CLAVE = "Clave-Larga-123"


@pytest.fixture
def ctx(monkeypatch):
    db = nueva_sesion()
    ev = {"passwd": 0, "purgas": 0, "avisos": [], "marcas": 0}
    monkeypatch.setattr(settings, "BCRYPT_COST", 4)
    monkeypatch.setattr(pu, "write_passwd_file", lambda d: ev.__setitem__("passwd", ev["passwd"] + 1) or 0)
    monkeypatch.setattr(pu, "write_digest_file", lambda d, r: None)
    monkeypatch.setattr(pu, "realm_actual", lambda d: "SquidManager")
    # la purga real reinicia Squid y, con `background_tasks`, se difiere: aquí solo se cuenta cuántas veces se pide
    monkeypatch.setattr(pu, "_revocar", lambda bt: ev.__setitem__("purgas", ev["purgas"] + 1))
    monkeypatch.setattr(pu, "reload_squid", lambda: (True, "ok"))
    monkeypatch.setattr(pu, "mark_dirty", lambda: ev.__setitem__("marcas", ev["marcas"] + 1))
    monkeypatch.setattr(pu, "queue_notification", lambda bt, d, tipo, titulo, msg: ev["avisos"].append(msg))
    monkeypatch.setattr("app.services.notification_service.notify_now", lambda d, tipo, titulo, msg: ev["avisos"].append(msg))
    # `htpasswd` es un programa externo: aquí basta una línea con la forma correcta
    monkeypatch.setattr(pu, "_generate_htpasswd_hash", lambda u, p: f"{u}:$2y$04$fake")
    yield db, ev
    db.close()


def _crear(db, nombre="ana", **extra):
    return pu.create_proxy_user(ProxyUserCreate(username=nombre, password=CLAVE, **extra), db=db,
                                current_admin=ADMIN, background_tasks=BackgroundTasks())


# ---------------------------------------------------------------- alta

def test_crear_un_usuario_guarda_hashes_y_deja_rastro(ctx):
    db, ev = ctx
    u = _crear(db, "ana", display_name="  Ana  ", email="ana@empresa.com")
    fila = db.query(ProxyUser).one()
    assert fila.username == "ana" and fila.display_name == "Ana" and fila.email == "ana@empresa.com"
    assert fila.password_hash.startswith("$2") and CLAVE not in fila.password_hash
    assert fila.htpasswd_hash.startswith("ana:") and len(fila.digest_ha1) == 32 and fila.digest_ha1_realm == "SquidManager"
    assert u.active is True and ev["passwd"] == 1
    assert [a.action for a in db.query(AuditLog)] == ["create"]


@pytest.mark.parametrize("nombre", ["con espacio", "ñandú", "a:b", "x" * 65, "", "a/b", "a\nb"])
def test_nombres_de_usuario_invalidos(ctx, nombre):
    db, _ = ctx
    with pytest.raises(HTTPException) as e:
        pu.create_proxy_user(ProxyUserCreate.model_construct(username=nombre, password=CLAVE, display_name=None, email=None,
                                                             enabled=True, expires_at=None),
                             db=db, current_admin=ADMIN, background_tasks=None)
    assert e.value.status_code == 400
    assert db.query(ProxyUser).count() == 0


def test_no_se_repite_un_usuario_ni_se_usa_el_nombre_de_un_administrador(ctx):
    db, _ = ctx
    _crear(db, "ana")
    with pytest.raises(HTTPException) as e:
        _crear(db, "ana")
    assert e.value.status_code == 400 and "ya existe" in e.value.detail
    db.add(Admin(username="Jefe", password_hash="x", role="admin"))
    db.commit()
    with pytest.raises(HTTPException) as e:
        _crear(db, "jefe")
    assert "administrador" in e.value.detail


def test_correo_invalido(ctx):
    db, _ = ctx
    with pytest.raises(HTTPException) as e:
        _crear(db, "ana", email="no-es-un-correo")
    assert e.value.status_code == 400


@pytest.mark.parametrize("clave", ["corta", "x" * 101, "ñ" * 40])
def test_contrasenas_que_el_esquema_rechaza(clave):
    with pytest.raises(Exception):
        ProxyUserCreate(username="ana", password=clave)


# ---------------------------------------------------------------- edición, baja y alternar

def test_editar_cambia_la_clave_y_purga_la_cache(ctx):
    db, ev = ctx
    _crear(db, "ana")
    antes = db.query(ProxyUser).one().password_hash
    pu.update_proxy_user(1, ProxyUserUpdate(password="Otra-Clave-456", display_name=" "), db=db, current_admin=ADMIN, background_tasks=None)
    fila = db.query(ProxyUser).one()
    assert fila.password_hash != antes and fila.display_name is None and ev["purgas"] == 1


def test_editar_sin_cambiar_la_clave_no_purga(ctx):
    db, ev = ctx
    _crear(db, "ana")
    pu.update_proxy_user(1, ProxyUserUpdate(email="a@b.com"), db=db, current_admin=ADMIN, background_tasks=None)
    assert ev["purgas"] == 0


def test_deshabilitar_o_caducar_purga_y_deja_de_estar_activo(ctx):
    db, ev = ctx
    _crear(db, "ana")
    out = pu.update_proxy_user(1, ProxyUserUpdate(enabled=False), db=db, current_admin=ADMIN, background_tasks=None)
    assert out.active is False and ev["purgas"] == 1
    pu.update_proxy_user(1, ProxyUserUpdate(enabled=True), db=db, current_admin=ADMIN, background_tasks=None)
    out = pu.update_proxy_user(1, ProxyUserUpdate(expires_at=utcnow() - timedelta(days=1)), db=db, current_admin=ADMIN, background_tasks=None)
    assert out.active is False and ev["purgas"] == 2
    out = pu.update_proxy_user(1, ProxyUserUpdate(expires_at=None), db=db, current_admin=ADMIN, background_tasks=None)
    assert out.active is True and db.query(ProxyUser).one().expires_at is None


def test_inexistente_da_404(ctx):
    db, _ = ctx
    for f in (lambda: pu.update_proxy_user(9, ProxyUserUpdate(), db=db, current_admin=ADMIN, background_tasks=None),
              lambda: pu.delete_proxy_user(9, db=db, current_admin=ADMIN, background_tasks=None),
              lambda: pu.toggle_proxy_user(9, db=db, current_admin=ADMIN, background_tasks=None),
              lambda: pu.reset_password(9, BackgroundTasks(), db=db, current_admin=ADMIN)):
        with pytest.raises(HTTPException) as e:
            f()
        assert e.value.status_code == 404


def test_borrar_quita_al_usuario_de_sus_grupos(ctx):
    db, ev = ctx
    _crear(db, "ana"); _crear(db, "luis")
    db.add(UserGroup(name="ventas")); db.commit()
    db.add_all([UserGroupMember(group_id=1, username="ana"), UserGroupMember(group_id=1, username="luis")]); db.commit()
    pu.delete_proxy_user(1, db=db, current_admin=ADMIN, background_tasks=None)
    assert [m.username for m in db.query(UserGroupMember)] == ["luis"]
    assert db.query(ProxyUser).count() == 1 and ev["purgas"] == 1 and ev["marcas"] == 1


def test_alternar_habilitado(ctx):
    db, ev = ctx
    _crear(db, "ana")
    assert pu.toggle_proxy_user(1, db=db, current_admin=ADMIN, background_tasks=None).enabled is False
    assert ev["purgas"] == 1
    assert pu.toggle_proxy_user(1, db=db, current_admin=ADMIN, background_tasks=None).enabled is True
    assert ev["purgas"] == 1                          # habilitar no purga


def test_reset_de_contrasena_devuelve_una_nueva_y_valida(ctx):
    db, ev = ctx
    _crear(db, "ana")
    antes = db.query(ProxyUser).one().password_hash
    out = pu.reset_password(1, BackgroundTasks(), db=db, current_admin=ADMIN)
    assert len(out["new_password"]) == 16 and out["new_password"].isalnum()
    assert db.query(ProxyUser).one().password_hash != antes
    from app.services.auth_service import verify_password
    assert verify_password(out["new_password"], db.query(ProxyUser).one().password_hash)


def test_listar_pagina_y_marca_activos(ctx):
    db, _ = ctx
    for n in ("a1", "a2", "a3"):
        _crear(db, n)
    pu.toggle_proxy_user(2, db=db, current_admin=ADMIN, background_tasks=None)
    filas = pu.list_proxy_users(limit=2, offset=0, db=db, _=ADMIN)
    assert [f.username for f in filas] == ["a1", "a2"] and [f.active for f in filas] == [True, False]
    assert [f.username for f in pu.list_proxy_users(limit=2, offset=2, db=db, _=ADMIN)] == ["a3"]


def test_sincronizar_informa_cuantos_activos(ctx, monkeypatch):
    db, _ = ctx
    monkeypatch.setattr(pu, "write_passwd_file", lambda d: 7)
    out = pu.sync_passwd_endpoint(db=db, _=ADMIN)
    assert out["active_users"] == 7 and out["status"] == "ok"


# ---------------------------------------------------------------- acciones en bloque

def _bulk(db, accion, nombres):
    return pu.bulk_action(pu.BulkAction(action=accion, usernames=nombres), BackgroundTasks(), db=db, current_admin=ADMIN)


def test_bloque_deshabilitar_mezcla_locales_ldap_e_inexistentes(ctx, monkeypatch):
    db, ev = ctx
    monkeypatch.setattr("app.routes.ldap._sync_ldap_files", lambda d: None)
    _crear(db, "ana")
    db.add(LdapUser(username="carlos", enabled=True)); db.commit()
    out = _bulk(db, "disable", ["ana", "carlos", "fantasma", "ana", " "])
    assert out["ok"] == ["ana", "carlos"] and out["omitidos"] == [{"usuario": "fantasma", "motivo": "No existe."}]
    assert db.query(ProxyUser).one().enabled is False and db.query(LdapUser).one().enabled is False
    assert ev["purgas"] == 1 and ev["passwd"] == 2        # un solo volcado del htpasswd y una sola purga para todo el lote


def test_bloque_borrar_no_toca_a_los_ldap(ctx):
    db, ev = ctx
    _crear(db, "ana")
    db.add(LdapUser(username="carlos", enabled=True)); db.commit()
    out = _bulk(db, "delete", ["ana", "carlos"])
    assert out["ok"] == ["ana"] and out["omitidos"][0]["usuario"] == "carlos" and "LDAP" in out["omitidos"][0]["motivo"]
    assert db.query(ProxyUser).count() == 0 and db.query(LdapUser).count() == 1


def test_bloque_reset_entrega_credenciales_solo_de_locales(ctx):
    db, _ = ctx
    _crear(db, "ana"); _crear(db, "luis")
    db.add(LdapUser(username="carlos", enabled=True)); db.commit()
    out = _bulk(db, "reset_password", ["ana", "luis", "carlos", "nadie"])
    assert {c["usuario"] for c in out["credenciales"]} == {"ana", "luis"} and all(len(c["password"]) == 16 for c in out["credenciales"])
    assert {o["usuario"] for o in out["omitidos"]} == {"carlos", "nadie"}


def test_bloque_aviso_resumido_con_muchos_nombres(ctx):
    db, ev = ctx
    for i in range(12):
        _crear(db, f"u{i:02d}")
    ev["avisos"].clear()
    _bulk(db, "disable", [f"u{i:02d}" for i in range(12)])
    assert "12 usuarios" in ev["avisos"][-1] and "y 4 más" in ev["avisos"][-1]


def test_bloque_valida_la_accion_y_el_tamano():
    with pytest.raises(Exception):
        pu.BulkAction(action="formatear", usernames=["a"])
    with pytest.raises(Exception):
        pu.BulkAction(action="delete", usernames=[])
    with pytest.raises(Exception):
        pu.BulkAction(action="delete", usernames=["a"] * 2001)


# ---------------------------------------------------------------- exportar e importar

def _csv(filas, cabecera="usuario,contraseña,nombre,email,habilitado,caduca"):
    return (cabecera + "\n" + "\n".join(filas) + "\n").encode("utf-8")


def _importar(db, datos, nombre="u.csv", **kw):
    args = dict(modo="crear", simular=True, segundo_plano=False)
    args.update(kw)
    return pu.import_users(BackgroundTasks(), file=UploadFile(file=io.BytesIO(datos), filename=nombre), db=db,
                           current_admin=ADMIN, **args)


def test_exportar_no_incluye_contrasenas_e_incluye_locales_y_ldap(ctx):
    db, _ = ctx
    _crear(db, "ana", display_name="Ana", email="a@b.com")
    db.add(LdapUser(username="carlos", enabled=False)); db.commit()
    r = pu.export_users(format="csv", db=db, _=ADMIN)
    texto = r.body.decode("utf-8-sig")
    filas = list(csv.reader(io.StringIO(texto)))
    assert len(filas) == 3 and "$2" not in texto and CLAVE not in texto
    assert {f[0]: f[3] for f in filas[1:]} == {"ana": "local", "carlos": "ldap"}
    assert pu.export_users(format="xlsx", db=db, _=ADMIN).body[:2] == b"PK"


def test_plantilla_en_los_dos_formatos():
    assert b"usuario" in pu.import_template(format="csv", _=ADMIN).body
    assert pu.import_template(format="xlsx", _=ADMIN).body[:2] == b"PK"


def test_simular_no_escribe_nada(ctx):
    db, _ = ctx
    inf = _importar(db, _csv(["ana,,Ana,,si,", "luis,,,,si,", "malo nombre,,,,si,"]))
    assert inf["simulacion"] and inf["a_crear"] == 2 and len(inf["errores"]) == 1 and db.query(ProxyUser).count() == 0


def test_importar_crea_con_claves_generadas_y_dadas(ctx):
    db, ev = ctx
    inf = _importar(db, _csv(["ana,,Ana,,si,", "luis,Clave-Segura-2026,,,si,2030-12-31"]), simular=False)
    assert (inf["creados"], inf["actualizados"]) == (2, 0)
    assert [c["usuario"] for c in inf["credenciales"]] == ["ana"]           # solo se entrega la que se generó
    assert db.query(ProxyUser).count() == 2 and db.query(ProxyUser).filter_by(username="luis").one().expires_at.year == 2030
    assert any("importó usuarios" in a for a in ev["avisos"])


def test_importar_no_pisa_usuarios_existentes_salvo_que_se_pida(ctx):
    db, ev = ctx
    _crear(db, "ana")
    antes = db.query(ProxyUser).one().password_hash
    inf = _importar(db, _csv(["ana,Nueva-Clave-999,Otro,,no,"]), simular=False)
    assert inf["creados"] == 0 and len(inf["omitidos"]) == 1 and db.query(ProxyUser).one().password_hash == antes
    inf = _importar(db, _csv(["ana,Nueva-Clave-999,Otro,,no,"]), simular=False, modo="crear_o_actualizar")
    fila = db.query(ProxyUser).one()
    assert inf["actualizados"] == 1 and fila.display_name == "Otro" and fila.enabled is False and fila.password_hash != antes
    assert ev["purgas"] == 1


def test_importar_rechaza_nombres_de_ldap_y_de_administradores(ctx):
    db, _ = ctx
    db.add(LdapUser(username="Carlos", enabled=True)); db.add(Admin(username="jefe", password_hash="x", role="admin")); db.commit()
    inf = _importar(db, _csv(["carlos,,,,si,", "JEFE,,,,si,", "nuevo,,,,si,"]), simular=False)
    assert inf["creados"] == 1 and len(inf["errores"]) == 2


def test_importar_archivos_que_no_sirven(ctx):
    db, _ = ctx
    for datos, nombre in ((b"", "vacio.csv"), (b"\x00\x01\x02", "raro.xlsx"), (b"a,b\n1,2\n", "otro.csv")):
        with pytest.raises(HTTPException) as e:
            _importar(db, datos, nombre=nombre)
        assert e.value.status_code == 400


def test_importar_clave_de_mas_de_72_bytes_es_error_de_fila(ctx):
    db, _ = ctx
    inf = _importar(db, _csv([f"ana,{'ñ' * 40},,,si,", "luis,,,,si,"]), simular=False)
    assert inf["creados"] == 1 and len(inf["errores"]) == 1 and db.query(ProxyUser).one().username == "luis"


def test_importar_en_segundo_plano_responde_con_una_tarea(ctx, monkeypatch):
    db, _ = ctx
    capturado = {}
    from app.services import import_jobs
    monkeypatch.setattr(import_jobs, "iniciar", lambda total, fn: capturado.update(total=total) or "tarea-1")
    inf = _importar(db, _csv(["ana,,,,si,", "luis,,,,si,"]), simular=False, segundo_plano=True)
    assert inf["tarea"] == "tarea-1" and capturado["total"] == 2 and db.query(ProxyUser).count() == 0


def test_importar_en_segundo_plano_con_otra_en_curso_da_409(ctx, monkeypatch):
    db, _ = ctx
    from app.services import import_jobs
    monkeypatch.setattr(import_jobs, "iniciar", lambda total, fn: None)
    with pytest.raises(HTTPException) as e:
        _importar(db, _csv(["ana,,,,si,"]), simular=False, segundo_plano=True)
    assert e.value.status_code == 409


def test_estado_de_una_tarea_desconocida(ctx):
    with pytest.raises(HTTPException) as e:
        pu.import_estado("no-existe", _=ADMIN)
    assert e.value.status_code == 404


def test_hashes_en_paralelo_y_estimacion():
    progreso = []
    r = pu._hashes_en_paralelo([("a", "Clave-Larga-1"), ("b", "Clave-Larga-2")], "r", progreso.append)
    assert set(r) == {"a", "b"} and max(progreso) == 2
    assert r["a"][1].startswith("a:$2y$") and len(r["a"][2]) == 32
    assert pu._segundos_estimados(0) == 0 and pu._segundos_estimados(10) >= 1


def test_htpasswd_sin_el_programa_da_500_con_el_remedio(monkeypatch):
    import subprocess
    from app.services import runtime

    def falta(*a, **k):
        raise FileNotFoundError()
    monkeypatch.setattr(subprocess, "run", falta)
    monkeypatch.setattr(runtime, "get_runtime", lambda: N(name="native"))
    with pytest.raises(HTTPException) as e:
        pu._generate_htpasswd_hash("ana", CLAVE)
    assert e.value.status_code == 500 and "apache2-utils" in e.value.detail
    monkeypatch.setattr(runtime, "get_runtime", lambda: N(name="docker"))
    with pytest.raises(HTTPException) as e:
        pu._generate_htpasswd_hash("ana", CLAVE)
    assert "imagen" in e.value.detail


def test_htpasswd_que_falla_o_tarda(monkeypatch):
    import subprocess
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: N(returncode=1, stdout="", stderr="boom"))
    with pytest.raises(HTTPException) as e:
        pu._generate_htpasswd_hash("ana", CLAVE)
    assert e.value.status_code == 500 and "boom" in e.value.detail

    def lento(*a, **k):
        raise subprocess.TimeoutExpired("htpasswd", 15)
    monkeypatch.setattr(subprocess, "run", lento)
    with pytest.raises(HTTPException) as e:
        pu._generate_htpasswd_hash("ana", CLAVE)
    assert "tardó" in e.value.detail
