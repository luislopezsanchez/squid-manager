"""upgrade-docker.sh: complemento de backup-database.sh e
install-nativo.sh para el modo Docker.

Mismo criterio que el resto de tests de scripts de este proyecto: no
ejecuta el script -corre en la máquina de destino, no en la suite-, pero
comprueba las propiedades que no deben perderse.
"""

from pathlib import Path

import pytest

MARCADOR = Path("upgrade-docker.sh")


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


def test_hace_backup_antes_de_tocar_el_codigo():
    """La resiliencia de un upgrade depende de que el backup se haga ANTES,
    no despues de que algo salga mal."""
    contenido = _script()
    pos_backup = contenido.index("backup-database.sh")
    pos_checkout = contenido.index("git checkout --quiet -- .")
    assert pos_backup < pos_checkout


def test_un_backup_fallido_no_bloquea_el_resto():
    """Preferible seguir sin backup (con aviso) a que un problema del
    backup impida actualizar del todo -set -e exigiria manejar el error
    explicitamente, que es lo que hace el || de abajo."""
    contenido = _script()
    assert '"$PROJECT_DIR/backup-database.sh" ||' in contenido


def test_descarta_cambios_locales_antes_de_cambiar_de_rama():
    """Mismo bug real que en install-nativo.sh: git checkout se niega a
    cambiar de rama si eso pisaria una modificacion local, y aborta el
    script entero antes de llegar al reset --hard que la iba a descartar
    de todas formas."""
    contenido = _script()
    assert "git checkout --quiet -- ." in contenido
    assert "git clean -fdq" in contenido
    pos_clean = contenido.index("git clean -fdq")
    pos_branch_checkout = contenido.index('git checkout --quiet "$BRANCH"')
    assert pos_clean < pos_branch_checkout


def test_build_no_es_opcional():
    contenido = _script()
    assert "docker compose up -d --build" in contenido


def test_verifica_health_al_final():
    contenido = _script()
    assert "/health" in contenido
