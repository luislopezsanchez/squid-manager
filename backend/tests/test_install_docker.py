"""install.sh: instalador del modo Docker.

Mismo criterio que el resto de tests de scripts de este proyecto: no ejecuta
el script -corre en la máquina de destino, no en la suite-, pero comprueba
las propiedades que no deben perderse.
"""

from pathlib import Path

import pytest

MARCADOR = Path("install.sh")


def _raiz_del_proyecto() -> Path | None:
    for base in Path(__file__).resolve().parents:
        if (base / MARCADOR).is_file():
            return base

    from app.services.squid_service import _project_dir

    base = _project_dir()
    return base if base and (base / MARCADOR).is_file() else None


def _script() -> str:
    raiz = _raiz_del_proyecto()
    if raiz is None:
        pytest.skip("el proyecto no esta accesible desde aqui")
    return (raiz / MARCADOR).read_text(encoding="utf-8")


def test_falla_seguro():
    assert "set -euo pipefail" in _script()


def test_rechaza_una_ruta_que_el_backend_no_puede_alcanzar_antes_de_levantar_nada():
    """El backend corre como uid 999 dentro del contenedor y lee
    docker-compose.yml y .env por el bind-mount. Si el proyecto está bajo un
    directorio sin 'x' para "otros" (clonar en /root, que es 700), ese
    usuario no llega al fichero: el panel arranca pero NO aplica la config a
    Squid y el proxy se queda en el arranque provisional. Confirmado en vivo
    (172.30.36.42, 2026-09-10). La comprobación tiene que estar ANTES del
    `docker compose up`."""
    contenido = _script()
    assert "ruta_accesible_para_otros" in contenido
    pos_check = contenido.index("ruta_accesible_para_otros \"$INSTALL_DIR\"")
    # el comando real está a principio de línea; hay otra mención dentro de un
    # mensaje de aviso ("  3) docker compose up -d") que no cuenta.
    pos_up = contenido.index("\ndocker compose up -d")
    assert pos_check < pos_up
    # el mensaje de error orienta a la solución
    assert "/opt/squid-manager" in contenido
    assert "chmod o+x /root" in contenido


def test_declara_el_directorio_como_safe_para_git():
    """git 2.35.2+ aborta con "detected dubious ownership": el entrypoint del
    backend hace chown del proyecto a uid 999 y el admin corre git como root.
    Se declara safe, idempotente, en la instalación -no solo en el upgrade-."""
    contenido = _script()
    assert "safe.directory" in contenido
    assert "--get-all safe.directory" in contenido


def test_no_canaliza_a_bash_desde_internet():
    """La cabecera insiste en descargar-revisar-ejecutar, no `curl | bash`."""
    contenido = _script()
    assert "less install.sh" in contenido
