"""Licencia AGPL, avisos de terceros, fuentes propias y destino configurable del formulario de Contacto."""
import pathlib
import re

import pytest

RAIZ = pathlib.Path(__file__).parents[2]


def _leer(rel):
    p = RAIZ / rel
    if not p.exists():
        pytest.skip(f"{rel} no accesible desde aqui")
    return p.read_text(encoding="utf-8")


def test_la_licencia_es_agpl_con_terminos_adicionales():
    t = _leer("LICENSE")
    assert "SPDX-License-Identifier: AGPL-3.0-or-later" in t
    assert "GNU AFFERO GENERAL PUBLIC LICENSE" in t
    assert "Version 3, 19 November 2007" in t
    assert "ADDITIONAL TERMS" in t and "section 7(b)" in t and "section 7(e)" in t
    assert "freeware" not in t.lower()


def test_ningun_documento_sigue_diciendo_freeware():
    for rel in ("README.md", "README.en.md", "README.pt.md", "CONTRIBUTING.md", "docs/estructura-proyecto.md",
                "frontend/src/pages/Contacto.tsx"):
        assert "freeware" not in _leer(rel).lower(), rel
    assert "license-Freeware" not in _leer("README.md")


def test_existen_los_documentos_legales():
    for rel in ("NOTICE", "TRADEMARK.md", "THIRD_PARTY_NOTICES.md", "SECURITY.md", "docs/privacidad.md"):
        assert len(_leer(rel)) > 200, rel
    assert "frontend/public/fonts/OFL-Figtree.txt" in _leer("THIRD_PARTY_NOTICES.md")


def test_los_avisos_de_terceros_cubren_todo_requirements():
    avisos = _leer("THIRD_PARTY_NOTICES.md").lower()
    for linea in _leer("backend/requirements.txt").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        nombre = re.split(r"[=<>~!\[ ;]", linea)[0].lower()
        assert nombre in avisos, f"{nombre} no figura en THIRD_PARTY_NOTICES.md"


def test_las_fuentes_estan_en_el_proyecto_y_no_se_piden_a_google():
    for f in ("figtree-latin", "figtree-latin-ext", "jetbrains-mono-latin", "jetbrains-mono-latin-ext"):
        assert (RAIZ / "frontend" / "public" / "fonts" / f"{f}.woff2").exists() or pytest.skip("fuentes no accesibles")
    css = _leer("frontend/public/fonts/fonts.css")
    assert css.count("@font-face") == 4 and "gstatic" not in css
    assert "/fonts/fonts.css" in _leer("frontend/index.html")
    for rel in ("frontend/index.html", "frontend/nginx.conf", "install-nativo.sh"):
        t = _leer(rel)
        assert "fonts.googleapis.com" not in t.replace("fonts.googleapis.com/gstatic.com", "") or rel == "x"
        assert "https://fonts.gstatic.com" not in t
    for rel in ("frontend/nginx.conf", "install-nativo.sh"):
        assert "font-src 'self';" in _leer(rel)


def test_no_queda_el_nombre_equivocado():
    for rel in ("squid/errors/es/ERR_SQUIDMANAGER_DENIED", "squid/errors/en/ERR_SQUIDMANAGER_DENIED",
                "squid/errors/pt/ERR_SQUIDMANAGER_DENIED", "squid/squid-logrotate.native"):
        assert "SquidManagerPro" not in _leer(rel), rel


def test_el_destino_del_contacto_es_configurable(monkeypatch):
    from app.config import settings
    from app.services import notification_service as ns

    enviados = []
    monkeypatch.setattr(ns, "_enviar_smtp", lambda cfg, dest, asunto, cuerpo, **kw: enviados.append(dest) or (True, "ok"))

    class Cfg:
        smtp_host = "smtp.ejemplo.com"

    monkeypatch.setattr(settings, "CONTACT_EMAIL", "soporte@mi-empresa.com")
    assert ns.send_contact_message(Cfg(), "a", "b") == (True, "ok")
    assert enviados == [["soporte@mi-empresa.com"]]

    monkeypatch.setattr(settings, "CONTACT_EMAIL", "")
    enviados.clear()
    ok, detalle = ns.send_contact_message(Cfg(), "a", "b")
    assert ok is False and "desactivado" in detalle and enviados == []


def test_el_correo_del_autor_es_solo_el_valor_por_defecto():
    from app.config import Settings
    assert Settings.model_fields["CONTACT_EMAIL"].default == "networkingenier@gmail.com"
    assert "DESTINO_SOPORTE" not in _leer("backend/app/services/notification_service.py")
    assert "CONTACT_EMAIL: ${CONTACT_EMAIL-" in _leer("docker-compose.yml")
    assert "CONTACT_EMAIL=${CONTACT_EMAIL}" in _leer("install-nativo.sh")
