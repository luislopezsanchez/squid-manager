"""Logs históricos: lectura de los meses ya consolidados en frío.

Se cuida sobre todo que esta capa esté genuinamente separada de log_service
(la que usa el polling del panel): nada de caché compartida, nada de tocar
el access.log activo, y que un mes sin index.json no rompa el listado.
"""

import gzip
import json
from pathlib import Path

import pytest

from app.services import historical_log_service as hls


@pytest.fixture
def mes_de_prueba(tmp_path, monkeypatch):
    """Arma un archive/historical/2026/03/ con un access.log.gz real y su índice."""
    monkeypatch.setattr(hls, "HISTORICAL_DIR", tmp_path)
    mes_dir = tmp_path / "2026" / "03"
    mes_dir.mkdir(parents=True)

    lineas = [
        "1798700000.123    50 10.0.0.5 TCP_MISS/200 1234 GET http://example.com/ jperez HIER_DIRECT/93.184.216.34 text/html",
        "1798700010.456    30 10.0.0.6 TCP_DENIED/407 500 GET http://otro.com/ - HIER_NONE/- text/html",
        "1798700020.789    40 10.0.0.5 TCP_HIT/200 800 GET http://example.com/img.png jperez HIER_NONE/- image/png",
    ]
    gz_path = mes_dir / "access-202603.log.gz"
    with gzip.open(gz_path, "wt", encoding="utf-8") as f:
        f.write("\n".join(lineas) + "\n")

    indice = {
        "year": 2026, "month": 3, "file": gz_path.name,
        "size_bytes": gz_path.stat().st_size, "total_lines": 3,
        "unique_users": 1, "unique_domains": 1,
        "status_codes": {"200": 2, "407": 1},
        "denied_count": 1, "total_bytes": 2534,
    }
    (mes_dir / "index.json").write_text(json.dumps(indice), encoding="utf-8")
    return tmp_path


def test_sin_directorio_historico_lista_vacio(tmp_path, monkeypatch):
    """Instalación recién hecha, todavía sin ningún mes cerrado."""
    monkeypatch.setattr(hls, "HISTORICAL_DIR", tmp_path / "no-existe")
    assert hls.list_months() == []


def test_lista_meses_leyendo_solo_el_indice(mes_de_prueba):
    meses = hls.list_months()
    assert len(meses) == 1
    assert meses[0]["year"] == 2026
    assert meses[0]["month"] == 3
    assert meses[0]["denied_count"] == 1


def test_mes_sin_indice_igual_aparece_marcado(tmp_path, monkeypatch):
    """Instalación vieja que consolidó antes de tener el indexador: no debe
    desaparecer el mes solo porque falte el resumen."""
    monkeypatch.setattr(hls, "HISTORICAL_DIR", tmp_path)
    mes_dir = tmp_path / "2025" / "12"
    mes_dir.mkdir(parents=True)
    gz = mes_dir / "access-202512.log.gz"
    gz.write_bytes(b"")

    meses = hls.list_months()
    assert len(meses) == 1
    assert meses[0]["sin_indice"] is True


def test_get_month_index_devuelve_none_si_no_existe(tmp_path, monkeypatch):
    monkeypatch.setattr(hls, "HISTORICAL_DIR", tmp_path)
    assert hls.get_month_index(2026, 3) is None


def test_get_month_index_lee_el_json(mes_de_prueba):
    indice = hls.get_month_index(2026, 3)
    assert indice is not None
    assert indice["total_lines"] == 3


def test_entries_filtra_por_usuario(mes_de_prueba):
    resultado = hls.get_historical_entries(2026, 3, user="jperez")
    assert resultado["total_matched"] == 2
    assert all(e["user"] == "jperez" for e in resultado["entries"])


def test_entries_filtra_denegados(mes_de_prueba):
    resultado = hls.get_historical_entries(2026, 3, denied_only=True)
    assert resultado["total_matched"] == 1
    assert resultado["entries"][0]["status"] == 407


def test_entries_pagina_con_offset_y_limit(mes_de_prueba):
    pagina1 = hls.get_historical_entries(2026, 3, limit=1, offset=0)
    assert len(pagina1["entries"]) == 1
    assert pagina1["has_more"] is True

    pagina2 = hls.get_historical_entries(2026, 3, limit=1, offset=2)
    assert len(pagina2["entries"]) == 1
    assert pagina2["has_more"] is False


def test_entries_mes_inexistente_no_falla(tmp_path, monkeypatch):
    monkeypatch.setattr(hls, "HISTORICAL_DIR", tmp_path)
    resultado = hls.get_historical_entries(2020, 1)
    assert resultado == {"entries": [], "total_matched": 0, "has_more": False}


def test_iter_historical_lines_respeta_filtros(mes_de_prueba):
    entradas = list(hls.iter_historical_lines(2026, 3, {"user": "jperez"}))
    assert len(entradas) == 2


def test_no_importa_nada_de_log_service_mas_alla_de_parse_line():
    """La separación entre capa activa e histórica es el punto central del
    diseño: si este módulo empieza a importar caché, TTLs o el path del
    access.log activo, deja de estar aislado."""
    fuente = Path(hls.__file__).read_text(encoding="utf-8")
    assert "ACCESS_LOG_PATH" not in fuente
    assert "_CACHE_TTL" not in fuente
