"""Carga masiva de ACLs por archivo para tipos que no son dominio (IP, URL, puertos)."""
import asyncio
from io import BytesIO
from types import SimpleNamespace as N

import pytest
from fastapi import HTTPException, UploadFile

from app.routes import acls as r
from app.services.squid_names import TIPOS_CARGA_MASIVA, validar_lista_por_tipo


def test_ips_redes_y_rangos_ipv4_e_ipv6():
    validos, malos = validar_lista_por_tipo("src", [
        "192.168.1.10", "10.0.0.0/8", "10.0.0.1-10.0.0.50", "2001:db8::/32", "fe80::1",
        "10.0.0.0/255.255.255.0", "# comentario", "", "192.168.1.10",
        "300.1.1.1", "10.0.0.50-10.0.0.1", "10.0.0.1-2001:db8::1", "hola", "10.0.0.0/33",
    ])
    assert validos == ["192.168.1.10", "10.0.0.0/8", "10.0.0.1-10.0.0.50", "2001:db8::/32", "fe80::1",
                       "10.0.0.0/255.255.255.0"]
    assert malos == ["300.1.1.1", "10.0.0.50-10.0.0.1", "10.0.0.1-2001:db8::1", "hola", "10.0.0.0/33"]


def test_puertos():
    validos, malos = validar_lista_por_tipo("port", ["443", "8000-8100", "70000", "9000-8000", "ab", "1-2-3", "80"])
    assert validos == ["443", "8000-8100", "80"]
    assert malos == ["70000", "9000-8000", "ab", "1-2-3"]


def test_regex_sin_espacios_y_que_compilen():
    validos, malos = validar_lista_por_tipo("url_regex", [r"\.mp4$", r"^http://ads\.", "con espacio", "(sin cerrar", "[a-"])
    assert validos == [r"\.mp4$", r"^http://ads\."]
    assert malos == ["con espacio", "(sin cerrar", "[a-"]


def test_dominios_siguen_igual():
    validos, malos = validar_lista_por_tipo("dstdomain", [".facebook.com", ".FACEBOOK.com", "no es dominio!"])
    assert validos == [".facebook.com"] and malos == ["no es dominio!"]


def _subir(contenido: str):
    return UploadFile(file=BytesIO(contenido.encode()), filename="lista.txt")


def _llamar(monkeypatch, tipo, contenido, **extra):
    capturado = {}

    def falso(db, name, acl_type, nuevos, modo, descripcion, categoria, **kw):
        capturado.update(name=name, tipo=acl_type, nuevos=nuevos)
        return N(id=1, name=name, type=acl_type, value=" ".join(nuevos), source="inline", enabled=True,
                 description="", is_category=categoria, display_name=None, sync_url=None, line_count=None,
                 content_hash=None, created_at=None, updated_at=None, sync_enabled=False,
                 last_sync_at=None, last_sync_status=None), {"combinados": len(nuevos), "source": "inline"}

    monkeypatch.setattr("app.services.squid_service.aplicar_lista_dominios", falso)
    monkeypatch.setattr(r, "_to_response", lambda a: N(model_dump=lambda mode=None: {"source": a.source}))
    out = asyncio.run(r.cargar_dominios_masivo(
        file=_subir(contenido), acl_name="lista_ips", modo="reemplazar", acl_type=tipo, description=None,
        is_category=extra.get("is_category", False), db=None, current_admin=N(id=1, username="admin"),
        background_tasks=None))
    return out, capturado


def test_endpoint_acepta_un_archivo_de_ips(monkeypatch):
    out, cap = _llamar(monkeypatch, "src", "10.0.0.0/8\n192.168.1.5\nbasura\n")
    assert cap["tipo"] == "src" and cap["nuevos"] == ["10.0.0.0/8", "192.168.1.5"]
    assert out["dominios_importados"] == 2 and out["total_rechazados"] == 1 and out["rechazados"] == ["basura"]


def test_endpoint_rechaza_archivo_sin_entradas_validas(monkeypatch):
    with pytest.raises(HTTPException) as e:
        _llamar(monkeypatch, "port", "abc\nxyz\n")
    assert e.value.status_code == 400 and "ninguna entrada válida" in e.value.detail


@pytest.mark.parametrize("tipo", ["time", "proto", "method", "maxconn", "proxy_auth", "raro"])
def test_endpoint_rechaza_tipos_que_no_se_cargan_en_masa(monkeypatch, tipo):
    assert tipo not in TIPOS_CARGA_MASIVA
    with pytest.raises(HTTPException) as e:
        _llamar(monkeypatch, tipo, "x\n")
    assert e.value.status_code == 400


def test_una_categoria_solo_puede_ser_de_dominio(monkeypatch):
    with pytest.raises(HTTPException) as e:
        _llamar(monkeypatch, "src", "10.0.0.1\n", is_category=True)
    assert e.value.status_code == 400
