"""Reglas de ancho de banda nuevas (app/services/bandwidth_service.py)."""
import json
import types

from app.services import bandwidth_service as bw


def _pool(**kw):
    base = dict(pool_class=1, parameters="", acl_name=None, acl_names=None, targets=None,
                download_bps=None, shared=True)
    base.update(kw)
    return types.SimpleNamespace(**base)


def test_regla_antigua_conserva_clase_parametros_y_acl():
    d = bw.directivas([_pool(pool_class=2, parameters="64000/64000 64000/32000", acl_name="streaming")])
    assert d == [{"clase": 2, "parametros": "64000/64000 64000/32000", "acls": ["streaming"]}]


def test_regla_antigua_sin_acl_aplica_a_todo():
    d = bw.directivas([_pool(pool_class=1, parameters="1000/1000")])
    assert d[0]["acls"] == ["all"]


def test_descarga_compartida_es_clase_1_y_por_equipo_es_clase_2():
    assert bw.parametros_descarga(50000, True) == (1, "50000/50000")
    clase, params = bw.parametros_descarga(50000, False)
    assert clase == 2 and params == f"{bw.AGREGADO_SIN_LIMITE}/{bw.AGREGADO_SIN_LIMITE} 50000/50000"


def test_regla_nueva_traduce_descarga_y_acls():
    d = bw.directivas([_pool(targets="[]", acl_names="a b", download_bps=5000)])
    assert d == [{"clase": 1, "parametros": "5000/5000", "acls": ["a", "b"]}]


def test_regla_nueva_sin_limite_no_genera_nada():
    assert bw.directivas([_pool(targets="[]", acl_names="a")]) == []


def test_nombre_de_acl_de_usuario_es_estable_y_valido_para_squid():
    n = bw.nombre_acl_usuario("juan.perez")
    assert n == bw.nombre_acl_usuario("juan.perez") and n != bw.nombre_acl_usuario("juan_perez")
    assert n.replace("_", "").isalnum()


def test_los_tipos_de_trafico_generan_regex_con_o_sin_query_string():
    import re
    regex = bw._regex_extensiones(bw.TIPOS_TRAFICO["video"]["extensiones"])
    patron = re.compile(regex.replace("-i ", ""), re.I)
    assert patron.search("http://x.com/a/pelicula.MP4")
    assert patron.search("http://x.com/a/pelicula.mp4?token=abc")
    assert not patron.search("http://x.com/a/pelicula.mp4.txt")
    assert not patron.search("http://x.com/mp4")


def test_validar_limite():
    import pytest
    from fastapi import HTTPException
    for malo in (None, 0, -5, 10 * 1024 * 1024 * 1024 + 1):
        with pytest.raises(HTTPException):
            bw.validar_limite(malo)
    bw.validar_limite(1000)


def test_serializar_objetivos_no_repite_acls():
    j, nombres = bw.serializar_objetivos([
        {"kind": "acl", "value": "a", "acl": "a"}, {"kind": "group", "value": "a", "acl": "a"},
        {"kind": "all", "value": "", "acl": "all"}])
    assert nombres == "a all" and len(json.loads(j)) == 3
