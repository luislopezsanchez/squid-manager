"""Ajustes de la revisión: zona horaria, reporte diario, avisos de bloqueos, rar/7z."""
import shutil
import subprocess
import tarfile
import io
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from app.services import timezone_service as tzs
from app.services import quota_service


def _con_zona(monkeypatch, nombre):
    monkeypatch.setattr(tzs, "nombre_configurado", lambda: nombre)


def test_reinicio_diario_respeta_la_zona_elegida(monkeypatch):
    # 2026-09-30 15:00 UTC = 11:00 en Nueva York (EDT): la medianoche local es 04:00 UTC del 1/10.
    _con_zona(monkeypatch, "America/New_York")
    r = quota_service.proximo_reinicio(datetime(2026, 9, 30, 15, 0), "daily")
    assert r == datetime(2026, 10, 1, 4, 0)


def test_reinicio_semanal_es_lunes_a_medianoche_local(monkeypatch):
    _con_zona(monkeypatch, "America/Havana")
    r = quota_service.proximo_reinicio(datetime(2026, 9, 30, 15, 0), "weekly")  # miércoles
    local = r.replace(tzinfo=__import__("datetime").timezone.utc).astimezone(ZoneInfo("America/Havana"))
    assert (local.weekday(), local.hour, local.minute) == (0, 0, 0)


def test_reinicio_mensual_es_dia_1(monkeypatch):
    _con_zona(monkeypatch, "UTC")
    assert quota_service.proximo_reinicio(datetime(2026, 9, 30, 15, 0), "monthly") == datetime(2026, 10, 1, 0, 0)
    assert quota_service.proximo_reinicio(datetime(2026, 12, 31, 23, 0), "monthly") == datetime(2027, 1, 1, 0, 0)


def test_inicio_dia_usa_la_zona(monkeypatch):
    _con_zona(monkeypatch, "Asia/Tokyo")  # UTC+9
    ts = datetime(2026, 9, 30, 20, 0, tzinfo=ZoneInfo("UTC")).timestamp()  # ya es 1/10 05:00 en Tokio
    d = datetime.fromtimestamp(tzs.inicio_dia(ts), ZoneInfo("Asia/Tokyo"))
    assert (d.month, d.day, d.hour) == (10, 1, 0)


def test_zona_invalida():
    assert tzs.es_valida("America/Havana")
    assert not tzs.es_valida("Mars/Olympus")


# --- reporte diario ---------------------------------------------------------

def _datos():
    return {
        "totales": {"usuarios": {"count": 5, "bytes": 5 * 1024 ** 3, "requests": 900},
                    "dominios": {"count": 40, "requests": 900, "bytes": 1},
                    "dominios_bloqueados": {"count": 2, "requests": 12}, "usuarios_bloqueados_requests": 12},
        "peticiones": 900, "cache": {"cache_hit_ratio": 41.5},
        "top_usuarios": [{"user": "ana", "bytes": 2 * 1024 ** 3, "requests": 500}],
        "top_sitios": [{"domain": "example.com", "bytes": 1024, "requests": 300}],
        "top_bloqueados": [{"domain": "casino.test", "requests": 9}],
        "top_bloqueos_usuarios": [("luis", 9)],
        "cuotas": [{"nombre": "luis", "tipo": "usuario", "quota_bytes": 1024 ** 3, "quota_bytes_used": 1024 ** 3,
                    "quota_action": "cut", "quota_action_applied": True}],
        "alertas": [{"asunto": "SquidManager: pico de tráfico", "mensaje": "La ventana reciente transfirió mucho."}],
    }


@pytest.mark.parametrize("idioma,palabra", [("es", "Reporte diario"), ("en", "Daily browsing report"), ("pt", "Relatório diário")])
def test_reporte_diario_incluye_todas_las_secciones(idioma, palabra):
    from app.services.daily_report_service import construir
    asunto, html, texto = construir(_datos(), idioma, datetime(2026, 9, 30, 23, 55))
    assert palabra in html and palabra in asunto
    for esperado in ("ana", "example.com", "casino.test", "luis", "5.0 GB", "900"):
        assert esperado in html
        assert esperado in texto
    assert "<table" in html


def test_reporte_diario_escapa_html():
    from app.services.daily_report_service import construir
    d = _datos()
    d["top_usuarios"][0]["user"] = "<script>alert(1)</script>"
    _, html, _ = construir(d, "es")
    assert "<script>" not in html and "&lt;script&gt;" in html


def test_reporte_requiere_smtp_y_admin_con_email(monkeypatch):
    from app.services import daily_report_service as d

    class Q:
        def __init__(self, filas): self.filas = filas
        def first(self): return self.filas[0] if self.filas else None
        def filter(self, *_): return self
        def all(self): return self.filas

    class DB:
        def __init__(self, smtp, admins): self.smtp, self.admins = smtp, admins
        def query(self, modelo):
            return Q([self.smtp] if self.smtp else []) if modelo.__name__ == "SmtpConfig" else Q(self.admins)

    smtp = SimpleNamespace(smtp_host="mail.x", smtp_from="a@x", smtp_user=None)
    admin = SimpleNamespace(email="admin@x.com")
    assert d.condiciones(DB(smtp, [admin]))["ok"]
    assert not d.condiciones(DB(None, [admin]))["ok"]
    assert not d.condiciones(DB(smtp, [SimpleNamespace(email=None)]))["ok"]
    assert d.condiciones(DB(smtp, [SimpleNamespace(email="sin-arroba")]))["admin_con_email"] is False


# --- avisos de bloqueos -----------------------------------------------------

def test_aviso_de_bloqueos_usa_umbral_y_lista_sitios():
    from app.services.anomaly_service import _detectar_bloqueos_en_racha
    e = [{"user": "luis", "denied": True, "domain": "casino.test"}] * 6 + [{"user": "luis", "denied": True, "domain": "bet.test"}] * 2
    assert _detectar_bloqueos_en_racha(e, umbral=9) == []
    (clave, asunto, msg), = _detectar_bloqueos_en_racha(e, umbral=8)
    assert clave == "bloqueos:luis" and "luis" in asunto
    assert "casino.test (6)" in msg and "bet.test (2)" in msg


def test_eventos_nuevos_tienen_su_propio_interruptor():
    from app.services.notification_service import EVENT_CONFIG_MAP
    assert EVENT_CONFIG_MAP["quota_reached"] == "notify_on_quota_reached"
    assert EVENT_CONFIG_MAP["blocked_access"] == "notify_on_blocked_access"


# --- rar / 7z / xz vía bsdtar ----------------------------------------------

@pytest.mark.skipif(not shutil.which("bsdtar"), reason="bsdtar no instalado")
def test_extrae_con_bsdtar_y_rechaza_basura():
    from fastapi import HTTPException
    from app.routes.backup import _extraer_con_bsdtar
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:xz") as t:
        datos = b"http_port 3128\n"
        info = tarfile.TarInfo("squid/squid.conf"); info.size = len(datos)
        t.addfile(info, io.BytesIO(datos))
        enlace = tarfile.TarInfo("squid/enlace"); enlace.type = tarfile.SYMTYPE; enlace.linkname = "/etc/passwd"
        t.addfile(enlace)
    salida = _extraer_con_bsdtar("x.tar.xz", buf.getvalue())
    assert salida == [("squid/squid.conf", b"http_port 3128\n")]  # el enlace simbólico se ignora
    with pytest.raises(HTTPException) as e:
        _extraer_con_bsdtar("mal.rar", b"basura")
    assert e.value.status_code == 400


# --- correos de alerta con formato ------------------------------------------

@pytest.mark.parametrize("evento", ["apply", "user_change", "acl_change", "rule_change", "security_alert",
                                    "node_down", "quota_reached", "blocked_access", "test", None])
@pytest.mark.parametrize("idioma", ["es", "en", "pt"])
def test_todo_aviso_sale_con_formato(evento, idioma):
    from app.services.email_templates import construir_correo
    html, texto = construir_correo(evento, "SquidManager: algo pasó", "El usuario <ana> hizo algo.", idioma)
    assert "<table" in html and "algo pasó".capitalize() in html or "Algo pasó" in html
    assert "&lt;ana&gt;" in html and "<ana>" not in html   # se escapa
    assert "<ana>" in texto                                # el texto plano no se escapa


def test_el_aviso_usa_el_idioma_pedido():
    from app.services.email_templates import construir_correo
    en, _ = construir_correo("quota_reached", "x", "y", "en")
    pt, _ = construir_correo("quota_reached", "x", "y", "pt")
    assert "What it means" in en and "O que significa" in pt


def test_toast_container_es_estable():
    import pathlib
    src = (pathlib.Path(__file__).parents[2] / "frontend/src/components/Toast.tsx")
    if src.exists():
        assert "useRef(() =>" in src.read_text(), "ToastContainer no debe redefinirse en cada render"
