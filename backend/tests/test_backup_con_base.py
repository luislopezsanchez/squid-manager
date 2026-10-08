"""Backup y restauración contra una base SQLite en memoria (consultas, filtros y borrados reales, no mocks).

La suite no usa PostgreSQL; todas las tablas excepto `doc_chunks` (columna tsvector) se crean igual en SQLite, y con eso
se ejercitan de verdad el formato heredado (JSON), el v2 (.smbackup) y las validaciones de entrada del restore.
"""
import asyncio
import json
from io import BytesIO
from types import SimpleNamespace as N

import pytest
from fastapi import HTTPException, UploadFile
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import sessionmaker

import app.models as _modelos
import importlib
import pkgutil
for _m in pkgutil.iter_modules(_modelos.__path__):
    importlib.import_module(f"app.models.{_m.name}")

from app.database import Base
from app.models.access_rule import AccessRule
from app.models.acl import Acl
from app.models.delay_pool import DelayPool
from app.models.ldap_user import LdapUser
from app.models.proxy_user import ProxyUser
from app.models.squid_settings import SquidSetting
from app.models.user_group import UserGroup, UserGroupMember
from app.routes import backup as bk
from app.services import backup_v2_service as b2

ADMIN = N(id=1, username="admin")


def _db_vacia():
    motor = create_engine("sqlite://")
    for t in Base.metadata.sorted_tables:
        if t.name != "doc_chunks":
            t.create(motor)
    with motor.begin() as c:                              # la crea una migración, no un modelo
        c.execute(text("CREATE TABLE app_modules (key TEXT PRIMARY KEY, enabled BOOLEAN, updated_at TIMESTAMP)"))
    return sessionmaker(bind=motor, expire_on_commit=False)()


@pytest.fixture
def db(monkeypatch):
    sesion = _db_vacia()
    monkeypatch.setattr(bk, "mark_dirty", lambda: None)
    yield sesion
    sesion.close()


def _contar(db, modelo):
    return db.scalar(select(func.count()).select_from(modelo))


def _backup(**extra):
    base = {
        "metadata": {"platform": "SquidManager", "version": 1, "exported_at": "2026-01-01T00:00:00", "exported_by": "x"},
        "squid_settings": [{"key": "cache_mem", "value": "256 MB"}],
        "acls": [
            {"name": "redes", "type": "src", "value": "10.0.0.0/8", "source": "inline", "enabled": True},
            {"name": "grande", "type": "dstdomain", "value": None, "source": "file", "line_count": 5000, "enabled": True},
        ],
        "user_groups": [{"name": "ventas", "members": ["ana", "luis"]}],
        "access_rules": [{"action": "allow", "acl_names": "redes", "order": 1, "enabled": True}],
        "proxy_users": [{"username": "ana", "enabled": True}],
        "ldap_users": [{"username": "carlos", "enabled": True}],
    }
    base.update(extra)
    return base


def _restaurar(db, backup):
    return bk._aplicar_backup_heredado(db, backup, ADMIN)


def _subir(datos: bytes, nombre="b.json"):
    return UploadFile(file=BytesIO(datos), filename=nombre)


def _ruta(db, datos: bytes):
    return asyncio.run(bk.restore_backup(file=_subir(datos), db=db, admin=ADMIN))


# ---------------------------------------------------------------- formato heredado: lo que se crea

def test_restaura_todo_y_avisa_de_lo_que_no_viaja(db):
    out = _restaurar(db, _backup())
    d = out["details"]
    assert (d["settings"], d["acls"], d["rules"], d["groups"], d["users"], d["ldap_users"]) == (1, 2, 1, 1, 1, 1)
    assert db.query(SquidSetting).one().value == "256 MB"
    grande = db.query(Acl).filter_by(name="grande").one()
    assert grande.source == "file" and grande.value is None and grande.line_count == 5000
    assert {m.username for m in db.query(UserGroupMember)} == {"ana", "luis"}
    ana = db.query(ProxyUser).one()
    assert ana.enabled is False and ana.password_hash == ""           # sin contraseña: no puede entrar nadie con ella
    avisos = " ".join(d["warnings"])
    assert "grande" in avisos and "sin contraseña" in avisos and "Aplicar cambios" in avisos


def test_restaurar_dos_veces_no_duplica(db):
    _restaurar(db, _backup())
    _restaurar(db, _backup())
    assert (_contar(db, Acl), _contar(db, UserGroup), _contar(db, UserGroupMember), _contar(db, AccessRule),
            _contar(db, ProxyUser), _contar(db, SquidSetting)) == (2, 1, 2, 1, 1, 1)


def test_restaurar_actualiza_lo_existente(db):
    _restaurar(db, _backup())
    nuevo = _backup(acls=[{"name": "redes", "type": "src", "value": "192.168.0.0/16", "source": "inline", "enabled": False}],
                    squid_settings=[{"key": "cache_mem", "value": "512 MB"}])
    _restaurar(db, nuevo)
    redes = db.query(Acl).filter_by(name="redes").one()
    assert redes.value == "192.168.0.0/16" and redes.enabled is False
    assert db.query(SquidSetting).one().value == "512 MB"


def test_las_reglas_y_los_pools_se_reemplazan_no_se_acumulan(db):
    _restaurar(db, _backup())
    _restaurar(db, _backup(access_rules=[{"action": "deny", "acl_names": "redes", "order": 5, "enabled": True}],
                           delay_pools=[{"pool_class": 1, "parameters": "64000/64000", "acl_name": "redes", "enabled": True}]))
    reglas = db.query(AccessRule).all()
    assert [(r.action, r.order) for r in reglas] == [("deny", 5)]
    assert _contar(db, DelayPool) == 1


def test_un_grupo_existente_toma_los_miembros_del_backup(db):
    _restaurar(db, _backup())
    _restaurar(db, _backup(user_groups=[{"name": "ventas", "members": ["pedro"]}]))
    assert [m.username for m in db.query(UserGroupMember)] == ["pedro"]


def test_un_usuario_existente_conserva_su_contrasena(db):
    db.add(ProxyUser(username="ana", password_hash="$2b$hash", htpasswd_hash=None, enabled=False))
    db.commit()
    _restaurar(db, _backup())
    ana = db.query(ProxyUser).one()
    assert ana.password_hash == "$2b$hash" and ana.enabled is True


# ---------------------------------------------------------------- formato heredado: lo que se rechaza

@pytest.mark.parametrize("cambio,fragmento", [
    ({"acls": [{"name": "mala", "type": "inventado", "value": "x", "source": "inline", "enabled": True}]}, "Tipo de ACL"),
    ({"acls": [{"name": "localhost", "type": "src", "value": "x", "source": "inline", "enabled": True}]}, "reservado"),
    ({"acls": [{"name": "1mala", "type": "src", "value": "x", "source": "inline", "enabled": True}]}, "inválido"),
    ({"acls": [{"name": "x", "type": "src", "value": "a\nhttp_access allow all", "source": "inline", "enabled": True}]}, "saltos de línea"),
    ({"access_rules": [{"action": "permitir", "acl_names": "redes", "order": 1, "enabled": True}]}, "Acción de regla"),
    ({"access_rules": [{"action": "allow", "acl_names": "no_existe", "order": 1, "enabled": True}]}, "no existen"),
    ({"squid_settings": [{"key": "trusted_sources", "value": "0.0.0.0/0"}]}, ""),
    ({"squid_settings": [{"key": "cache_mem", "value": "1\nhttp_access allow all"}]}, "saltos de línea"),
    ({"ldap_config": {"server_url": "ldap://x"}}, "incompleta"),
    ({"delay_pools": [{"pool_class": 1, "parameters": "a\nb"}]}, "saltos de línea"),
    ({"user_groups": [{"name": "grupo malo!", "members": []}]}, "inválido"),
])
def test_un_backup_manipulado_se_rechaza_y_no_deja_nada(db, cambio, fragmento):
    with pytest.raises(HTTPException) as e:
        _restaurar(db, _backup(**cambio))
    assert e.value.status_code == 400 and fragmento in e.value.detail
    db.rollback()                                     # lo que hace get_db al cerrar sin commit
    assert (_contar(db, Acl), _contar(db, AccessRule), _contar(db, SquidSetting), _contar(db, UserGroup)) == (0, 0, 0, 0)


# ---------------------------------------------------------------- la ruta /restore

def test_ruta_restaura_un_json_valido(db):
    assert _ruta(db, json.dumps(_backup()).encode())["status"] == "ok"


@pytest.mark.parametrize("contenido,fragmento", [
    (b"no es json", "inválido"),
    (b"\xff\xfe\x00", "Error leyendo"),
    (json.dumps({"hola": 1}).encode(), "No es un backup válido"),
    (json.dumps({"metadata": {"version": 1}}).encode(), "No es un backup válido"),
    (json.dumps({"metadata": {"platform": "x"}, "acls": [{"type": "src"}]}).encode(), "mal formado"),
    (json.dumps({"metadata": {"platform": "x"}, "acls": "texto"}).encode(), "mal formado"),
    (json.dumps({"metadata": {"platform": "x"}, "proxy_users": [{"enabled": True}]}).encode(), "mal formado"),
])
def test_ruta_explica_los_archivos_que_no_sirven(db, contenido, fragmento):
    with pytest.raises(HTTPException) as e:
        _ruta(db, contenido)
    assert e.value.status_code == 400 and fragmento in e.value.detail
    assert _contar(db, Acl) == 0


def test_ruta_rechaza_un_archivo_demasiado_grande(db):
    with pytest.raises(HTTPException) as e:
        _ruta(db, b"{" + b" " * (bk.MAX_UPLOAD_BYTES + 10))
    assert e.value.status_code == 413


# ---------------------------------------------------------------- ida y vuelta con el formato heredado

def test_exportar_y_restaurar_en_otra_base_deja_lo_mismo(db):
    _restaurar(db, _backup())
    exportado = bk.build_backup_dict(db, "admin")
    assert exportado["metadata"]["platform"] == "SquidManager"
    json.dumps(exportado)                               # tiene que ser serializable
    db2 = _db_vacia()
    bk._aplicar_backup_heredado(db2, json.loads(json.dumps(exportado)), ADMIN)
    assert {a.name for a in db2.query(Acl)} == {"redes", "grande"}
    assert db2.query(Acl).filter_by(name="redes").one().value == "10.0.0.0/8"
    assert {m.username for m in db2.query(UserGroupMember)} == {"ana", "luis"}
    assert [(r.action, r.acl_names) for r in db2.query(AccessRule)] == [("allow", "redes")]
    # no viajan contraseñas en el formato heredado
    assert "password" not in json.dumps(exportado).lower().replace("password_hash", "")


# ---------------------------------------------------------------- formato v2 (.smbackup)

def _sembrar(db):
    _restaurar(db, _backup(ldap_users=[]))
    db.query(ProxyUser).one().password_hash = "$2b$12$abcdefghijklmnopqrstuv"
    db.commit()


def test_v2_ida_y_vuelta_sin_secretos(db):
    _sembrar(db)
    datos = b2.exportar(db, "admin", "1.0.13", passphrase=None, incluir_listas=False)
    destino = _db_vacia()
    informe = b2.restaurar(destino, b2.leer_paquete(datos), modo="combinar", simular=False)
    assert {a.name for a in destino.query(Acl)} == {"redes", "grande"}
    assert [m.username for m in destino.query(UserGroupMember).order_by(UserGroupMember.username)] == ["ana", "luis"]
    # sin contraseña de backup, el hash original no viaja: el usuario nace con uno aleatorio que no sirve para entrar
    assert destino.query(ProxyUser).one().password_hash != "$2b$12$abcdefghijklmnopqrstuv"
    assert informe.usuarios_sin_contrasena == ["ana"] and any("SIN contraseña" in a for a in informe.avisos)


def test_v2_con_secretos_recupera_el_hash_y_exige_la_contrasena(db):
    _sembrar(db)
    datos = b2.exportar(db, "admin", "1.0.13", passphrase="clave-del-backup", incluir_listas=False)
    assert b"$2b$12$abcdefghijklmnopqrstuv" not in datos
    with pytest.raises(b2.BackupError):
        b2.leer_paquete(datos, "clave-equivocada")
    destino = _db_vacia()
    b2.restaurar(destino, b2.leer_paquete(datos, "clave-del-backup"), modo="combinar", simular=False)
    assert destino.query(ProxyUser).one().password_hash == "$2b$12$abcdefghijklmnopqrstuv"


def test_v2_simular_no_toca_la_base(db):
    _sembrar(db)
    datos = b2.exportar(db, "admin", "1.0.13", incluir_listas=False)
    destino = _db_vacia()
    informe = b2.restaurar(destino, b2.leer_paquete(datos), modo="combinar", simular=True)
    assert informe is not None and _contar(destino, Acl) == 0


def test_v2_reemplazar_elimina_lo_que_no_esta_en_el_backup(db):
    _sembrar(db)
    datos = b2.exportar(db, "admin", "1.0.13", incluir_listas=False)
    destino = _db_vacia()
    destino.add(Acl(name="sobrante", type="src", value="1.1.1.1", source="inline", enabled=True))
    destino.commit()
    b2.restaurar(destino, b2.leer_paquete(datos), modo="reemplazar", simular=False)
    assert {a.name for a in destino.query(Acl)} == {"redes", "grande"}


def test_v2_combinar_conserva_lo_que_no_esta_en_el_backup(db):
    _sembrar(db)
    datos = b2.exportar(db, "admin", "1.0.13", incluir_listas=False)
    destino = _db_vacia()
    destino.add(Acl(name="sobrante", type="src", value="1.1.1.1", source="inline", enabled=True))
    destino.commit()
    b2.restaurar(destino, b2.leer_paquete(datos), modo="combinar", simular=False)
    assert {a.name for a in destino.query(Acl)} == {"redes", "grande", "sobrante"}


@pytest.mark.parametrize("basura", [b"", b"no es un zip", b"PK\x03\x04roto"])
def test_v2_archivos_que_no_son_un_backup(basura):
    with pytest.raises(b2.BackupError):
        b2.leer_paquete(basura)


def test_v2_ruta_restore_explica_el_error(db):
    with pytest.raises(HTTPException) as e:
        asyncio.run(bk.restore_backup_v2(request=N(headers={}), file=_subir(b"no es un zip"), contrasena=None,
                                         modo="combinar", simular=True, aplicar=False, db=db, admin=ADMIN))
    assert e.value.status_code == 400


def test_v2_ruta_export_exige_contrasena_larga(db):
    with pytest.raises(HTTPException) as e:
        bk.export_backup_v2(bk.ExportRequest(contrasena="corta"), db=db, admin=ADMIN)
    assert e.value.status_code == 400 and "8 caracteres" in e.value.detail


# ---------------------------------------------------------------- migrar desde un Squid tradicional

SQUID_CONF = b"""http_port 3128
acl red_local src 192.168.1.0/24
acl sitios dstdomain .ejemplo.com
acl puertos_ok port 443 8080
http_access deny sitios
http_access allow red_local
http_access deny all
"""


def _zip(archivos: dict[str, bytes]) -> bytes:
    import zipfile
    b = BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for n, d in archivos.items():
            z.writestr(n, d)
    return b.getvalue()


def _targz(archivos: dict[str, bytes]) -> bytes:
    import tarfile
    b = BytesIO()
    with tarfile.open(fileobj=b, mode="w:gz") as t:
        for n, d in archivos.items():
            i = tarfile.TarInfo(n)
            i.size = len(d)
            t.addfile(i, BytesIO(d))
    return b.getvalue()


def test_expandir_zip_targz_y_sueltos():
    r = bk._expandir_subidas([
        ("a.zip", _zip({"etc/squid/squid.conf": b"x", "etc/squid/lista.txt": b"y"})),
        ("b.tar.gz", _targz({"dir/otro.conf": b"z"})),
        ("suelto.txt", b"hola"),
    ])
    assert r == {"squid.conf": "x", "lista.txt": "y", "otro.conf": "z", "suelto.txt": "hola"}


def test_expandir_ignora_binarios_y_vacios_y_prefiere_la_ruta_menos_profunda():
    r = bk._expandir_subidas([
        ("a.zip", _zip({"profundo/uno/squid.conf": b"hondo", "squid.conf": b"raiz", "bin.dat": b"\x00\x01", "vacio": b""})),
    ])
    assert r == {"squid.conf": "raiz"}


def test_expandir_no_escribe_en_disco_rutas_con_puntos(tmp_path):
    # solo se usa el nombre base como clave; nada se extrae a disco
    r = bk._expandir_subidas([("a.zip", _zip({"../../etc/passwd": b"root", "..\\..\\x.conf": b"c"}))])
    assert set(r) == {"passwd", "x.conf"}


def test_expandir_errores_claros():
    with pytest.raises(HTTPException) as e:
        bk._expandir_subidas([("roto.zip", b"no es un zip")])
    assert e.value.status_code == 400 and "roto.zip" in e.value.detail
    with pytest.raises(HTTPException) as e:
        bk._expandir_subidas([("roto.tar.gz", b"no es un tar")])
    assert e.value.status_code == 400
    with pytest.raises(HTTPException) as e:
        bk._expandir_subidas([("muchos.zip", _zip({f"f{i}.conf": b"x" for i in range(bk.MAX_ARCHIVO_COMPRIMIDO_MIEMBROS + 1)}))])
    assert e.value.status_code == 400 and "demasiados" in e.value.detail


def test_expandir_limite_total(monkeypatch):
    monkeypatch.setattr(bk, "MAX_TEXTO_TOTAL", 100)
    with pytest.raises(HTTPException) as e:
        bk._expandir_subidas([("a.txt", b"a" * 60), ("b.txt", b"b" * 60)])
    assert e.value.status_code == 413


def test_un_archivo_enorme_suelto_se_ignora(monkeypatch):
    monkeypatch.setattr(bk, "MAX_TEXTO_POR_ARCHIVO", 10)
    assert bk._expandir_subidas([("grande.txt", b"x" * 11)]) == {}


def _analizar(db, archivos, principal=None):
    subidas = [UploadFile(file=BytesIO(d), filename=n) for n, d in archivos]
    return asyncio.run(bk.analyze_squid_conf(request=N(headers={}), files=subidas, principal=principal, db=db, admin=ADMIN))


def test_analizar_un_squid_conf_no_escribe_nada_y_devuelve_token(db):
    out = _analizar(db, [("squid.conf", SQUID_CONF)])
    assert out["status"] == "ok" and out["token"] and out["principal"] == "squid.conf"
    assert {a["name"] for a in out["acls"]} >= {"red_local", "sitios"}
    assert _contar(db, Acl) == 0 and _contar(db, AccessRule) == 0


def test_analizar_encuentra_el_conf_dentro_de_un_zip(db):
    out = _analizar(db, [("etc.zip", _zip({"etc/squid/squid.conf": SQUID_CONF}))])
    assert out["principal"] == "squid.conf"


def test_analizar_sin_squid_conf_explica_que_falta(db):
    with pytest.raises(HTTPException) as e:
        _analizar(db, [("otra_cosa.txt", b"hola")])
    assert e.value.status_code == 400 and "squid.conf" in e.value.detail


def test_analizar_limita_la_cantidad_de_archivos(db):
    with pytest.raises(HTTPException) as e:
        _analizar(db, [(f"f{i}.txt", b"x") for i in range(bk.MAX_IMPORT_FILES + 1)])
    assert e.value.status_code == 400


def test_importar_aplica_una_vez_y_el_token_se_consume(db):
    token = _analizar(db, [("squid.conf", SQUID_CONF)])["token"]
    out = bk.apply_squid_import(request=N(headers={}), token=token, importar_usuarios=True, importar_dns=True, db=db, admin=ADMIN)
    assert out["status"] == "ok" and _contar(db, Acl) >= 2
    assert any("Aplicar cambios" in a for a in out["details"]["avisos"])
    with pytest.raises(HTTPException) as e:
        bk.apply_squid_import(request=N(headers={}), token=token, importar_usuarios=True, importar_dns=True, db=db, admin=ADMIN)
    assert e.value.status_code == 400 and "expiró" in e.value.detail


def test_importar_con_token_inventado(db):
    with pytest.raises(HTTPException) as e:
        bk.apply_squid_import(request=N(headers={}), token="inventado", importar_usuarios=True, importar_dns=True, db=db, admin=ADMIN)
    assert e.value.status_code == 400


# ---------------------------------------------------------------- tras restaurar v2

def test_despues_de_restaurar_deja_aviso_y_no_aplica_si_no_se_pide(db, monkeypatch):
    from app.services import squid_service as ss
    llamadas = []
    monkeypatch.setattr(ss, "write_passwd_file", lambda d: llamadas.append("passwd"))
    monkeypatch.setattr(ss, "write_digest_file", lambda d, realm: llamadas.append("digest"))
    monkeypatch.setattr(ss, "realm_actual", lambda d: "r")
    monkeypatch.setattr(ss, "purge_credentials", lambda: llamadas.append("purge"))
    monkeypatch.setattr(ss, "apply_squid_config", lambda d: llamadas.append("APPLY") or {"status": "ok", "message": "m"})
    salida = {"modo": "combinar"}
    bk._despues_de_restaurar(db, ADMIN, False, salida)
    assert "APPLY" not in llamadas and llamadas[:2] == ["passwd", "digest"]
    assert any("pendiente" in a for a in salida["avisos"])
    salida2 = {}
    bk._despues_de_restaurar(db, ADMIN, True, salida2)
    assert "APPLY" in llamadas and salida2["aplicado"]["status"] == "ok"


def test_despues_de_restaurar_un_fallo_de_archivos_no_aborta(db, monkeypatch):
    from app.services import squid_service as ss
    monkeypatch.setattr(ss, "write_passwd_file", lambda d: (_ for _ in ()).throw(OSError("disco lleno")))
    monkeypatch.setattr(ss, "purge_credentials", lambda: None)
    salida = {}
    bk._despues_de_restaurar(db, ADMIN, False, salida)
    assert any("disco lleno" in a for a in salida["avisos"])
