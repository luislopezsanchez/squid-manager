"""El proxy no puede quedar abierto entre que arranca y que se configura.

El caso real, encontrado instalando de cero en una máquina limpia: tanto el
instalador nativo como el entrypoint de Docker escriben un `squid.conf` que
ellos mismos llaman «configuración inicial temporal», y ese fichero traía

    acl localnet src 10.0.0.0/8
    acl localnet src 172.16.0.0/12
    acl localnet src 192.168.0.0/16
    http_access allow localnet

sin una sola línea `auth_param`. Resultado: recién instalado, cualquiera dentro
del rango privado podía usar el proxy sin credenciales —comprobado, HTTP 200 sin
autenticarse y con un usuario inexistente—. La configuración buena, la que sí
exige autenticación, solo se escribía cuando alguien entraba al panel y pulsaba
«aplicar», y nada en la instalación decía que hubiera que hacerlo.

El arranque provisional ahora niega todo salvo localhost, y el backend aplica la
definitiva él solo. Estas pruebas cubren la mitad estática: que nadie vuelva a
abrir la LAN en un fichero de arranque.
"""

import re
from pathlib import Path

import pytest


def _raiz() -> Path | None:
    for base in Path(__file__).resolve().parents:
        if (base / "install-nativo.sh").is_file():
            return base
    return None


RAIZ = _raiz()

ARRANQUES = [
    "install-nativo.sh",
    "squid/entrypoint.sh",
]


def _texto(relativa: str) -> str:
    assert RAIZ is not None, "no se encontró la raíz del proyecto"
    fichero = RAIZ / relativa
    if not fichero.is_file():
        pytest.skip(f"{relativa} no está en este árbol")
    return fichero.read_text(encoding="utf-8")


@pytest.mark.parametrize("relativa", ARRANQUES)
def test_el_arranque_no_permite_la_lan(relativa):
    """Ningún fichero de arranque puede permitir el rango privado."""
    texto = _texto(relativa)

    permisos = re.findall(r"^http_access\s+allow\s+(\S+)", texto, re.MULTILINE)
    assert permisos, f"{relativa}: no se encontró ninguna regla http_access allow"

    prohibidos = [p for p in permisos if p != "localhost"]
    assert not prohibidos, (
        f"{relativa}: el arranque provisional permite {prohibidos}. "
        "Solo puede permitir localhost: cualquier otra cosa deja el proxy "
        "abierto hasta que alguien aplique la configuración desde el panel."
    )


@pytest.mark.parametrize("relativa", ARRANQUES)
def test_el_arranque_termina_denegando(relativa):
    """La última regla tiene que ser un deny all."""
    texto = _texto(relativa)
    reglas = re.findall(r"^http_access\s+(\S+)\s+(\S+)", texto, re.MULTILINE)
    assert reglas, f"{relativa}: no se encontró ninguna regla http_access"
    assert reglas[-1] == ("deny", "all"), (
        f"{relativa}: la última regla es {reglas[-1]}, y tiene que ser «deny all»."
    )


@pytest.mark.parametrize("relativa", ARRANQUES)
def test_el_arranque_no_declara_localnet(relativa):
    """Sin la ACL no hay forma de permitirla por descuido más adelante."""
    texto = _texto(relativa)
    assert not re.search(r"^acl\s+localnet\s+src", texto, re.MULTILINE), (
        f"{relativa}: sigue declarando la ACL localnet en el arranque provisional."
    )


def test_la_plantilla_real_si_exige_autenticacion():
    """El contraste: la configuración definitiva sí autentica.

    Si esta prueba fallara, el arranque cerrado dejaría el proxy inservible en
    lugar de seguro, que es un fallo distinto y peor de diagnosticar.
    """
    assert RAIZ is not None
    plantilla = RAIZ / "backend" / "app" / "templates" / "squid.conf.j2"
    if not plantilla.is_file():
        pytest.skip("no está la plantilla")
    texto = plantilla.read_text(encoding="utf-8")
    assert "auth_param basic program" in texto
    assert "http_access deny !authenticated" in texto


# ---------------------------------------------------------------------------
# La otra mitad: reconocer el arranque provisional para sustituirlo.
# ---------------------------------------------------------------------------

def test_reconoce_el_arranque_provisional_de_los_dos_modos(tmp_path):
    """El instalador nativo lo escribe sin tilde y el entrypoint con ella."""
    from app.main import _es_configuracion_provisional

    nativo = tmp_path / "nativo.conf"
    nativo.write_text("# SquidManager - Configuracion inicial temporal\nhttp_port 3128\n")
    assert _es_configuracion_provisional(nativo) is True

    docker = tmp_path / "docker.conf"
    docker.write_text("# SquidManager - Configuración inicial temporal\nhttp_port 3128\n")
    assert _es_configuracion_provisional(docker) is True


def test_no_pisa_una_configuracion_ya_generada(tmp_path):
    """Lo que escribe el panel no se puede tocar en cada arranque."""
    from app.main import _es_configuracion_provisional

    real = tmp_path / "real.conf"
    real.write_text(
        "# ============================================\n"
        "# SquidManager - Configuración generada automáticamente\n"
        "auth_param basic program /usr/lib/squid/squidmanager_auth_helper\n"
    )
    assert _es_configuracion_provisional(real) is False


def test_si_no_hay_fichero_hay_que_generarlo(tmp_path):
    from app.main import _es_configuracion_provisional

    assert _es_configuracion_provisional(tmp_path / "no-existe.conf") is True
