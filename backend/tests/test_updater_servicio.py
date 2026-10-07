"""Servicio `updater` (docker-autoupdate-check.sh en sus dos modos) y su convivencia con el temporizador del host.

Se ejecuta el script de verdad contra un directorio de proyecto temporal, con un `docker` simulado en el PATH que
registra sus llamadas. Cubre las ramas que, si fallan, dejan "Actualizar ahora" sin efecto o aplican una orden dos
veces: ceder el turno, el bloqueo, el contenedor auxiliar y las actualizaciones interrumpidas.
"""

import json
import os
import subprocess
import time
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "docker-autoupdate-check.sh"


@pytest.fixture
def entorno(tmp_path):
    proyecto = tmp_path / "proyecto"
    proyecto.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "rama-de-prueba", str(proyecto)], check=True)
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    log = tmp_path / "docker.log"
    log.write_text("")
    stub = bin_ / "docker"
    stub.write_text(
        '#!/bin/bash\n'
        'echo "$*" >> "$STUB_LOG"\n'
        'case "$1" in\n'
        '  inspect) if [[ "$*" == *com.docker.compose.project* ]]; then echo "${STUB_PROYECTO:-miproyecto}"; else echo "sha256:imagenfalsa"; fi ;;\n'
        '  ps) [ -n "${STUB_AUX_VIVO:-}" ] && echo "abc123" || true ;;\n'
        '  run) [ -z "${STUB_RUN_FALLA:-}" ] ;;\n'
        'esac\n'
    )
    stub.chmod(0o755)
    # "upgrade-docker.sh" falso: deja constancia de con que entorno lo llamaron.
    upgrade = tmp_path / "upgrade-falso.sh"
    upgrade.write_text(
        '#!/bin/bash\n'
        'echo "rama=$BRANCH en_updater=${SQUIDMGR_IN_UPDATER:-} fg=${SQUIDMGR_UPGRADE_FOREGROUND:-}" >> "$PROJECT_DIR/upgrade.llamado"\n'
        'exit "${UPGRADE_SALIDA:-0}"\n'
    )
    upgrade.chmod(0o755)
    base = {
        **os.environ,
        "PATH": f"{bin_}:{os.environ['PATH']}",
        "PROJECT_DIR": str(proyecto),
        "STUB_LOG": str(log),
        "SQUIDMGR_UPGRADE_SCRIPT": str(upgrade),
    }
    return proyecto, base, log


def _estado(proyecto, aprobada=True, running=False, hace=60, running_hace=3600):
    t = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - hace))
    inicio = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - running_hace))
    (proyecto / ".update_state.json").write_text(json.dumps({
        "check": {"update_available": True, "remote_commit": "bbbbbbb", "local_commit": "aaaaaaa", "commits": [{"sha": "bbbbbbb"}]},
        "request": {"approved": aprobada, "scheduled_at": t if aprobada else None, "requested_by": "admin", "requested_at": t},
        "apply": {"status": "running" if running else None, "started_at": inicio if running else None, "finished_at": None, "commit": None, "log_tail": None},
    }))


def _leer(proyecto):
    return json.loads((proyecto / ".update_state.json").read_text())


def _ejecutar(env, **extra):
    return subprocess.run(["bash", str(SCRIPT)], env={**env, **{k: str(v) for k, v in extra.items()}},
                          capture_output=True, text=True, timeout=60)


def _llamadas(log):
    return log.read_text().splitlines()


# --- latidos ---------------------------------------------------------------

def test_el_servicio_escribe_el_latido_y_la_marca_de_vivo_aunque_no_haya_estado(entorno):
    proyecto, env, _ = entorno
    r = _ejecutar(env, SQUIDMGR_UPDATER=1)
    assert r.returncode == 0, r.stderr
    for f in (".update_heartbeat", ".updater_alive"):
        assert abs(int((proyecto / f).read_text()) - time.time()) < 30


def test_el_temporizador_del_host_no_escribe_la_marca_de_vivo_del_servicio(entorno):
    proyecto, env, _ = entorno
    _ejecutar(env)
    assert (proyecto / ".update_heartbeat").exists()
    assert not (proyecto / ".updater_alive").exists()


# --- convivencia: el temporizador cede mientras el servicio vive -------------

def test_el_temporizador_cede_si_el_servicio_esta_vivo_y_no_toca_la_orden(entorno):
    proyecto, env, _ = entorno
    _estado(proyecto)
    (proyecto / ".updater_alive").write_text(str(int(time.time()) - 10))
    r = _ejecutar(env)
    assert r.returncode == 0
    assert _leer(proyecto)["request"]["approved"] is True
    assert not (proyecto / "upgrade.llamado").exists()


def test_el_temporizador_trabaja_si_el_servicio_dejo_de_dar_senales(entorno):
    proyecto, env, _ = entorno
    _estado(proyecto)
    (proyecto / ".updater_alive").write_text(str(int(time.time()) - 600))
    r = _ejecutar(env)
    assert r.returncode == 0, r.stderr
    e = _leer(proyecto)
    assert e["request"]["approved"] is False and e["apply"]["status"] == "ok"
    assert "en_updater=0" in (proyecto / "upgrade.llamado").read_text()


def test_el_temporizador_sin_servicio_funciona_como_siempre(entorno):
    proyecto, env, _ = entorno
    _estado(proyecto)
    r = _ejecutar(env)
    assert r.returncode == 0, r.stderr
    assert _leer(proyecto)["apply"]["status"] == "ok"
    assert "fg=1" in (proyecto / "upgrade.llamado").read_text()


def test_una_actualizacion_que_falla_queda_como_error(entorno):
    proyecto, env, _ = entorno
    _estado(proyecto)
    r = _ejecutar(env, UPGRADE_SALIDA=3)
    assert r.returncode == 0
    assert _leer(proyecto)["apply"]["status"] == "error"


# --- el servicio lanza un contenedor auxiliar, no aplica el mismo ------------

def test_el_servicio_consume_la_orden_y_lanza_el_contenedor_auxiliar(entorno):
    proyecto, env, log = entorno
    _estado(proyecto)
    r = _ejecutar(env, SQUIDMGR_UPDATER=1)
    assert r.returncode == 0, r.stderr
    e = _leer(proyecto)
    assert e["request"]["approved"] is False and e["apply"]["status"] == "running"
    run = [l for l in _llamadas(log) if l.startswith("run ")]
    assert len(run) == 1
    linea = run[0]
    assert "--name squidmgr-updater-run" in linea and "-d" in linea.split() and "--rm" in linea
    assert f"-v {proyecto}:{proyecto}" in linea and "/var/run/docker.sock:/var/run/docker.sock" in linea
    assert "SQUIDMGR_APPLY=1" in linea and "COMPOSE_PROJECT_NAME=miproyecto" in linea
    assert "sha256:imagenfalsa" in linea and "docker-autoupdate-check.sh" in linea
    assert "--entrypoint timeout" in linea and "sha256:imagenfalsa 7200 bash" in linea, "el auxiliar debe tener un tiempo limite"
    assert not (proyecto / "upgrade.llamado").exists(), "el servicio no debe aplicar la actualizacion el mismo"


def test_si_no_se_puede_lanzar_el_auxiliar_queda_un_error_visible(entorno):
    proyecto, env, _ = entorno
    _estado(proyecto)
    r = _ejecutar(env, SQUIDMGR_UPDATER=1, STUB_RUN_FALLA=1)
    assert r.returncode == 0
    e = _leer(proyecto)
    assert e["apply"]["status"] == "error" and "auxiliar" in e["apply"]["log_tail"]


def test_el_contenedor_auxiliar_aplica_y_deja_el_resultado(entorno):
    proyecto, env, _ = entorno
    _estado(proyecto, aprobada=False, running=True)  # el servicio ya consumio la orden y puso "running"
    r = _ejecutar(env, SQUIDMGR_UPDATER=1, SQUIDMGR_APPLY=1, STUB_AUX_VIVO=1)
    assert r.returncode == 0, r.stderr
    assert _leer(proyecto)["apply"]["status"] == "ok", "el auxiliar no debe confundirse a si mismo con una corrida interrumpida"
    assert "en_updater=1" in (proyecto / "upgrade.llamado").read_text()


# --- actualizaciones en curso o interrumpidas --------------------------------

def test_con_el_auxiliar_vivo_el_servicio_no_toca_una_actualizacion_en_curso(entorno):
    proyecto, env, _ = entorno
    _estado(proyecto, aprobada=False, running=True)
    r = _ejecutar(env, SQUIDMGR_UPDATER=1, STUB_AUX_VIVO=1)
    assert r.returncode == 0
    assert _leer(proyecto)["apply"]["status"] == "running"


def test_sin_auxiliar_un_running_se_marca_como_interrumpido(entorno):
    proyecto, env, _ = entorno
    _estado(proyecto, aprobada=False, running=True)
    r = _ejecutar(env, SQUIDMGR_UPDATER=1)
    assert r.returncode == 0
    e = _leer(proyecto)
    assert e["apply"]["status"] == "error" and "interrumpi" in e["apply"]["log_tail"]


# --- bloqueo: una orden nunca se aplica dos veces ------------------------------

def test_con_el_bloqueo_tomado_nadie_mas_consume_la_orden(entorno):
    proyecto, env, _ = entorno
    _estado(proyecto)
    bloqueador = subprocess.Popen(["flock", "-x", str(proyecto / ".update.lock"), "sleep", "20"])
    try:
        time.sleep(0.5)
        for modo in ({}, {"SQUIDMGR_UPDATER": 1}):
            r = _ejecutar(env, **modo)
            assert r.returncode == 0
            assert _leer(proyecto)["request"]["approved"] is True
            assert not (proyecto / "upgrade.llamado").exists()
    finally:
        bloqueador.kill()
        bloqueador.wait()


def test_una_orden_programada_para_mas_tarde_no_se_toca(entorno):
    proyecto, env, _ = entorno
    _estado(proyecto, hace=-3600)  # dentro de una hora
    _ejecutar(env, SQUIDMGR_UPDATER=1)
    assert _leer(proyecto)["request"]["approved"] is True
    assert not any(l.startswith("run ") for l in _llamadas(entorno[2]))


def test_un_running_reciente_sin_auxiliar_no_se_da_por_muerto_en_el_servicio(entorno):
    # Caso real: el servicio se recrea a mitad de una actualizacion que aplica el temporizador del host
    # (de una version anterior, sin contenedor auxiliar). No es una corrida interrumpida.
    proyecto, env, _ = entorno
    _estado(proyecto, aprobada=False, running=True, running_hace=30)
    _ejecutar(env, SQUIDMGR_UPDATER=1)
    assert _leer(proyecto)["apply"]["status"] == "running"


def test_el_temporizador_del_host_sigue_marcando_de_inmediato_un_running_sin_auxiliar(entorno):
    # En el host la unidad es oneshot: un running al arrancar solo puede ser de una corrida anterior muerta.
    proyecto, env, _ = entorno
    _estado(proyecto, aprobada=False, running=True, running_hace=30)
    _ejecutar(env)
    assert _leer(proyecto)["apply"]["status"] == "error"


def test_la_actualizacion_sigue_la_rama_del_checkout_y_no_adivina_main(entorno):
    proyecto, env, _ = entorno
    _estado(proyecto)
    _ejecutar(env)
    assert "rama=rama-de-prueba" in (proyecto / "upgrade.llamado").read_text()


def test_en_contenedor_sin_poder_leer_el_repositorio_no_se_actualiza_a_ciegas(entorno, tmp_path):
    # Caso real: git se negaba a leer el proyecto montado ("dubious ownership"), la rama salia vacia, se
    # suponia "main" y un servidor que seguia otra rama acababa actualizado contra main.
    proyecto, env, _ = entorno
    _estado(proyecto)
    git_roto = tmp_path / "bin" / "git"
    git_roto.write_text('#!/bin/bash\necho "fatal: detected dubious ownership" >&2\nexit 128\n')
    git_roto.chmod(0o755)
    # Se pasa por el aplicador (SQUIDMGR_APPLY=1): es el que lee la rama.
    _estado(proyecto, aprobada=False, running=True)
    r = _ejecutar(env, SQUIDMGR_UPDATER=1, SQUIDMGR_APPLY=1)
    assert r.returncode == 0
    e = _leer(proyecto)
    assert e["apply"]["status"] == "error" and "no puede leer el repositorio" in e["apply"]["log_tail"]
    assert not (proyecto / "upgrade.llamado").exists()


def test_el_dockerfile_del_servicio_deja_a_git_confiar_en_el_proyecto():
    texto = (RAIZ / "updater" / "Dockerfile").read_text()
    assert "safe.directory" in texto and "/etc/systemd/system" in texto


# --- Invariantes de la definicion del servicio (docker-compose.yml, scripts) ----------------------------------

def _compose():
    yaml = pytest.importorskip("yaml")
    return yaml.safe_load((RAIZ / "docker-compose.yml").read_text(encoding="utf-8"))["services"]


def test_el_servicio_updater_existe_y_no_expone_ni_acepta_nada():
    u = _compose()["updater"]
    assert u["container_name"] == "squidmgr-updater"
    assert u["restart"] == "unless-stopped"
    assert "ports" not in u and "expose" not in u, "el updater no debe publicar ni exponer puertos"
    assert "no-new-privileges:true" in u["security_opt"]
    assert "healthcheck" in u and u["init"] is True


def test_solo_el_updater_monta_el_socket_de_docker_completo():
    # El backend (la parte expuesta a la web) habla con Docker por el proxy filtrado, nunca por el socket.
    servicios = _compose()
    for nombre, definicion in servicios.items():
        monta = any("docker.sock" in str(v) and ":ro" not in str(v) for v in definicion.get("volumes", []))
        if nombre == "updater":
            assert monta, "el updater necesita el socket para construir y recrear contenedores"
        else:
            assert not monta, f"{nombre} no debe montar el socket de Docker sin restriccion"
    assert servicios["backend"]["environment"]["DOCKER_HOST"] == "tcp://docker-socket-proxy:2375"


def test_ningun_otro_servicio_depende_del_updater():
    # Si el updater falla (red, build) el resto del stack tiene que seguir exactamente igual.
    for nombre, definicion in _compose().items():
        dep = definicion.get("depends_on", {})
        assert "updater" not in (dep if isinstance(dep, (list, dict)) else [])


def test_el_compose_de_imagenes_no_incluye_el_updater():
    assert "updater:" not in "\n".join(l.split("#")[0] for l in (RAIZ / "docker-compose.images.yml").read_text().splitlines())


def test_el_contexto_de_build_del_updater_solo_deja_pasar_lo_que_la_imagen_copia():
    ignore = (RAIZ / ".dockerignore").read_text().splitlines()
    assert "*" in ignore
    copiados = {"docker-autoupdate-check.sh", "upgrade-docker.sh", "backup-database.sh", "updater/entrypoint.sh"}
    assert copiados <= {l[1:] for l in ignore if l.startswith("!")}
    dockerfile = (RAIZ / "updater" / "Dockerfile").read_text()
    for f in ("docker-autoupdate-check.sh", "upgrade-docker.sh", "backup-database.sh", "updater/entrypoint.sh"):
        assert f in dockerfile


def test_upgrade_docker_actualiza_en_dos_fases_y_omite_el_temporizador_del_host_en_el_updater():
    t = (RAIZ / "upgrade-docker.sh").read_text()
    assert "docker compose config --services" in t
    assert "grep -vx 'updater'" in t and "docker compose up -d --build updater" in t
    assert 'SQUIDMGR_IN_UPDATER' in t


def test_install_sh_no_se_aborta_si_falla_el_temporizador_de_respaldo():
    t = (RAIZ / "install.sh").read_text()
    assert "instalar_temporizador_host()" in t
    assert "if instalar_temporizador_host; then" in t


def test_install_sh_construye_el_updater_en_una_segunda_fase_que_no_aborta_la_instalacion():
    t = (RAIZ / "install.sh").read_text()
    assert "grep -vx 'updater'" in t
    assert "docker compose up -d --build updater \\\n        || warn" in t


def test_los_ficheros_de_ejecucion_del_servicio_estan_en_gitignore():
    # Si no, `git status` sale sucio y install.sh se niega a re-ejecutarse ("Hay cambios locales sin confirmar").
    ignorados = (RAIZ / ".gitignore").read_text().splitlines()
    for f in ("/.update_state.json*", "/.update_heartbeat", "/.updater_alive", "/.update.lock",
              "backend/.update_state.json*", "backend/.update_heartbeat"):
        assert f in ignorados, f


def test_git_ignora_de_verdad_esos_ficheros(tmp_path):
    repo = tmp_path / "r"
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / ".gitignore").write_text((RAIZ / ".gitignore").read_text())
    (repo / "backend").mkdir()
    for f in (".update_heartbeat", ".updater_alive", ".update.lock", ".update_state.json", "backend/.update_heartbeat"):
        (repo / f).write_text("x")
    r = subprocess.run(["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=all"], capture_output=True, text=True)
    assert r.stdout.strip() == ".gitignore" or r.stdout.strip() == "?? .gitignore", r.stdout
