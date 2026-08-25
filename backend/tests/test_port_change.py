"""Pruebas del cambio de puerto del proxy.

El puerto vive en un único sitio: PROXY_PORT del .env, que es lo que Docker
publica. Squid escucha siempre en un puerto interno fijo. Estas pruebas cubren
la función que mantiene ese fichero al día, que es donde estaba la avería: si
el .env conserva el puerto viejo, el siguiente `docker compose up -d` republica
un puerto donde Squid no escucha y el proxy queda inalcanzable.
"""

import os

import pytest

from app.services import squid_service
from app.services.config_generator import INTERNAL_SQUID_PORT


ENV_COMPLETO = """\
# Comentario inicial
DB_NAME=squidmanager
DB_USER=squid
DB_PASS=secreto-de-la-base
SECRET_KEY=clave-de-firma-muy-larga-que-no-se-debe-perder

# --- Puertos ---
WEB_PORT=3000
PROXY_PORT=3128
"""


@pytest.fixture
def proyecto(tmp_path, monkeypatch):
    """Simula el directorio del proyecto montado en el backend."""
    (tmp_path / "docker-compose.yml").write_text("services: {}\n")
    (tmp_path / ".env").write_text(ENV_COMPLETO)
    monkeypatch.setenv("PROJECT_DIR", str(tmp_path))
    return tmp_path


def test_actualiza_el_puerto(proyecto):
    ok, _ = squid_service.sync_env_port("9128")
    assert ok
    assert "PROXY_PORT=9128" in (proyecto / ".env").read_text()


def test_no_pierde_los_secretos(proyecto):
    """Lo más importante: el .env lleva la contraseña de la BD y la clave JWT."""
    squid_service.sync_env_port("9128")
    contenido = (proyecto / ".env").read_text()
    assert "DB_PASS=secreto-de-la-base" in contenido
    assert "SECRET_KEY=clave-de-firma-muy-larga-que-no-se-debe-perder" in contenido
    assert "WEB_PORT=3000" in contenido
    assert "# Comentario inicial" in contenido


def test_no_deja_el_puerto_viejo(proyecto):
    """Justo el fallo original: quedaban las dos líneas y ganaba la vieja."""
    squid_service.sync_env_port("9128")
    contenido = (proyecto / ".env").read_text()
    assert "PROXY_PORT=3128" not in contenido
    assert contenido.count("PROXY_PORT=") == 1


def test_anade_la_variable_si_falta(tmp_path, monkeypatch):
    (tmp_path / "docker-compose.yml").write_text("services: {}\n")
    (tmp_path / ".env").write_text("DB_USER=squid\n")
    monkeypatch.setenv("PROJECT_DIR", str(tmp_path))

    ok, _ = squid_service.sync_env_port("9128")
    assert ok
    assert "PROXY_PORT=9128" in (tmp_path / ".env").read_text()


def test_respeta_las_lineas_comentadas(tmp_path, monkeypatch):
    """Una línea comentada no es una asignación: no debe tocarse."""
    (tmp_path / "docker-compose.yml").write_text("services: {}\n")
    (tmp_path / ".env").write_text("# PROXY_PORT=1111 (valor antiguo)\nPROXY_PORT=3128\n")
    monkeypatch.setenv("PROJECT_DIR", str(tmp_path))

    squid_service.sync_env_port("9128")
    contenido = (tmp_path / ".env").read_text()
    assert "# PROXY_PORT=1111 (valor antiguo)" in contenido
    assert "PROXY_PORT=9128" in contenido


def test_es_idempotente(proyecto):
    squid_service.sync_env_port("9128")
    primero = (proyecto / ".env").read_text()
    ok, mensaje = squid_service.sync_env_port("9128")
    assert ok
    assert (proyecto / ".env").read_text() == primero
    assert "ya estaba" in mensaje.lower()


def test_conserva_los_permisos(proyecto):
    """El .env lleva secretos: no puede acabar siendo legible por todos."""
    env = proyecto / ".env"
    os.chmod(env, 0o600)
    squid_service.sync_env_port("9128")
    assert (env.stat().st_mode & 0o777) == 0o600


def test_falla_si_el_proyecto_no_esta_montado(monkeypatch):
    """Sin PROJECT_DIR no se inventa nada: se avisa del problema."""
    monkeypatch.delenv("PROJECT_DIR", raising=False)
    ok, mensaje = squid_service.sync_env_port("9128")
    assert not ok
    assert "PROJECT_DIR" in mensaje


def test_el_puerto_de_la_bd_no_llega_al_squid_conf():
    """La prueba que define este diseño.

    El puerto elegido en el panel es el que Docker publica, no el que Squid
    escucha. Si este test falla, el puerto ha vuelto a vivir en dos sitios y la
    avería original puede repetirse: Docker publicando un puerto donde Squid no
    escucha, sin que nada lo avise.
    """
    from test_config_generator import FakeDB, FakeSetting
    from app.services.config_generator import generate_squid_config

    db = FakeDB(settings=[FakeSetting("http_port", "9999", "network")])
    config = generate_squid_config(db)

    assert f"http_port {INTERNAL_SQUID_PORT}" in config
    assert "http_port 9999" not in config
