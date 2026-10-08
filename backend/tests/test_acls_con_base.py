"""ACLs contra una base SQLite en memoria: alta, edición, baja, uso, carga masiva por archivo y acciones en bloque."""
import asyncio
from io import BytesIO
from types import SimpleNamespace as N

import pytest
from fastapi import HTTPException, UploadFile

from app.models.access_rule import AccessRule
from app.models.acl import Acl
from app.models.audit_log import AuditLog
from app.models.delay_pool import DelayPool
from app.routes import acls as r
from app.schemas.acl import AclCreate, AclUpdate
from app.services import squid_service as ss
from tests.bd_sqlite import nueva_sesion

ADMIN = N(id=1, username="admin")


@pytest.fixture
def ctx(monkeypatch, tmp_path):
    db = nueva_sesion()
    ev = {"marcas": 0, "avisos": [], "indice": [], "indice_borrado": []}
    monkeypatch.setattr(r, "mark_dirty", lambda: ev.__setitem__("marcas", ev["marcas"] + 1))
    monkeypatch.setattr(ss, "mark_dirty", lambda: ev.__setitem__("marcas", ev["marcas"] + 1), raising=False)
    monkeypatch.setattr("app.services.config_state.mark_dirty", lambda: ev.__setitem__("marcas", ev["marcas"] + 1))
    monkeypatch.setattr(r, "queue_notification", lambda bt, d, tipo, titulo, msg: ev["avisos"].append(msg))
    monkeypatch.setattr(ss, "ACL_LISTS_DIR", tmp_path)
    from app.services import domain_index_service as di
    monkeypatch.setattr(di, "index_category", lambda n, lista, h: ev["indice"].append((n, len(lista))))
    monkeypatch.setattr(di, "remove_category", lambda n: ev["indice_borrado"].append(n))
    ev["dir"] = tmp_path
    yield db, ev
    db.close()


def _crear(db, nombre="redes", tipo="src", valor="10.0.0.0/8", **kw):
    return r.create_acl(AclCreate(name=nombre, type=tipo, value=valor, **kw), db=db, current_admin=ADMIN, background_tasks=None)


def _usar(db, nombre):
    db.add(AccessRule(action="deny", acl_names=nombre, order=1, enabled=True))
    db.commit()


# ---------------------------------------------------------------- alta

def test_crear_deja_la_acl_pendiente_de_aplicar(ctx):
    db, ev = ctx
    a = _crear(db, display_name="Redes internas")
    assert a.name == "redes" and a.source == "inline" and a.display_name == "Redes internas" and ev["marcas"] == 1
    assert [x.action for x in db.query(AuditLog)] == ["create"]


@pytest.mark.parametrize("nombre,tipo,valor,codigo", [
    ("1mala", "src", "x", 400), ("all", "src", "x", 400), ("ok", "inventado", "x", 400),
    ("ok", "src", "a\nb", 400), ("ok", "src", "#comentario", 400), ("ok", "src", "   ", 400),
    ("ok", "url_regex", 'x" /etc/passwd', 400), ("ok", "dstdomain", "a.com 'b'", 400),
])
def test_crear_rechaza_entradas_peligrosas(ctx, nombre, tipo, valor, codigo):
    db, _ = ctx
    with pytest.raises(HTTPException) as e:
        r.create_acl(AclCreate.model_construct(name=nombre, type=tipo, value=valor, description=None, enabled=True,
                                               is_category=False, display_name=None),
                     db=db, current_admin=ADMIN, background_tasks=None)
    assert e.value.status_code == codigo and db.query(Acl).count() == 0


def test_crear_no_repite_nombre_y_una_categoria_es_de_dominio(ctx):
    db, _ = ctx
    _crear(db)
    with pytest.raises(HTTPException) as e:
        _crear(db)
    assert "Ya existe" in e.value.detail
    with pytest.raises(HTTPException) as e:
        _crear(db, "cat", "src", "1.1.1.1", is_category=True)
    assert "categoría" in e.value.detail
    assert _crear(db, "cat2", "dstdomain", ".a.com", is_category=True).is_category


# ---------------------------------------------------------------- edición

def test_editar_valor_tipo_y_descripcion(ctx):
    db, _ = ctx
    a = _crear(db)
    out = r.update_acl(a.id, AclUpdate(value="192.168.0.0/16", description="d", enabled=False), db=db, current_admin=ADMIN, background_tasks=None)
    assert out.value == "192.168.0.0/16" and out.description == "d" and out.enabled is False


def test_renombrar_una_acl_en_uso_se_rechaza_y_una_libre_se_puede(ctx):
    db, _ = ctx
    a = _crear(db)
    _usar(db, "redes")
    with pytest.raises(HTTPException) as e:
        r.update_acl(a.id, AclUpdate(name="otra"), db=db, current_admin=ADMIN, background_tasks=None)
    assert e.value.status_code == 409 and "en uso" in e.value.detail
    libre = _crear(db, "libre", "port", "80")
    assert r.update_acl(libre.id, AclUpdate(name="nueva"), db=db, current_admin=ADMIN, background_tasks=None).name == "nueva"


def test_renombrar_a_un_nombre_ocupado_o_invalido(ctx):
    db, _ = ctx
    a = _crear(db, "a1"); _crear(db, "a2", "port", "80")
    for nuevo, frag in (("a2", "Ya existe"), ("2mal", "inválido"), ("localhost", "reservado")):
        with pytest.raises(HTTPException) as e:
            r.update_acl(a.id, AclUpdate(name=nuevo), db=db, current_admin=ADMIN, background_tasks=None)
        assert frag in e.value.detail


def test_editar_valida_valor_tipo_y_categoria(ctx):
    db, _ = ctx
    a = _crear(db)
    for cambio in (AclUpdate(value="a\nb"), AclUpdate(value='x"y'), AclUpdate(type="inventado"), AclUpdate(is_category=True)):
        with pytest.raises(HTTPException) as e:
            r.update_acl(a.id, cambio, db=db, current_admin=ADMIN, background_tasks=None)
        assert e.value.status_code == 400
    assert db.query(Acl).one().value == "10.0.0.0/8"


def test_sync_url_solo_https_y_vacia_la_desconecta(ctx):
    db, _ = ctx
    a = _crear(db, "cat", "dstdomain", ".a.com")
    with pytest.raises(HTTPException):
        r.update_acl(a.id, AclUpdate(sync_url="http://x.com/lista"), db=db, current_admin=ADMIN, background_tasks=None)
    assert r.update_acl(a.id, AclUpdate(sync_url="https://x.com/lista"), db=db, current_admin=ADMIN, background_tasks=None).sync_url == "https://x.com/lista"
    assert r.update_acl(a.id, AclUpdate(sync_url=""), db=db, current_admin=ADMIN, background_tasks=None).sync_url is None
    assert r.update_acl(a.id, AclUpdate(display_name=""), db=db, current_admin=ADMIN, background_tasks=None).display_name is None


def test_editar_o_borrar_inexistente_da_404(ctx):
    db, _ = ctx
    with pytest.raises(HTTPException) as e:
        r.update_acl(99, AclUpdate(), db=db, current_admin=ADMIN, background_tasks=None)
    assert e.value.status_code == 404
    with pytest.raises(HTTPException) as e:
        r.delete_acl(99, db=db, current_admin=ADMIN, background_tasks=None)
    assert e.value.status_code == 404


# ---------------------------------------------------------------- baja y uso

def test_borrar_una_acl_en_uso_da_409_y_una_libre_se_borra(ctx):
    db, ev = ctx
    usada = _crear(db); libre = _crear(db, "libre", "port", "80")
    _usar(db, "redes")
    with pytest.raises(HTTPException) as e:
        r.delete_acl(usada.id, db=db, current_admin=ADMIN, background_tasks=None)
    assert e.value.status_code == 409 and db.query(Acl).count() == 2
    r.delete_acl(libre.id, db=db, current_admin=ADMIN, background_tasks=None)
    assert [a.name for a in db.query(Acl)] == ["redes"]


def test_el_uso_incluye_delay_pools_y_negaciones(ctx):
    db, _ = ctx
    _crear(db, "a1"); _crear(db, "a2", "port", "80"); _crear(db, "a3", "port", "81"); _crear(db, "a4", "port", "82")
    db.add(AccessRule(action="allow", acl_names="a1 !a2", order=1, enabled=True))
    db.add(DelayPool(pool_class=1, parameters="64000/64000", acl_name="a3", enabled=True))
    db.commit()
    usos = r.acl_usage(db=db, _=ADMIN)
    assert set(usos) == {"a1", "a2", "a3"}
    assert r.list_unused_acls(db=db, _=ADMIN) == ["a4"]


def test_listar_filtra_por_categoria_y_pagina(ctx):
    db, _ = ctx
    _crear(db, "a1"); _crear(db, "c1", "dstdomain", ".a.com", is_category=True); _crear(db, "a2", "port", "80")
    assert [x.name for x in r.list_acls(limit=10, offset=0, is_category=True, db=db, _=ADMIN)] == ["c1"]
    assert [x.name for x in r.list_acls(limit=10, offset=0, is_category=False, db=db, _=ADMIN)] == ["a1", "a2"]
    assert [x.name for x in r.list_acls(limit=1, offset=1, is_category=None, db=db, _=ADMIN)] == ["a2"]


# ---------------------------------------------------------------- acciones en bloque

def test_bloque_borrar_respeta_las_que_estan_en_uso(ctx):
    db, ev = ctx
    a = _crear(db, "a1"); b = _crear(db, "a2", "port", "80"); c = _crear(db, "a3", "port", "81")
    _usar(db, "a2")
    out = r.accion_masiva(r.AclBulkIn(ids=[a.id, b.id, c.id, 999], accion="delete"), db=db, current_admin=ADMIN, background_tasks=None)
    assert out["hechas"] == ["a1", "a3"] and {o["name"] for o in out["omitidas"]} == {"a2", None}
    assert [x.name for x in db.query(Acl)] == ["a2"]


def test_bloque_activar_y_desactivar_solo_audita_lo_que_cambia(ctx):
    db, _ = ctx
    a = _crear(db, "a1"); b = _crear(db, "a2", "port", "80", enabled=False)
    antes = db.query(AuditLog).count()
    r.accion_masiva(r.AclBulkIn(ids=[a.id, b.id], accion="enable"), db=db, current_admin=ADMIN, background_tasks=None)
    assert all(x.enabled for x in db.query(Acl)) and db.query(AuditLog).count() == antes + 1


def test_bloque_valida_la_peticion():
    for malo in ({"ids": [], "accion": "delete"}, {"ids": [1], "accion": "destruir"}, {"ids": list(range(1001)), "accion": "delete"}):
        with pytest.raises(Exception):
            r.AclBulkIn(**malo)


# ---------------------------------------------------------------- carga masiva por archivo

def _cargar(db, contenido, nombre="lista", tipo="src", modo="reemplazar", **kw):
    return asyncio.run(r.cargar_dominios_masivo(
        file=UploadFile(file=BytesIO(contenido.encode()), filename="l.txt"), acl_name=nombre, modo=modo, acl_type=tipo,
        description=None, is_category=kw.get("is_category", False), db=db, current_admin=ADMIN, background_tasks=None))


def _ips(n, desde=0):
    return "".join(f"10.{(i + desde) // 250}.{(i + desde) % 250}.1\n" for i in range(n))


def test_carga_chica_queda_en_linea_y_grande_pasa_a_archivo(ctx):
    db, ev = ctx
    out = _cargar(db, _ips(50))
    assert out["acl"]["source"] == "inline" and out["dominios_importados"] == 50
    out = _cargar(db, _ips(300))
    assert out["acl"]["source"] == "file" and out["acl"]["line_count"] == 300 and out["acl"]["value"] is None
    assert len((ev["dir"] / "lista.txt").read_text().splitlines()) == 300


def test_carga_que_vuelve_a_bajar_del_umbral_vuelve_a_linea(ctx):
    db, _ = ctx
    _cargar(db, _ips(300))
    out = _cargar(db, _ips(5))
    assert out["acl"]["source"] == "inline" and db.query(Acl).one().value.count(" ") == 4


def test_agregar_suma_sin_duplicar_en_linea_y_en_archivo(ctx):
    db, _ = ctx
    _cargar(db, "10.0.0.1\n10.0.0.2\n")
    out = _cargar(db, "10.0.0.2\n10.0.0.3\n", modo="agregar")
    assert out["dominios_importados"] == 3
    _cargar(db, _ips(300), nombre="grande")
    out = _cargar(db, _ips(10, desde=295), nombre="grande", modo="agregar")
    assert out["dominios_importados"] == 305 and out["acl"]["line_count"] == 305


def test_recargar_la_misma_lista_no_marca_cambios(ctx):
    db, ev = ctx
    _cargar(db, _ips(300))
    marcas = ev["marcas"]
    _cargar(db, _ips(300))
    assert ev["marcas"] == marcas
    _cargar(db, _ips(301))
    assert ev["marcas"] == marcas + 1


def test_carga_de_dominios_se_indexa_y_las_de_ip_no(ctx):
    db, ev = ctx
    _cargar(db, "".join(f"d{i}.com\n" for i in range(300)), nombre="blocklist", tipo="dstdomain")
    _cargar(db, _ips(300), nombre="ips")
    assert ev["indice"] == [("blocklist", 300)]


def test_carga_con_modo_o_limite_invalido(ctx, monkeypatch):
    db, _ = ctx
    with pytest.raises(HTTPException) as e:
        _cargar(db, "10.0.0.1\n", modo="borrar")
    assert e.value.status_code == 400
    monkeypatch.setattr(r, "MAX_UPLOAD_BYTES", 10)
    with pytest.raises(HTTPException) as e:
        _cargar(db, "10.0.0.1\n10.0.0.2\n10.0.0.3\n")
    assert e.value.status_code == 413


def test_una_acl_de_archivo_no_se_edita_a_mano(ctx):
    db, _ = ctx
    _cargar(db, _ips(300))
    a = db.query(Acl).one()
    for cambio in (AclUpdate(value="1.1.1.1"), AclUpdate(name="otro"), AclUpdate(type="dst")):
        with pytest.raises(HTTPException) as e:
            r.update_acl(a.id, cambio, db=db, current_admin=ADMIN, background_tasks=None)
        assert e.value.status_code == 400
    assert r.update_acl(a.id, AclUpdate(description="solo descripción"), db=db, current_admin=ADMIN, background_tasks=None).description


def test_borrar_una_acl_de_dominios_de_archivo_limpia_el_indice(ctx):
    db, ev = ctx
    _cargar(db, "".join(f"d{i}.com\n" for i in range(300)), nombre="blocklist", tipo="dstdomain")
    r.delete_acl(db.query(Acl).one().id, db=db, current_admin=ADMIN, background_tasks=None)
    assert ev["indice_borrado"] == ["blocklist"]


# ---------------------------------------------------------------- sincronización de categorías

def test_sincronizar_ahora_exige_url(ctx, monkeypatch):
    db, _ = ctx
    a = _crear(db, "cat", "dstdomain", ".a.com")
    with pytest.raises(HTTPException) as e:
        r.sincronizar_categoria_ahora(a.id, db=db, current_admin=ADMIN)
    assert e.value.status_code == 400
    with pytest.raises(HTTPException) as e:
        r.sincronizar_categoria_ahora(99, db=db, current_admin=ADMIN)
    assert e.value.status_code == 404
    llamadas = []
    monkeypatch.setattr("app.services.category_sync_service.sync_one", lambda d, acl: llamadas.append(acl.name))
    r.update_acl(a.id, AclUpdate(sync_url="https://x.com/l"), db=db, current_admin=ADMIN, background_tasks=None)
    assert r.sincronizar_categoria_ahora(a.id, db=db, current_admin=ADMIN).name == "cat" and llamadas == ["cat"]
