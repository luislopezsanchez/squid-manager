"""Generación del index.json de un mes consolidado (squid/build_monthly_index.py).

Standalone respecto al backend a propósito (corre dentro del contenedor de
Squid, sin el venv del backend): se importa como script suelto, no como
paquete de la app.
"""

import gzip
import importlib.util
import json
import sys
from pathlib import Path

import pytest


def _raiz_del_proyecto() -> Path | None:
    for base in Path(__file__).resolve().parents:
        if (base / "squid" / "build_monthly_index.py").is_file():
            return base
    return None


@pytest.fixture
def modulo():
    raiz = _raiz_del_proyecto()
    if raiz is None:
        pytest.skip("el proyecto no esta accesible desde aqui")
    ruta = raiz / "squid" / "build_monthly_index.py"
    spec = importlib.util.spec_from_file_location("build_monthly_index", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def gz_de_prueba(tmp_path):
    lineas = [
        "1798700000.100    50 10.0.0.5 TCP_MISS/200 1000 GET http://a.com/ ana HIER_DIRECT/1.2.3.4 text/html",
        "1798700010.200    30 10.0.0.6 TCP_DENIED/403 500 GET http://b.com/ - HIER_NONE/- text/html",
        "1798700020.300    40 10.0.0.5 TCP_HIT/200 2000 GET http://a.com/x ana HIER_NONE/- text/html",
        "esto no es una linea valida de squid",
    ]
    gz_path = tmp_path / "access-202603.log.gz"
    with gzip.open(gz_path, "wt", encoding="utf-8") as f:
        f.write("\n".join(lineas) + "\n")
    return gz_path


def test_dominio_de_extrae_host_de_una_url_http(modulo):
    assert modulo.dominio_de("http://www.example.com/ruta") == "example.com"


def test_dominio_de_sin_www_no_lo_toca(modulo):
    assert modulo.dominio_de("http://example.com/") == "example.com"


def test_ignora_lineas_que_no_matchean_el_patron(modulo, gz_de_prueba):
    indice = modulo.construir_indice(gz_de_prueba, 2026, 3)
    assert indice["total_lines"] == 3  # las 3 validas, no la linea rota


def test_cuenta_denegados_por_status(modulo, gz_de_prueba):
    indice = modulo.construir_indice(gz_de_prueba, 2026, 3)
    assert indice["denied_count"] == 1
    assert indice["status_codes"]["403"] == 1
    assert indice["status_codes"]["200"] == 2


def test_usuarios_unicos_no_cuenta_el_guion(modulo, gz_de_prueba):
    """'-' significa 'sin usuario', no es un usuario llamado '-'."""
    indice = modulo.construir_indice(gz_de_prueba, 2026, 3)
    assert indice["unique_users"] == 1
    assert indice["top_users"] == [{"user": "ana", "count": 2}]


def test_dominios_unicos_y_bytes_totales(modulo, gz_de_prueba):
    indice = modulo.construir_indice(gz_de_prueba, 2026, 3)
    assert indice["unique_domains"] == 2
    assert indice["total_bytes"] == 3500


def test_rango_de_fechas_primero_y_ultimo(modulo, gz_de_prueba):
    indice = modulo.construir_indice(gz_de_prueba, 2026, 3)
    assert indice["date_range"]["first"] is not None
    assert indice["date_range"]["last"] is not None
    assert indice["date_range"]["first"] <= indice["date_range"]["last"]


def test_indice_es_json_valido_de_extremo_a_extremo(modulo, gz_de_prueba, tmp_path):
    salida = tmp_path / "index.json"
    sys.argv = ["build_monthly_index.py", str(gz_de_prueba), "2026", "3", str(salida)]
    modulo.main()
    leido = json.loads(salida.read_text(encoding="utf-8"))
    assert leido["year"] == 2026
    assert leido["month"] == 3
    assert leido["total_lines"] == 3
