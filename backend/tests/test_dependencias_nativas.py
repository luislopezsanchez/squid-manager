"""El instalador nativo tiene que traer todo lo que el código ejecuta.

El caso real: el backend genera el hash de cada usuario del proxy invocando
`htpasswd`. La imagen Docker instala `apache2-utils`, que es quien lo trae; el
instalador nativo no lo hacía. La instalación terminaba diciendo que todo había
ido bien, y el fallo aparecía mucho después —al crear el primer usuario— con un
mensaje que encima no venía a cuento: «reconstruye la imagen», cuando en una
instalación nativa no hay ninguna imagen.

Esta prueba cruza las dos listas: los binarios que el código invoca de verdad y
los paquetes que el instalador declara. Es barata y detecta la clase entera de
problema, no solo el caso que ya conocemos.
"""

import re
from pathlib import Path

import pytest

# Binario -> paquete de Debian/Ubuntu que lo proporciona.
PROVEEDORES = {
    "htpasswd": "apache2-utils",
    "openssl": "openssl",
    "logrotate": "logrotate",
    "systemctl": None,   # parte del sistema, no se instala
    "squid": "squid-openssl",
    "docker": None,      # solo en modo Docker, y lo aporta el anfitrión
}


def _raiz() -> Path | None:
    for base in Path(__file__).resolve().parents:
        if (base / "install-nativo.sh").is_file():
            return base
    return None


@pytest.fixture(scope="module")
def instalador() -> str:
    raiz = _raiz()
    if raiz is None:
        pytest.skip("install-nativo.sh no está disponible junto al backend")
    return (raiz / "install-nativo.sh").read_text(encoding="utf-8")


def _binarios_invocados() -> set[str]:
    """Comandos externos que el backend ejecuta con subprocess."""
    raiz = _raiz()
    if raiz is None:
        return set()

    encontrados: set[str] = set()
    patron = re.compile(r'subprocess\.\w+\(\s*\n?\s*\[\s*"([a-z0-9_.-]+)"', re.M)
    for fichero in (raiz / "backend" / "app").rglob("*.py"):
        encontrados.update(patron.findall(fichero.read_text(encoding="utf-8")))
    return encontrados


def test_htpasswd_esta_cubierto(instalador):
    """El caso concreto que se nos escapó."""
    assert "apache2-utils" in instalador, (
        "el backend genera los hashes con htpasswd, que viene en apache2-utils"
    )


def test_todo_binario_que_se_invoca_tiene_su_paquete(instalador):
    faltan = []
    for binario in sorted(_binarios_invocados()):
        paquete = PROVEEDORES.get(binario, "DESCONOCIDO")
        if paquete is None:
            continue
        if paquete == "DESCONOCIDO":
            faltan.append(f"{binario} (no se sabe qué paquete lo trae)")
        elif paquete not in instalador:
            faltan.append(f"{binario} -> falta instalar {paquete}")

    assert not faltan, "el instalador nativo no cubre: " + "; ".join(faltan)


def test_el_instalador_comprueba_los_binarios_al_terminar(instalador):
    """Que falle al instalar, no el día que alguien cree un usuario."""
    assert "command -v" in instalador and "htpasswd" in instalador, (
        "el instalador debe verificar que los comandos necesarios existen"
    )
