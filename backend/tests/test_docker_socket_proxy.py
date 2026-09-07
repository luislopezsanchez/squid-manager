"""Acceso a Docker acotado por docker-socket-proxy + backend sin privilegios.

No levanta contenedores de verdad -eso se prueba en vivo contra un despliegue
real-, pero comprueba las propiedades de seguridad que no deben perderse
silenciosamente en un cambio futuro: el backend no debe volver a montar el
socket real directamente, tiene que hablar por DOCKER_HOST con el proxy, y el
proxy tiene que dejar cerrado lo que no hace falta (build, swarm, secrets,
plugins).
"""

from pathlib import Path

import pytest
import yaml


def _raiz_del_proyecto() -> Path | None:
    for base in Path(__file__).resolve().parents:
        if (base / "docker-compose.yml").is_file():
            return base
    return None


@pytest.fixture
def compose() -> dict:
    raiz = _raiz_del_proyecto()
    if raiz is None:
        pytest.skip("el proyecto no esta accesible desde aqui")
    with open(raiz / "docker-compose.yml", encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture
def dockerfile_backend() -> str:
    raiz = _raiz_del_proyecto()
    if raiz is None:
        pytest.skip("el proyecto no esta accesible desde aqui")
    return (raiz / "backend" / "Dockerfile").read_text(encoding="utf-8")


@pytest.fixture
def entrypoint_backend() -> str:
    raiz = _raiz_del_proyecto()
    if raiz is None:
        pytest.skip("el proyecto no esta accesible desde aqui")
    return (raiz / "backend" / "entrypoint.sh").read_text(encoding="utf-8")


# --- El backend ya no toca el socket real directamente ----------------------

def test_backend_no_monta_el_socket_directo(compose):
    """Si esto vuelve a aparecer, se perdió la protección entera: el backend
    tendría acceso root-equivalente sin pasar por ningún filtro."""
    volumes = compose["services"]["backend"].get("volumes", [])
    assert not any("docker.sock" in v for v in volumes)


def test_backend_habla_con_el_proxy_por_docker_host(compose):
    env = compose["services"]["backend"]["environment"]
    assert env.get("DOCKER_HOST") == "tcp://docker-socket-proxy:2375"


def test_backend_depende_del_proxy(compose):
    depends = compose["services"]["backend"].get("depends_on", {})
    assert "docker-socket-proxy" in depends


# --- El proxy monta el socket real, cerrado a lo mínimo necesario -----------

def test_proxy_monta_el_socket_real_de_solo_lectura(compose):
    volumes = compose["services"]["docker-socket-proxy"].get("volumes", [])
    assert any("docker.sock:/var/run/docker.sock:ro" in v for v in volumes)


def test_proxy_no_expone_puertos_hacia_fuera(compose):
    """Solo el backend debe poder hablarle, por la red interna."""
    assert "ports" not in compose["services"]["docker-socket-proxy"]


@pytest.mark.parametrize("variable", ["CONTAINERS", "EXEC", "NETWORKS", "VOLUMES", "POST"])
def test_proxy_habilita_lo_que_hace_falta(compose, variable):
    env = compose["services"]["docker-socket-proxy"]["environment"]
    assert env.get(variable) == 1


@pytest.mark.parametrize("variable", [
    "BUILD", "SWARM", "SECRETS", "PLUGINS", "NODES", "SERVICES", "SESSION", "AUTH",
])
def test_proxy_mantiene_cerrado_lo_peligroso(compose, variable):
    """Estas NO deben aparecer habilitadas -su ausencia en las variables
    significa que quedan en su valor por defecto (0), que es lo correcto.
    Si alguna aparece puesta en 1, es una regresión de seguridad real."""
    env = compose["services"]["docker-socket-proxy"]["environment"]
    assert env.get(variable) != 1


# --- Backend corre sin privilegios ------------------------------------------

def test_backend_crea_un_usuario_sin_privilegios(dockerfile_backend):
    assert "useradd" in dockerfile_backend
    assert "squidmgr" in dockerfile_backend


def test_backend_usuario_comparte_grupo_con_squid(dockerfile_backend):
    """Mismo grupo 'proxy' (gid 13, ya viene de fábrica en python:3.12-slim)
    que usa Squid en su propia imagen: sin esto, los archivos que este
    backend escribe en el volumen compartido (squid_passwd, squid_digest, el
    keytab de Kerberos) quedarían ilegibles para Squid en cuanto el backend
    deje de poder hacer chown a un uid ajeno."""
    assert "-g proxy" in dockerfile_backend


def test_backend_usa_gosu_para_bajar_privilegios(dockerfile_backend):
    assert "gosu" in dockerfile_backend


def test_backend_entrypoint_no_toca_spool_ni_logs(entrypoint_backend):
    """El backend solo LEE de squid-spool/squid-logs, nunca escribe: un
    chown -R ahi seria innecesario y potencialmente muy lento (el directorio
    de cache de Squid puede tener cientos de miles de archivos)."""
    assert "/etc/squid" in entrypoint_backend
    assert "/var/spool/squid" not in entrypoint_backend
    assert "/var/log/squid" not in entrypoint_backend


def test_backend_entrypoint_corrige_el_dueno_de_etc_squid(entrypoint_backend):
    assert "chown" in entrypoint_backend
    assert "squidmgr:proxy" in entrypoint_backend


def test_backend_entrypoint_corrige_el_dueno_de_project_dir(entrypoint_backend):
    """PROJECT_DIR es un bind-mount del host (no un volumen de Docker), casi
    siempre propiedad de root: sync_env_port() necesita escribir el .env ahí
    (con un temporal en el mismo directorio, para el rename atómico), y sin
    esto el backend sin privilegios se queda sin poder sincronizar el
    PROXY_PORT tras cambiar el puerto -confirmado en vivo: 'Permission
    denied' al escribir .env.tmp-*, y el contenedor de Squid recreándose en
    el puerto viejo en vez del nuevo."""
    assert "PROJECT_DIR" in entrypoint_backend
    assert '.env' in entrypoint_backend
