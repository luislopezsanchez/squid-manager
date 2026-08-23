"""Tests del parser de logs de Squid."""

import pytest
from app.services.log_service import parse_line, filter_entries


# Líneas de ejemplo del access.log de Squid
SAMPLE_LINES = {
    "http_ok": "1787399760.284      18 10.10.10.20 TCP_MISS/200 527 GET http://detectportal.firefox.com/canonical.html usuario1 HIER_DIRECT/151.101.1.91 text/html",
    "https_denied": "1787399760.294      0 10.10.10.20 TCP_DENIED/200 0 CONNECT www.youtube.com:443 - HIER_NONE/- -",
    "denied_403": "1787399760.294      0 10.10.10.20 NONE_NONE/403 4008 POST https://www.youtube.com/youtubei/v1/log_event? - HIER_NONE/- text/html",
    "error_line": "1787399760.294      0 10.10.10.20 NONE_NONE/000 0 - error:transaction-end-before-headers - HIER_NONE/- -",
    "large_download": "1787404015.514    459 10.10.10.20 NONE_NONE/200 0 CONNECT cdimage.ubuntu.com:443 usuario1 HIER_DIRECT/185.125.190.37 -",
}


def test_parse_http_ok():
    entry = parse_line(SAMPLE_LINES["http_ok"])
    assert entry is not None
    assert entry["client_ip"] == "10.10.10.20"
    assert entry["status"] == 200
    assert entry["method"] == "GET"
    assert entry["domain"] == "detectportal.firefox.com"
    assert entry["user"] == "usuario1"
    assert entry["bytes"] == 527
    assert entry["denied"] is False


def test_parse_https_denied():
    entry = parse_line(SAMPLE_LINES["https_denied"])
    assert entry is not None
    assert entry["action"] == "TCP_DENIED"
    assert entry["denied"] is True
    # El CONNECT bloqueado se registra con status 200 pero action DENIED
    assert entry["status"] == 200
    assert entry["domain"] == "youtube.com"


def test_parse_denied_403():
    entry = parse_line(SAMPLE_LINES["denied_403"])
    assert entry is not None
    assert entry["status"] == 403
    assert entry["denied"] is True
    assert entry["domain"] == "youtube.com"


def test_parse_error_line():
    entry = parse_line(SAMPLE_LINES["error_line"])
    assert entry is not None
    assert entry["domain"] == "error:transaction-end-before-headers"
    assert entry["user"] == "-"


def test_parse_invalid_line():
    assert parse_line("esto no es un log válido") is None
    assert parse_line("") is None


def test_domain_www_stripped():
    line = "1787399760.284      18 10.10.10.20 TCP_MISS/200 100 GET http://www.facebook.com/page testuser HIER_DIRECT/1.2.3.4 text/html"
    entry = parse_line(line)
    assert entry["domain"] == "facebook.com"


def test_filter_by_user():
    entries = [parse_line(l) for l in SAMPLE_LINES.values()]
    entries = [e for e in entries if e is not None]
    filtered = filter_entries(entries, user="usuario1")
    assert all(e["user"] == "usuario1" for e in filtered)
    assert len(filtered) == 2


def test_filter_denied_only():
    entries = [parse_line(l) for l in SAMPLE_LINES.values()]
    entries = [e for e in entries if e is not None]
    filtered = filter_entries(entries, denied_only=True)
    assert all(e["denied"] for e in filtered)
    assert len(filtered) == 2  # https_denied + denied_403


def test_filter_by_domain():
    entries = [parse_line(l) for l in SAMPLE_LINES.values()]
    entries = [e for e in entries if e is not None]
    filtered = filter_entries(entries, domain="youtube")
    assert all("youtube" in e["domain"] for e in filtered)
    assert len(filtered) == 2


def test_auth_required_cuenta_como_denegado():
    """407 es 'hacen falta credenciales': también es acceso denegado."""
    line = "1787399760.284 0 10.10.10.20 TCP_DENIED/407 4003 GET http://example.com/ - HIER_NONE/- text/html"
    entry = parse_line(line)
    assert entry["status"] == 407
    assert entry["denied"] is True


def test_lectura_inversa(tmp_path):
    """El lector devuelve las líneas de la más reciente a la más antigua."""
    from app.services.log_service import iter_lines_reverse

    fichero = tmp_path / "access.log"
    fichero.write_text("\n".join(f"linea{i}" for i in range(1, 501)) + "\n")

    leidas = list(iter_lines_reverse(str(fichero)))
    assert len(leidas) == 500
    assert leidas[0] == "linea500"
    assert leidas[-1] == "linea1"


def test_lectura_inversa_respeta_el_tope(tmp_path):
    """Con un tope, solo se examinan las últimas N líneas."""
    from app.services.log_service import iter_lines_reverse

    fichero = tmp_path / "access.log"
    fichero.write_text("\n".join(f"linea{i}" for i in range(1, 10001)) + "\n")

    leidas = list(iter_lines_reverse(str(fichero), max_lines=10))
    assert len(leidas) == 10
    assert leidas[0] == "linea10000"


def test_lectura_inversa_fichero_inexistente():
    from app.services.log_service import iter_lines_reverse

    assert list(iter_lines_reverse("/no/existe/access.log")) == []
