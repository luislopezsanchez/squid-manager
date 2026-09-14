"""upgrade-nativo.sh: script de actualización independiente de
install-nativo.sh para el modo nativo (sin Docker).

Por qué separado y no basta con volver a correr install-nativo.sh
directamente (que ya es seguro de re-ejecutar sobre una instalación que
existe): install-nativo.sh hace git checkout/fetch/reset SOBRE SI MISMO
como parte de la actualización. Si la versión ya instalada difiere de la
versión destino en la lógica del propio script, bash sigue ejecutando en
memoria el código VIEJO durante el resto de la corrida mientras los
archivos de disco -el propio script incluido- ya cambiaron por debajo: la
corrección de git-checkout, pgvector y el reinicio de servicios, todas
agregadas en versiones más nuevas, nunca llegan a ejecutarse. Bug real,
encontrado y aislado probando el upgrade main -> pruebas en vivo
(172.30.36.63, 2026-09-08).

upgrade-nativo.sh evita el problema por diseño: nunca se modifica a sí
mismo. Trae el código nuevo sobre INSTALL_DIR y luego invoca -como proceso
nuevo- el install-nativo.sh que quedó ahí, que en ese momento ya es 100%
la versión destino.

Mismo criterio que test_upgrade_docker.py: no ejecuta el script -corre en
la máquina de destino, no en la suite-, pero comprueba las propiedades que
no deben perderse.
"""

from pathlib import Path

import pytest

MARCADOR = Path("upgrade-nativo.sh")


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
    """Misma resiliencia que upgrade-docker.sh: el backup tiene que ser
    ANTES de tocar el código, no después de que algo salga mal."""
    contenido = _script()
    pos_backup = contenido.index("backup-database.sh")
    pos_checkout = contenido.index("git checkout --quiet -- .")
    assert pos_backup < pos_checkout


def test_un_backup_fallido_no_bloquea_el_resto():
    contenido = _script()
    assert '"$INSTALL_DIR/backup-database.sh" ||' in contenido


def test_descarta_cambios_locales_antes_de_cambiar_de_rama():
    """Mismo bug real que en install-nativo.sh y upgrade-docker.sh: git
    checkout se niega a cambiar de rama si eso pisaría una modificación
    local, y aborta el script entero antes de llegar al reset --hard que
    la iba a descartar de todas formas."""
    contenido = _script()
    assert "git checkout --quiet -- ." in contenido
    assert "git clean -fdq" in contenido
    pos_clean = contenido.index("git clean -fdq")
    pos_branch_checkout = contenido.index('git checkout --quiet "$BRANCH"')
    assert pos_clean < pos_branch_checkout


def test_nunca_se_modifica_a_si_mismo():
    """El motivo de existir de este script: el git checkout/reset actúa
    sobre INSTALL_DIR, pero install-nativo.sh -que sí cambia bajo sus
    propios pies al actualizar- se invoca DESPUÉS, como proceso nuevo, no
    con `source`, para no arrastrar el mismo problema un nivel más arriba."""
    contenido = _script()
    pos_reset = contenido.index('git reset --hard --quiet "origin/$BRANCH"')
    pos_invocacion = contenido.index('bash "$INSTALL_DIR/install-nativo.sh"')
    assert pos_reset < pos_invocacion
    assert "source " not in contenido
    assert not contenido.strip().endswith(". \"$INSTALL_DIR/install-nativo.sh\"")


def test_purga_el_pycache_antes_de_reinstalar():
    """__pycache__ está en .gitignore, así que "git clean -fd" -que respeta
    el .gitignore a propósito, para no llevarse .env ni node_modules/-
    nunca lo toca. Un .pyc viejo ahí puede quedar sirviendo al proceso
    reiniciado con código de antes del upgrade. Encontrado probando
    upgrades repetidos sobre el mismo checkout en 172.30.36.63."""
    contenido = _script()
    assert '-name "__pycache__"' in contenido
    assert "-exec rm -rf" in contenido


def test_exige_una_instalacion_existente():
    """No es un instalador: sobre un directorio que no es un checkout git
    debe fallar con un mensaje claro, no intentar seguir a ciegas."""
    contenido = _script()
    assert '[ -d "$INSTALL_DIR/.git" ]' in contenido


def test_se_ubica_por_el_directorio_del_script_no_una_ruta_fija():
    """Muchas instalaciones no estan en /opt/squid-manager. Igual que
    upgrade-docker.sh con PROJECT_DIR, INSTALL_DIR se deriva del directorio
    donde vive ESTE script cuando no se pasa uno explicito -no puede quedar
    /opt/squid-manager como unico default-."""
    contenido = _script()
    assert 'INSTALL_DIR="${INSTALL_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"' in contenido
    assert 'INSTALL_DIR="${INSTALL_DIR:-/opt/squid-manager}"' not in contenido


def test_declara_el_directorio_como_safe_antes_de_cualquier_git():
    """git 2.35.2+ aborta con "detected dubious ownership" si el dueno del
    repo no es quien corre git. Hay que declararlo safe ANTES del primer
    comando git, e idempotente. install-nativo.sh, invocado despues, hereda
    esta config del mismo usuario."""
    contenido = _script()
    assert "safe.directory" in contenido
    pos_safe = contenido.index("safe.directory")
    pos_primer_git = contenido.index("git checkout --quiet -- .")
    assert pos_safe < pos_primer_git
    assert "--get-all safe.directory" in contenido


def test_declara_safe_directory_con_system_no_global():
    """Bug real, visto en vivo: "git config --global --add safe.directory"
    necesita $HOME para ubicar ~/.gitconfig, y una unidad transient de
    systemd-run (el lanzador real desde el panel) no lo fija por si sola ->
    "fatal: $HOME not set", con el proceso muriendo antes de tocar el
    repositorio remoto. --system (como ya hacia install-nativo.sh) escribe
    en /etc/gitconfig y no depende de HOME en absoluto. Si esto vuelve a
    "--global" el bug reaparece igual, aunque exista el export defensivo de
    abajo -mejor no depender de un solo mecanismo-."""
    contenido = _script()
    assert "git config --system --get-all safe.directory" in contenido
    assert "git config --system --add safe.directory" in contenido
    assert "git config --global --add safe.directory" not in contenido


def test_fija_home_defensivamente_al_arrancar():
    """Segunda capa de defensa, independiente de --system: si el dia de
    manana un lanzador nuevo (u otro cambio) reintroduce una operacion que
    si necesite HOME, este script no depende de que ese lanzador se acuerde
    de pasarlo -se defiende solo, sin pisar un HOME ya presente."""
    contenido = _script()
    assert 'export HOME="${HOME:-/root}"' in contenido
    pos_export = contenido.index('export HOME="${HOME:-/root}"')
    pos_primer_git = contenido.index("git config --system")
    assert pos_export < pos_primer_git


def test_termina_invocando_install_nativo_de_la_version_destino():
    contenido = _script()
    assert 'bash "$INSTALL_DIR/install-nativo.sh"' in contenido


def test_aborta_si_no_es_una_instalacion_nativa_antes_de_tocar_nada():
    """Simetrico a upgrade-docker.sh: si el .env dice DEPLOY_MODE=docker, o
    hay contenedores squidmgr-* corriendo, o no hay systemctl, esto no es una
    instalacion nativa y hay que abortar ANTES del backup y del git reset."""
    contenido = _script()
    assert "DEPLOY_MODE" in contenido
    assert '"$_MODO" = "docker"' in contenido
    assert "squidmgr-" in contenido
    pos_check = contenido.index('"$_MODO" = "docker"')
    pos_backup = contenido.index('paso "1. Backup')
    pos_git = contenido.index("git reset --hard --quiet")
    assert pos_check < pos_backup < pos_git
    assert "upgrade-docker.sh" in contenido


def test_se_desliga_de_la_terminal_para_sobrevivir_a_un_corte_de_ssh():
    """La recompilacion de Squid tarda 10+ min. Un corte de SSH manda SIGHUP
    y mata el script a mitad de install-nativo.sh: paquetes puestos,
    migraciones quiza aplicadas, servicio sin reiniciar -mismo patron del
    incidente Docker en produccion-. El script se re-lanza con setsid a un
    log ANTES del backup y del git reset, detras de las guardas
    SQUIDMGR_UPGRADE_DETACHED / SQUIDMGR_UPGRADE_FOREGROUND."""
    contenido = _script()
    assert "setsid" in contenido
    assert "SQUIDMGR_UPGRADE_DETACHED" in contenido
    assert "SQUIDMGR_UPGRADE_FOREGROUND" in contenido
    pos_detach = contenido.index("setsid bash")
    pos_backup = contenido.index('paso "1. Backup')
    pos_git = contenido.index("git reset --hard --quiet")
    assert pos_detach < pos_backup < pos_git


def test_el_log_dice_si_la_actualizacion_termino_bien_o_mal():
    """Corriendo desligado el unico rastro es el log: termina con una linea
    inequivoca de OK o de FALLO y sale con codigo != 0 si el commit servido
    no coincide con el esperado."""
    contenido = _script()
    assert "ACTUALIZACION COMPLETADA" in contenido
    assert "LA ACTUALIZACION NO TERMINO BIEN" in contenido


def test_verifica_el_commit_servido_de_verdad_y_reintenta_si_no_coincide():
    """install-nativo.sh ya confirma que /health responde, pero eso no
    confirma que sea el commit que se acaba de dejar en el checkout -visto
    en pruebas repetidas en vivo, el primer reinicio dentro de la misma
    corrida puede quedar sirviendo todavía el commit anterior un rato-. Sin
    una causa aislada con certeza, lo honesto es verificar y reintentar un
    reinicio, no dar el upgrade por bueno a ciegas."""
    contenido = _script()
    assert "rev-parse --short HEAD" in contenido
    pos_invocacion = contenido.index('bash "$INSTALL_DIR/install-nativo.sh"')
    pos_verificacion = contenido.index("COMMIT_ESPERADO")
    assert pos_invocacion < pos_verificacion
    assert "systemctl restart squidmanager" in contenido[pos_verificacion:]


def test_escribe_su_resultado_para_autoupdate_check():
    """La unidad transient con --collect que lanza autoupdate-check.sh se
    descarga apenas termina, y `systemctl show` sobre una unidad descargada
    responde Result=success/ExecMainStatus=0 haya pasado lo que haya pasado
    (verificado en systemd 255): leer el estado de la unidad reportaba "ok"
    incluso para un upgrade abortado a mitad (auditoria 2026-09-14, hallazgo
    10-001). El resultado lo escribe este script, y cualquier salida que no
    haya llegado al final marca error (trap de EXIT).
    """
    s = _script()
    assert "SQUIDMGR_RESULT_FILE" in s
    assert "trap _escribir_resultado_upgrade EXIT" in s
    # Por defecto error: solo la confirmacion final del commit servido lo
    # vuelve "ok".
    assert '_RESULTADO_UPGRADE="error"' in s
    assert s.index('_RESULTADO_UPGRADE="error"') < s.index('_RESULTADO_UPGRADE="ok"')
    assert s.index('_RESULTADO_UPGRADE="ok"') > s.index('COMMIT_SERVIDO" = "$COMMIT_ESPERADO"')


def test_no_repite_el_backup_en_la_segunda_pasada():
    s = _script()
    assert 'SQUIDMGR_UPGRADE_REEXEC' in s
    bloque = s.split('paso "1. Backup antes de actualizar"', 1)[1].split('paso "2.', 1)[0]
    assert 'SQUIDMGR_UPGRADE_REEXEC' in bloque
