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


def test_en_docker_el_estado_y_el_git_viven_en_el_proyecto_montado(monkeypatch, tmp_path):
    """En el contenedor el código corre en /app: el estado tiene que ir al proyecto del host
    (PROJECT_DIR) o el temporizador del host nunca lo ve."""
    from app.services import update_service as us
    monkeypatch.setattr(us.settings, "DEPLOY_MODE", "docker")
    monkeypatch.setenv("PROJECT_DIR", str(tmp_path))
    assert us._raiz_proyecto() == tmp_path
    assert us._ruta_estado() == tmp_path / ".update_state.json"
    monkeypatch.setattr(us.settings, "DEPLOY_MODE", "native")
    assert us._ruta_estado() == us.BACKEND_DIR / ".update_state.json"


def test_el_script_docker_lee_el_mismo_archivo_que_escribe_el_backend():
    import pathlib
    sh = (pathlib.Path(__file__).parents[2] / "docker-autoupdate-check.sh")
    if sh.exists():
        assert 'ESTADO="$PROJECT_DIR/.update_state.json"' in sh.read_text()


def test_las_actualizaciones_siguen_la_rama_activa_y_no_main_a_ciegas():
    import pathlib
    raiz = pathlib.Path(__file__).parents[2]
    docker = raiz / "docker-autoupdate-check.sh"
    if docker.exists():
        t = docker.read_text()
        assert 'branch --show-current' in t and 'BRANCH="$RAMA"' in t
    for f in ("upgrade-docker.sh", "upgrade-nativo.sh"):
        p = raiz / f
        if p.exists():
            assert 'branch --show-current' in p.read_text(), f
