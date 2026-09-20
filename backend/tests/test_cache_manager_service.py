"""Tests del parser de mgr:info/mgr:storedir/mgr:client_list
(cache_manager_service.py).

Las fixtures son texto REAL, capturado en vivo contra un Squid corriendo
(172.30.36.33, 2026-09-10; client_list contra 172.30.36.52, 2026-09-19) -no
inventado a mano-, para que el parser se pruebe contra el formato de
verdad que Squid produce.
"""

import pytest
from unittest.mock import patch

from app.services.cache_manager_service import (
    CacheManagerError,
    REPORTES_PERMITIDOS,
    _parsear_info,
    _parsear_storedir,
    _parsear_client_list,
    _pedir_reporte,
    obtener_estadisticas_cache,
    obtener_conexiones_activas,
)

INFO_REAL = """Squid Object Cache: Version 6.14
Build Info: Ubuntu linux
Service Name: squid
Start Time:\tWed, 09 Sep 2026 19:22:07 GMT
Current Time:\tWed, 09 Sep 2026 20:46:55 GMT
Connection information for squid:
\tNumber of clients accessing cache:\t1
\tNumber of HTTP requests received:\t3
\tNumber of ICP messages received:\t0
\tNumber of ICP messages sent:\t0
\tNumber of queued ICP replies:\t0
\tNumber of HTCP messages received:\t0
\tNumber of HTCP messages sent:\t0
\tRequest failure ratio:\t 0.00
\tAverage HTTP requests per minute since start:\t0.0
\tAverage ICP messages per minute since start:\t0.0
\tSelect loop called: 12230 times, 416.025 ms avg
Cache information for squid:
\tHits as % of all requests:\t5min: 0.0%, 60min: 0.0%
\tHits as % of bytes sent:\t5min: -0.0%, 60min: 100.0%
\tMemory hits as % of hit requests:\t5min: 0.0%, 60min: 0.0%
\tDisk hits as % of hit requests:\t5min: 0.0%, 60min: 0.0%
\tStorage Swap size:\t8 KB
\tStorage Swap capacity:\t 0.0% used, 100.0% free
\tStorage Mem size:\t216 KB
\tStorage Mem capacity:\t 0.0% used, 100.0% free
\tMean Object Size:\t4.00 KB
\tRequests given to unlinkd:\t0
Median Service Times (seconds)  5 min    60 min:
\tHTTP Requests (All):   0.00000  0.00000
Resource usage for squid:
\tUP Time:\t5087.986 seconds
\tCPU Time:\t0.484 seconds
\tCPU Usage:\t0.01%
"""

STOREDIR_REAL = """Store Directory Statistics:
Store Entries          : 55
Maximum Swap Size      : 2097152 KB
Current Store Swap Size: 8.00 KB
Current Capacity       : 0.00% used, 100.00% free

Store Directory #0 (ufs): /var/spool/squid
FS Block Size 4096 Bytes
"""


def test_parsear_info_saca_los_valores_reales():
    datos = _parsear_info(INFO_REAL)
    assert datos["version"] == "6.14"
    assert datos["uptime_segundos"] == 5087.986
    assert datos["hits_peticiones_5min"] == 0.0
    assert datos["hits_peticiones_60min"] == 0.0
    assert datos["hits_bytes_5min"] == -0.0
    assert datos["hits_bytes_60min"] == 100.0
    assert datos["swap_size_kb"] == 8.0
    assert datos["swap_capacidad_pct"] == 0.0
    assert datos["mem_size_kb"] == 216.0
    assert datos["objeto_medio_kb"] == 4.00
    assert datos["ratio_fallos"] == 0.00
    assert datos["clientes_activos"] == 1
    assert datos["peticiones_recibidas"] == 3


def test_parsear_info_con_texto_vacio_no_revienta():
    """Squid caído/reporte distinto: valores None, no una excepción."""
    datos = _parsear_info("")
    assert datos["version"] is None
    assert datos["uptime_segundos"] is None


def test_parsear_storedir_saca_los_valores_reales():
    datos = _parsear_storedir(STOREDIR_REAL)
    assert datos["entradas"] == 55
    assert datos["tamano_maximo_kb"] == 2097152.0
    assert datos["tamano_actual_kb"] == 8.00
    assert datos["capacidad_pct"] == 0.00


def test_pedir_reporte_rechaza_nombres_no_permitidos():
    """El frontend nunca deberia poder pedir un reporte arbitrario de

    Squid (mgr:config, por ejemplo, puede volcar datos que no
    corresponde exponer por el panel)."""
    with pytest.raises(CacheManagerError, match="no permitido"):
        _pedir_reporte(db=None, reporte="config")


def test_reportes_permitidos_es_la_lista_corta_esperada():
    assert set(REPORTES_PERMITIDOS) == {"info", "storedir", "client_list"}


CLIENT_LIST_REAL = """Cache Clients:
Address: 127.0.0.1
Name:    localhost
Currently established connections: 1
    ICP  Requests 0
    HTTP Requests 0

Address: 172.30.36.1
Currently established connections: 2
    ICP  Requests 0
    HTTP Requests 126
        NONE_NONE                110  87%
        TCP_DENIED                16  13%

TOTALS
ICP : 0 Queries, 0 Hits (  0%)
HTTP: 126 Requests, 0 Hits (  0%)
"""


def test_parsear_client_list_saca_los_dos_clientes_reales():
    clientes = _parsear_client_list(CLIENT_LIST_REAL)
    assert len(clientes) == 2
    assert clientes[0]["address"] == "127.0.0.1"
    assert clientes[0]["name"] == "localhost"
    assert clientes[0]["conexiones_activas"] == 1
    assert clientes[0]["http_requests"] == 0
    assert clientes[1]["address"] == "172.30.36.1"
    assert clientes[1]["name"] is None
    assert clientes[1]["conexiones_activas"] == 2
    assert clientes[1]["http_requests"] == 126


def test_parsear_client_list_con_texto_vacio_devuelve_lista_vacia():
    assert _parsear_client_list("") == []


def test_obtener_conexiones_activas_suma_el_total(monkeypatch):
    monkeypatch.setattr(
        "app.services.cache_manager_service._pedir_reporte",
        lambda db, reporte: CLIENT_LIST_REAL,
    )
    resultado = obtener_conexiones_activas(db=None)
    assert resultado["total_conexiones"] == 3
    assert len(resultado["clientes"]) == 2
    assert "error" not in resultado


def test_obtener_conexiones_activas_si_falla_devuelve_vacio_no_lanza(monkeypatch):
    def _falla(db, reporte):
        raise CacheManagerError("Squid no responde")

    monkeypatch.setattr("app.services.cache_manager_service._pedir_reporte", _falla)
    resultado = obtener_conexiones_activas(db=None)
    assert resultado["clientes"] == []
    assert resultado["total_conexiones"] == 0
    assert "Squid no responde" in resultado["error"]


def test_obtener_estadisticas_un_reporte_falla_no_tumba_al_otro():
    """Si mgr:storedir falla pero mgr:info funciona (o viceversa), se

    devuelve lo que si se pudo, no un error total -Squid vivo con un
    reporte puntual fallando es mas probable que los dos a la vez."""
    def _pedir_falso(db, reporte):
        if reporte == "info":
            return INFO_REAL
        raise CacheManagerError("boom")

    with patch("app.services.cache_manager_service._pedir_reporte", side_effect=_pedir_falso):
        resultado = obtener_estadisticas_cache(db=None)

    assert resultado["info"] is not None
    assert resultado["info"]["version"] == "6.14"
    assert resultado["storedir"] is None
    assert len(resultado["errores"]) == 1
    assert "storedir" in resultado["errores"][0]
