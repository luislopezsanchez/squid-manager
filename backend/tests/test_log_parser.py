"""Tests del parser de logs de Squid."""

import pytest
from app.services.log_service import parse_line, filter_entries


# Líneas de ejemplo del access.log de Squid
SAMPLE_LINES = {
    "http_ok": "1787399760.284      18 192.168.145.1 TCP_MISS/200 527 GET http://detectportal.firefox.com/canonical.html llopez HIER_DIRECT/151.101.1.91 text/html",
    "https_denied": "1787399760.294      0 192.168.145.1 TCP_DENIED/200 0 CONNECT www.youtube.com:443 - HIER_NONE/- -",
    "denied_403": "1787399760.294      0 192.168.145.1 NONE_NONE/403 4008 POST https://www.youtube.com/youtubei/v1/log_event? - HIER_NONE/- text/html",
    "error_line": "1787399760.294      0 192.168.145.1 NONE_NONE/000 0 - error:transaction-end-before-headers - HIER_NONE/- -",
    "large_download": "1787404015.514    459 192.168.145.1 NONE_NONE/200 0 CONNECT cdimage.ubuntu.com:443 llopez HIER_DIRECT/185.125.190.37 -",
}


def test_parse_http_ok():
    entry = parse_line(SAMPLE_LINES["http_ok"])
    assert entry is not None
    assert entry["client_ip"] == "192.168.145.1"
    assert entry["status"] == 200
    assert entry["method"] == "GET"
    assert entry["domain"] == "detectportal.firefox.com"
    assert entry["user"] == "llopez"
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
    line = "1787399760.284      18 192.168.145.1 TCP_MISS/200 100 GET http://www.facebook.com/page testuser HIER_DIRECT/1.2.3.4 text/html"
    entry = parse_line(line)
    assert entry["domain"] == "facebook.com"


def test_filter_by_user():
    entries = [parse_line(l) for l in SAMPLE_LINES.values()]
    entries = [e for e in entries if e is not None]
    filtered = filter_entries(entries, user="llopez")
    assert all(e["user"] == "llopez" for e in filtered)
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
