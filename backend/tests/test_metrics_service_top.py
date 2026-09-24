"""Tests de get_top_domains(sort_by=...) y get_ips_compartidas(), agregados
al implementar la propuesta de análisis de datos del 2026-09-24 (comparación
con SquidStats). No existía ningún test de metrics_service.py hasta ahora
-se mockea _read_window() directo, sin depender de un access.log real."""

from app.services import metrics_service


def _entrada(domain="", user=None, bytes=0, client_ip="10.0.0.1", denied=False):
    return {
        "timestamp": 0.0, "elapsed_ms": 1, "client_ip": client_ip, "action": "TCP_MISS",
        "status": 200, "bytes": bytes, "method": "GET", "domain": domain,
        "user": user, "denied": denied, "interno": False,
    }


# --- get_top_domains(sort_by=...) -------------------------------------------

def test_top_domains_por_peticiones_es_el_default(monkeypatch):
    entradas = [
        _entrada(domain="poco-bytes-muchas-peticiones.com", bytes=10),
        _entrada(domain="poco-bytes-muchas-peticiones.com", bytes=10),
        _entrada(domain="poco-bytes-muchas-peticiones.com", bytes=10),
        _entrada(domain="pocas-peticiones-muchos-bytes.com", bytes=1_000_000),
    ]
    monkeypatch.setattr(metrics_service, "_read_window", lambda seconds: entradas)

    resultado = metrics_service.get_top_domains(limit=10)
    assert resultado[0]["domain"] == "poco-bytes-muchas-peticiones.com"
    assert resultado[0]["requests"] == 3


def test_top_domains_por_bytes_reordena(monkeypatch):
    """Bug real que motivó el cambio: un dominio con pocas peticiones pero
    una descarga grande quedaba invisible ordenando solo por peticiones,
    aunque el backend ya calculaba domain_bytes -no se usaba para ordenar."""
    entradas = [
        _entrada(domain="poco-bytes-muchas-peticiones.com", bytes=10),
        _entrada(domain="poco-bytes-muchas-peticiones.com", bytes=10),
        _entrada(domain="poco-bytes-muchas-peticiones.com", bytes=10),
        _entrada(domain="pocas-peticiones-muchos-bytes.com", bytes=1_000_000),
    ]
    monkeypatch.setattr(metrics_service, "_read_window", lambda seconds: entradas)

    resultado = metrics_service.get_top_domains(limit=10, sort_by="bytes")
    assert resultado[0]["domain"] == "pocas-peticiones-muchos-bytes.com"
    assert resultado[0]["bytes"] == 1_000_000
    # El campo requests sigue siendo el real, no se pierde al ordenar por bytes.
    assert resultado[0]["requests"] == 1


def test_top_domains_sin_datos_no_revienta(monkeypatch):
    monkeypatch.setattr(metrics_service, "_read_window", lambda seconds: [])
    assert metrics_service.get_top_domains(limit=10, sort_by="bytes") == []


# --- get_ips_compartidas() ---------------------------------------------------

def test_ip_con_un_solo_usuario_no_aparece(monkeypatch):
    entradas = [_entrada(user="ana", client_ip="10.0.0.5") for _ in range(5)]
    monkeypatch.setattr(metrics_service, "_read_window", lambda seconds: entradas)
    assert metrics_service.get_ips_compartidas() == []


def test_ip_con_dos_usuarios_distintos_aparece(monkeypatch):
    entradas = [
        _entrada(user="ana", client_ip="10.0.0.5"),
        _entrada(user="beto", client_ip="10.0.0.5"),
        _entrada(user="ana", client_ip="10.0.0.5"),
    ]
    monkeypatch.setattr(metrics_service, "_read_window", lambda seconds: entradas)

    resultado = metrics_service.get_ips_compartidas()
    assert len(resultado) == 1
    assert resultado[0]["ip"] == "10.0.0.5"
    assert resultado[0]["usuarios"] == ["ana", "beto"]
    assert resultado[0]["requests"] == 3


def test_trafico_sin_usuario_no_cuenta_como_señal(monkeypatch):
    """Ruido de fondo del navegador (sin usuario) es la norma, no una señal
    de nada -no debe hacer que una IP aparezca como "compartida"."""
    entradas = [
        _entrada(user=None, client_ip="10.0.0.9"),
        _entrada(user=None, client_ip="10.0.0.9"),
    ]
    monkeypatch.setattr(metrics_service, "_read_window", lambda seconds: entradas)
    assert metrics_service.get_ips_compartidas() == []


def test_orden_por_cantidad_de_usuarios_distintos(monkeypatch):
    entradas = (
        [_entrada(user="ana", client_ip="10.0.0.1"), _entrada(user="beto", client_ip="10.0.0.1")]
        + [_entrada(user=u, client_ip="10.0.0.2") for u in ("carla", "dani", "eva")]
    )
    monkeypatch.setattr(metrics_service, "_read_window", lambda seconds: entradas)

    resultado = metrics_service.get_ips_compartidas()
    assert [r["ip"] for r in resultado] == ["10.0.0.2", "10.0.0.1"]


def test_limit_se_respeta(monkeypatch):
    entradas = []
    for i in range(5):
        ip = f"10.0.0.{i}"
        entradas += [_entrada(user="a", client_ip=ip), _entrada(user="b", client_ip=ip)]
    monkeypatch.setattr(metrics_service, "_read_window", lambda seconds: entradas)

    assert len(metrics_service.get_ips_compartidas(limit=2)) == 2
