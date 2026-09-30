"""Agregación por hora del access.log (app/services/rollup_service.py).

Solo la parte pura (sin base de datos): la agregación en memoria, los cubos
del histograma de latencia, los percentiles y el cálculo del rango de horas.
"""
import time

from app.services import rollup_service as ru
from app.services.metrics_service import _parse_log_line


def _linea(ts, ms, ip, accion, status, bytes_, metodo, url, user="-"):
    return f"{ts} {ms} {ip} {accion}/{status} {bytes_} {metodo} {url} {user} HIER_DIRECT/1.2.3.4 text/html"


T = 1_790_000_000.0  # una hora cualquiera; T // 3600 * 3600 es su balde


def _agregar(lineas):
    return ru.agregar_lineas(lineas, _parse_log_line)


def test_cuenta_peticiones_bytes_y_usuario_por_hora():
    ag = _agregar([
        _linea(T, 10, "10.0.0.1", "TCP_MISS", 200, 1000, "GET", "http://www.ejemplo.com/a", "ana"),
        _linea(T + 5, 20, "10.0.0.1", "TCP_HIT", 200, 500, "GET", "http://www.ejemplo.com/b", "ana"),
    ])
    h = int(T) // 3600 * 3600
    assert ag.total[h][:2] == [2, 1500]
    assert ag.user[(h, "ana")] == [2, 1500, 0]
    assert ag.domain[(h, "ejemplo.com")][:2] == [2, 1500]


def test_bloqueo_cuenta_como_denegado_en_usuario_y_dominio():
    ag = _agregar([_linea(T, 1, "10.0.0.2", "TCP_DENIED", 403, 300, "GET", "http://malo.com/", "bob")])
    h = int(T) // 3600 * 3600
    assert ag.total[h][2] == 1
    assert ag.user[(h, "bob")][2] == 1
    assert ag.domain[(h, "malo.com")][2:4] == [1, 300]


def test_error_http_no_incluye_codigos_de_politica():
    ag = _agregar([
        _linea(T, 1, "10.0.0.2", "TCP_MISS", 502, 0, "GET", "http://roto.com/"),
        _linea(T + 1, 1, "10.0.0.2", "TCP_DENIED", 407, 0, "GET", "http://roto.com/"),
    ])
    h = int(T) // 3600 * 3600
    assert ag.total[h][3] == 1          # solo el 502
    assert ag.domain[(h, "roto.com")][4] == 1


def test_connect_no_entra_en_la_latencia():
    ag = _agregar([
        _linea(T, 90000, "10.0.0.2", "TCP_TUNNEL", 200, 5000, "CONNECT", "sitio.com:443", "ana"),
        _linea(T + 1, 40, "10.0.0.2", "TCP_MISS", 200, 100, "GET", "http://sitio.com/", "ana"),
    ])
    h = int(T) // 3600 * 3600
    assert ag.total[h][7:9] == [40, 1]
    assert sum(ag.lat.values()) == 1


def test_trafico_interno_del_panel_se_ignora():
    ag = _agregar([_linea(T, 1, "127.0.0.1", "TCP_MISS", 200, 10, "GET", "http://x:3128/squid-internal-mgr/info")])
    assert ag.lineas == 0


def test_aciertos_y_fallos_de_cache():
    ag = _agregar([
        _linea(T, 1, "10.0.0.2", "TCP_HIT", 200, 700, "GET", "http://a.com/"),
        _linea(T, 1, "10.0.0.2", "TCP_MISS", 200, 300, "GET", "http://a.com/"),
        _linea(T, 1, "10.0.0.2", "TCP_TUNNEL", 200, 300, "CONNECT", "a.com:443"),
    ])
    h = int(T) // 3600 * 3600
    assert ag.total[h][4:7] == [1, 1, 700]


def test_misma_ip_con_varios_usuarios_se_registra():
    ag = _agregar([
        _linea(T, 1, "10.0.0.9", "TCP_MISS", 200, 1, "GET", "http://a.com/", "ana"),
        _linea(T, 1, "10.0.0.9", "TCP_MISS", 200, 1, "GET", "http://a.com/", "bob"),
    ])
    h = int(T) // 3600 * 3600
    assert ag.ipuser[(h, "10.0.0.9", "ana")] == 1 and ag.ipuser[(h, "10.0.0.9", "bob")] == 1


def test_cubos_de_latencia_son_monotonos():
    assert ru._bucket_lat(1) == 0
    assert ru._bucket_lat(5) == 0
    assert ru._bucket_lat(6) == 1
    assert ru._bucket_lat(10**9) == len(ru.LAT_EDGES)


def test_percentil_sobre_histograma():
    hist = [0] * (len(ru.LAT_EDGES) + 1)
    hist[ru._bucket_lat(40)] = 90     # 90 peticiones rápidas
    hist[ru._bucket_lat(2500)] = 10   # 10 lentas
    assert ru._percentil(hist, 0.50) == 50
    assert ru._percentil(hist, 0.95) == 3000
    assert ru._percentil([0] * len(hist), 0.5) is None


def test_ventana_corta_o_sin_ventana_no_usa_rollups():
    assert ru._rango(None, None, None) is None
    assert ru._rango(3600, None, None) is None
    h0, h1 = ru._rango(86400, None, None)
    assert h1 - h0 in (86400, 86400 + 3600) or h1 - h0 == 86400


def test_rango_libre_usa_las_horas_de_los_extremos():
    assert ru._rango(None, T, T + 7200) == (int(T) // 3600 * 3600, int(T + 7200) // 3600 * 3600)
