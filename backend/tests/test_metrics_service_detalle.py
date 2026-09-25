"""get_detalle(denied_only=...): el drill-down de un ranking de bloqueos
("Usuarios con más bloqueos", "Sitios bloqueados") tiene que mostrar las
peticiones bloqueadas, no las últimas N sin filtrar -bug real reportado en
vivo el 2026-09-25: al abrir el detalle de un usuario desde "Usuarios con
más bloqueos" se veían puras peticiones 200, porque get_detalle no tenía
forma de filtrar por denied.
"""

from app.services import metrics_service


def _entrada(user=None, domain="", status=200, denied=False, timestamp=0.0):
    return {
        "timestamp": timestamp, "elapsed_ms": 1, "client_ip": "10.0.0.1", "action": "TCP_MISS",
        "status": status, "bytes": 0, "method": "GET", "domain": domain,
        "user": user, "denied": denied, "interno": False,
    }


def test_sin_denied_only_trae_todo_igual_que_antes(monkeypatch):
    entradas = [
        _entrada(user="ana", status=200, denied=False, timestamp=1),
        _entrada(user="ana", status=407, denied=True, timestamp=2),
    ]
    monkeypatch.setattr(metrics_service, "_read_window", lambda seconds: entradas)

    resultado = metrics_service.get_detalle(user="ana")
    assert len(resultado) == 2


def test_denied_only_filtra_las_permitidas(monkeypatch):
    entradas = [
        _entrada(user="ana", status=200, denied=False, timestamp=1),
        _entrada(user="ana", status=200, denied=False, timestamp=2),
        _entrada(user="ana", status=407, denied=True, timestamp=3),
    ]
    monkeypatch.setattr(metrics_service, "_read_window", lambda seconds: entradas)

    resultado = metrics_service.get_detalle(user="ana", denied_only=True)
    assert len(resultado) == 1
    assert resultado[0]["status"] == 407
    assert resultado[0]["denied"] is True


def test_denied_only_respeta_el_limite_sobre_lo_ya_filtrado(monkeypatch):
    """El limite debe aplicarse DESPUES del filtro: pedir las ultimas 2
    bloqueadas de una lista con muchas permitidas en el medio no debe
    devolver de menos por haber cortado antes de filtrar."""
    entradas = [
        _entrada(user="ana", status=407, denied=True, timestamp=1),
        _entrada(user="ana", status=200, denied=False, timestamp=2),
        _entrada(user="ana", status=200, denied=False, timestamp=3),
        _entrada(user="ana", status=403, denied=True, timestamp=4),
        _entrada(user="ana", status=403, denied=True, timestamp=5),
    ]
    monkeypatch.setattr(metrics_service, "_read_window", lambda seconds: entradas)

    resultado = metrics_service.get_detalle(user="ana", denied_only=True, limit=2)
    assert len(resultado) == 2
    assert all(r["denied"] for r in resultado)


def test_denied_only_con_dominio(monkeypatch):
    """Mismo caso que 'Usuarios con más bloqueos', pero desde 'Sitios
    bloqueados': un dominio con algo de trafico permitido mezclado no debe
    mostrar ese trafico permitido en el detalle de bloqueos."""
    entradas = [
        _entrada(domain="ads.example.com", status=200, denied=False, timestamp=1),
        _entrada(domain="ads.example.com", status=403, denied=True, timestamp=2),
    ]
    monkeypatch.setattr(metrics_service, "_read_window", lambda seconds: entradas)

    resultado = metrics_service.get_detalle(domain="ads.example.com", denied_only=True)
    assert len(resultado) == 1
    assert resultado[0]["status"] == 403


# --- errors_only (drill-down desde "Errores HTTP" -> "Por dominio") --------

def test_errors_only_filtra_las_peticiones_ok(monkeypatch):
    entradas = [
        _entrada(domain="api.example.com", status=200, timestamp=1),
        _entrada(domain="api.example.com", status=200, timestamp=2),
        _entrada(domain="api.example.com", status=502, timestamp=3),
    ]
    monkeypatch.setattr(metrics_service, "_read_window", lambda seconds: entradas)

    resultado = metrics_service.get_detalle(domain="api.example.com", errors_only=True)
    assert len(resultado) == 1
    assert resultado[0]["status"] == 502


def test_errors_only_no_cuenta_codigos_de_politica_de_acceso(monkeypatch):
    """401/403/407 son bloqueos (ver denied_only, la sección de arriba), no
    "errores" en el sentido de get_http_errors/'Errores HTTP' -si el
    drill-down los mezclara, se solaparía con "Usuarios/Sitios bloqueados"
    y el número ya no coincidiría con el ranking que lo abrió."""
    entradas = [
        _entrada(domain="intranet.example.com", status=407, denied=True, timestamp=1),
        _entrada(domain="intranet.example.com", status=500, timestamp=2),
    ]
    monkeypatch.setattr(metrics_service, "_read_window", lambda seconds: entradas)

    resultado = metrics_service.get_detalle(domain="intranet.example.com", errors_only=True)
    assert len(resultado) == 1
    assert resultado[0]["status"] == 500
