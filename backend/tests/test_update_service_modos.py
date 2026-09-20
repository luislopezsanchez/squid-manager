"""Tests del cambio de alcance de update_service.py: comprobar/aprobar una
actualización ahora funcionan igual en nativo y en Docker -antes,
`aprobar_actualizacion`/`comprobar_actualizacion` rechazaban cualquier cosa
que no fuera DEPLOY_MODE=native. Lo único que sigue siendo exclusivo de
nativo es el "empujón" inmediato vía sudo (no hay sudo hacia el host desde
dentro de un contenedor Docker)."""

import pytest

from app.services import update_service as us


@pytest.fixture(autouse=True)
def _estado_en_tmp(tmp_path, monkeypatch):
    """Nunca tocar el .update_state.json real del checkout -cada test usa
    su propio archivo temporal."""
    monkeypatch.setattr(us, "ESTADO_PATH", tmp_path / ".update_state.json")


def test_comprobar_actualizacion_no_revienta_en_modo_docker(monkeypatch):
    monkeypatch.setattr(us.settings, "DEPLOY_MODE", "docker")
    monkeypatch.setattr(us, "_rama_actual", lambda: "main")
    monkeypatch.setattr(us, "_commit_actual", lambda: "")

    class _RespuestaFalsa:
        def raise_for_status(self):
            pass

        def json(self):
            return {"sha": "abc123"}

    class _ClienteFalso:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, **k):
            return _RespuestaFalsa()

    monkeypatch.setattr(us.httpx, "Client", lambda **k: _ClienteFalso())

    # Antes de este cambio, esto lanzaba UpdateServiceError en modo docker.
    estado = us.comprobar_actualizacion()
    assert estado["check"]["remote_commit"] == "abc123"


def test_aprobar_actualizacion_funciona_en_modo_docker(monkeypatch):
    monkeypatch.setattr(us.settings, "DEPLOY_MODE", "docker")
    disparado = []
    monkeypatch.setattr(us, "_disparar_verificacion_inmediata", lambda: disparado.append(True))

    # Antes de este cambio, esto lanzaba UpdateServiceError en modo docker.
    estado = us.aprobar_actualizacion("admin", None)
    assert estado["request"]["approved"] is True
    # Docker no tiene forma de disparar nada hacia el host: nunca se llama.
    assert disparado == []


def test_aprobar_actualizacion_dispara_el_empujon_solo_en_nativo(monkeypatch):
    monkeypatch.setattr(us.settings, "DEPLOY_MODE", "native")
    disparado = []
    monkeypatch.setattr(us, "_disparar_verificacion_inmediata", lambda: disparado.append(True))

    us.aprobar_actualizacion("admin", None)
    assert disparado == [True]
