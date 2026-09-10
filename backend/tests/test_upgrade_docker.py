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


def test_reindexa_la_base_despues_del_cambio_de_imagen_de_postgres():
    """Hasta 0.21.0 la imagen era postgres:16-alpine (musl, que no registra
    version de collation); desde 0.22.0 es pgvector/pgvector:pg16 (glibc).
    Al cambiar de imagen Postgres NO avisa, pero el orden de comparacion de
    texto cambia y los indices btree de texto -entre ellos el UNIQUE de
    proxy_users.username- quedan logicamente corruptos (confirmado con
    amcheck en vivo, 172.30.36.42, 2026-09-10). REINDEX los reconstruye, y
    tiene que correr DESPUES de levantar los contenedores y ANTES de dar el
    upgrade por bueno."""
    contenido = _script()
    assert "REINDEX DATABASE" in contenido
    pos_up = contenido.index("docker compose up -d --build")
    pos_reindex = contenido.index("REINDEX DATABASE")
    pos_health = contenido.index("/health")
    assert pos_up < pos_reindex < pos_health


def test_el_reindex_no_es_fatal_si_falla():
    """Un REINDEX que no corre (base inaccesible, permisos) no debe abortar
    el upgrade entero bajo set -e: se avisa como hacerlo a mano y se sigue."""
    contenido = _script()
    assert "no se pudieron reconstruir los indices" in contenido.lower()


def test_se_ubica_por_el_directorio_del_script_no_una_ruta_fija():
    """Muchas instalaciones no estan en /opt/squid-manager: PROJECT_DIR se
    deriva del directorio donde vive el script, salvo override explicito."""
    contenido = _script()
    assert 'PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"' in contenido


def test_declara_el_directorio_como_safe_antes_de_cualquier_git():
    """git 2.35.2+ aborta con "detected dubious ownership" si el dueno del
    repo no es quien corre git -en Docker es LO NORMAL: entrypoint.sh del
    backend hace chown a uid 999 y el script se corre como root-. Hay que
    declararlo safe ANTES del primer comando git, e idempotente."""
    contenido = _script()
    assert "safe.directory" in contenido
    pos_safe = contenido.index("safe.directory")
    pos_primer_git = contenido.index("git checkout --quiet -- .")
    assert pos_safe < pos_primer_git
    # idempotente: solo agrega si no estaba
    assert "--get-all safe.directory" in contenido


def test_se_desliga_de_la_terminal_para_sobrevivir_a_un_corte_de_ssh():
    """El build de Squid tarda 10+ min. Corrido como `ssh host "bash
    upgrade-docker.sh"`, un corte de SSH manda SIGHUP y el script muere a
    mitad: git ya actualizado, contenedores sin recrear -visto en produccion
    (Contabo) y reproducido en una VM (172.30.36.42, "Remote side
    unexpectedly closed network connection")-. El script se re-lanza con
    setsid, salida a un log, y la primera invocacion sale enseguida. El
    re-lanzamiento va ANTES del backup y del git reset (no tiene sentido
    empezar a mutar el checkout en el proceso que va a morir con la terminal),
    y detras de las guardas SQUIDMGR_UPGRADE_DETACHED (ya desligado) y
    SQUIDMGR_UPGRADE_FOREGROUND (opt-out para tmux/consola local)."""
    contenido = _script()
    assert "setsid" in contenido
    assert "SQUIDMGR_UPGRADE_DETACHED" in contenido
    assert "SQUIDMGR_UPGRADE_FOREGROUND" in contenido
    pos_detach = contenido.index("setsid bash")
    pos_backup = contenido.index("=== 1. Backup")
    pos_git = contenido.index("git reset --hard --quiet")
    assert pos_detach < pos_backup < pos_git


def test_el_log_dice_si_la_actualizacion_termino_bien_o_mal():
    """Corriendo desligado, el unico rastro es el log: tiene que terminar con
    una linea inequivoca de OK o de FALLO, y salir con codigo != 0 si algo
    del final no cuadra, para que un `tail` del log no deje la duda."""
    contenido = _script()
    assert "ACTUALIZACION COMPLETADA" in contenido
    assert "LA ACTUALIZACION NO TERMINO BIEN" in contenido


def test_aborta_si_no_es_una_instalacion_docker_antes_de_tocar_nada():
    """El path /opt/squid-manager es el default de los dos modos: correr el
    script equivocado es un error facil. Sin este chequeo, hacia el backup y
    el `git reset --hard` -mutando el checkout- y recien moria en el paso 3
    con "docker: command not found". La comprobacion (DEPLOY_MODE=native o
    'docker' ausente) tiene que estar ANTES del backup y del git."""
    contenido = _script()
    assert 'DEPLOY_MODE' in contenido and 'native' in contenido
    assert "command -v docker" in contenido
    pos_check = contenido.index("command -v docker")
    pos_backup = contenido.index("=== 1. Backup")
    pos_git = contenido.index("git reset --hard --quiet")
    assert pos_check < pos_backup < pos_git
    assert "upgrade-nativo.sh" in contenido
