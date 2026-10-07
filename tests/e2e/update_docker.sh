#!/bin/bash
# Prueba de extremo a extremo de "Actualizar ahora" en una instalacion DOCKER, en una maquina limpia.
#
# Por que existe: la actualizacion desde el panel depende de piezas que viven FUERA de los contenedores
# y que ningun test unitario ejercita (un temporizador del host que install.sh no instalaba en un
# servidor sin instalacion nativa previa, y que dejaba la orden pendiente para siempre). Esta prueba hace
# lo que hace un usuario, desde cero, y falla si la version no cambia:
#
#   1. instala con ./install.sh (el instalador oficial) desde una copia local del commit bajo prueba;
#   2. crea un commit nuevo en el "origen" y pulsa «Actualizar ahora» (API real del panel);
#   3. exige que se aplique (commit y estado), que el servicio `updater` quede sano y que el panel responda;
#   4. repite con un commit que cambia la imagen del propio servicio `updater` (se recrea a mitad de camino).
#
# Uso (como root, en una maquina limpia y desechable: instala Docker y deja el stack corriendo):
#   sudo bash tests/e2e/update_docker.sh /ruta/al/checkout/del/commit/bajo/prueba
#
# No usa GitHub: el "origen" es un repositorio bare local servido por `git daemon` (git://), para que los
# contenedores —que no ven las rutas del servidor— lo alcancen como alcanzarian GitHub; y la aprobacion se hace
# por la API del panel (que no consulta GitHub para aprobar). El INSTALL_DIR es /opt/squid-manager.
set -euo pipefail

SRC="${1:?uso: update_docker.sh /ruta/al/checkout}"
[ "$(id -u)" = "0" ] || { echo "ERROR: ejecutalo como root"; exit 1; }
INSTALL_DIR=/opt/squid-manager
[ ! -e "$INSTALL_DIR" ] || { echo "ERROR: $INSTALL_DIR ya existe: usa una maquina limpia"; exit 1; }

WORK="$(mktemp -d)"
ORIGIN="$WORK/origin.git"
CLAVE_ADMIN="E2e-Clave-12345"
TIMEOUT_ACTUALIZACION="${E2E_TIMEOUT:-900}"
export GIT_AUTHOR_NAME=e2e GIT_AUTHOR_EMAIL=e2e@localhost GIT_COMMITTER_NAME=e2e GIT_COMMITTER_EMAIL=e2e@localhost

paso() { echo; echo "=== $* ==="; }
# El PID se guarda en una variable: al terminar bien se borra $WORK (y con el su .pid) antes de que corra el trap.
parar_daemon() { if [ -n "${DAEMON_PID:-}" ]; then kill "$DAEMON_PID" 2>/dev/null || true; fi; }
trap parar_daemon EXIT
fallar() {
    echo; echo "ERROR E2E: $*" >&2
    echo "--- contenedores"; docker ps -a --format '{{.Names}}  {{.Status}}' 2>&1 | head -20
    echo "--- servicio updater"; docker logs --tail 40 squidmgr-updater 2>&1 | tail -40
    echo "--- estado de actualizacion"; cat "$INSTALL_DIR/.update_state.json" 2>&1 | head -60
    echo "--- temporizador del host"; systemctl status squidmanager-docker-autoupdate.timer --no-pager 2>&1 | head -8
    exit 1
}

# --- 1. Origen local con el commit bajo prueba -----------------------------------------------------
paso "Preparando el origen local con el commit bajo prueba"
git init -q --bare -b main "$ORIGIN"
git -C "$SRC" push -q "$ORIGIN" HEAD:refs/heads/main
# Servido por git:// en la IP del servidor: los contenedores la alcanzan por la red, como alcanzarian GitHub.
IP_SERVIDOR="$(hostname -I | awk '{print $1}')"
git daemon --reuseaddr --base-path="$WORK" --export-all --listen=0.0.0.0 --port=9418 \
    --pid-file="$WORK/daemon.pid" --detach "$WORK"
sleep 1
DAEMON_PID="$(cat "$WORK/daemon.pid" 2>/dev/null || true)"
ORIGIN_URL="git://$IP_SERVIDOR/origin.git"
git ls-remote "$ORIGIN_URL" >/dev/null || fallar "no se pudo leer el origen local por git://"
git clone -q -b main "$ORIGIN_URL" "$INSTALL_DIR"
git -C "$INSTALL_DIR" log --oneline -1

# --- 2. Instalacion limpia con el instalador oficial -----------------------------------------------
paso "Instalando con install.sh en una maquina limpia (la primera vez compila Squid, ~15 min)"
cd "$INSTALL_DIR"
./install.sh > "$WORK/install.log" 2>&1 || { tail -40 "$WORK/install.log"; fallar "install.sh termino con error"; }
sed 's/\x1b\[[0-9;]*m//g' "$WORK/install.log" | grep -E '^\[(OK|AVISO|ERROR)\]' | tail -12
grep -q "Servicio de actualizaciones (updater) en marcha" "$WORK/install.log" || fallar "el instalador no dejo el servicio updater en marcha"
# El fallo original: `install: cannot create regular file '/usr/local/lib/squidmanager/...': No such file or directory`.
if grep -q "cannot create regular file" "$WORK/install.log"; then fallar "el instalador no pudo crear los scripts del temporizador"; fi

WEB_PORT="$(grep -E '^WEB_PORT=' .env | cut -d= -f2 || true)"; WEB_PORT="${WEB_PORT:-3000}"
API="http://127.0.0.1:${WEB_PORT}/api"

paso "Esperando a que el panel responda"
for _ in $(seq 1 60); do
    docker exec squidmgr-backend curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1 && break
    sleep 5
done
VERSION_INICIAL="$(docker exec squidmgr-backend curl -fsS http://127.0.0.1:8000/health)"
echo "$VERSION_INICIAL"

paso "El servicio updater esta sano y deja su senal de vida"
for _ in $(seq 1 30); do
    [ "$(docker inspect -f '{{.State.Health.Status}}' squidmgr-updater 2>/dev/null)" = "healthy" ] && break
    sleep 5
done
[ "$(docker inspect -f '{{.State.Health.Status}}' squidmgr-updater)" = "healthy" ] || fallar "squidmgr-updater no esta healthy"
[ -s "$INSTALL_DIR/.updater_alive" ] || fallar "no hay .updater_alive"

# --- 3. Sesion de administrador ----------------------------------------------------------------------
paso "Entrando al panel como administrador"
./reset-admin-password.sh admin "$CLAVE_ADMIN" >/dev/null
TOKEN=""
login() {
    curl -fsS -X POST "$API/auth/login" -d username=admin --data-urlencode "password=$1" 2>/dev/null \
        | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d.get("access_token",""),d.get("must_change_password",False))'
}
read -r TOKEN CAMBIAR < <(login "$CLAVE_ADMIN")
[ -n "$TOKEN" ] || fallar "no se pudo iniciar sesion"
if [ "$CAMBIAR" = "True" ]; then
    curl -fsS -X PUT "$API/admins/change-password" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
        -d "{\"current_password\":\"$CLAVE_ADMIN\",\"new_password\":\"${CLAVE_ADMIN}-nueva\"}" >/dev/null
    CLAVE_ADMIN="${CLAVE_ADMIN}-nueva"
    read -r TOKEN _ < <(login "$CLAVE_ADMIN")
fi
estado() {
    curl -fsS "$API/update/estado" -H "Authorization: Bearer $TOKEN" | python3 -c '
import sys, json
d = json.load(sys.stdin)
print("{} {} {}".format(d["request"]["approved"], d["apply"]["status"], (d["check"]["local_commit"] or "")[:7]))'
}

# --- 4. Actualizaciones --------------------------------------------------------------------------------
actualizar_con() {  # $1: descripcion  $2: archivo a tocar  $3: texto a anadir
    local desc="$1" archivo="$2" texto="$3" nuevo clon="$WORK/clon"
    paso "Actualizacion desde el panel: $desc"
    rm -rf "$clon"; git clone -q -b main "$ORIGIN" "$clon"
    printf '%s\n' "$texto" >> "$clon/$archivo"
    git -C "$clon" add -A
    git -C "$clon" commit -q -m "e2e: $desc"
    git -C "$clon" push -q origin main
    nuevo="$(git -C "$clon" rev-parse --short HEAD)"
    echo "commit nuevo en el origen: $nuevo"

    curl -fsS -X POST "$API/update/aprobar" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{}' >/dev/null \
        || fallar "el panel rechazo «Actualizar ahora»"
    local t0 ultimo="" actual
    t0="$(date +%s)"
    while [ $(( $(date +%s) - t0 )) -lt "$TIMEOUT_ACTUALIZACION" ]; do
        actual="$(estado 2>/dev/null || true)"
        [ -n "$actual" ] && [ "$actual" != "$ultimo" ] && { echo "+$(( $(date +%s) - t0 ))s  pendiente/estado/commit = $actual"; ultimo="$actual"; }
        if [ "$actual" = "False ok $nuevo" ]; then
            echo "OK: aplicada en $(( $(date +%s) - t0 ))s"
            break
        fi
        case "$actual" in "False error "*) fallar "la actualizacion termino en error";; esac
        sleep 5
    done
    [ "$actual" = "False ok $nuevo" ] || fallar "«Actualizar ahora» no se aplico en ${TIMEOUT_ACTUALIZACION}s (ultimo estado: $actual)"

    [ "$(git -C "$INSTALL_DIR" rev-parse --short HEAD)" = "$nuevo" ] || fallar "el checkout no esta en el commit nuevo"
    for _ in $(seq 1 30); do
        docker exec squidmgr-backend curl -fsS http://127.0.0.1:8000/health 2>/dev/null | grep -q "\"commit\":\"$nuevo\"" && break
        sleep 4
    done
    docker exec squidmgr-backend curl -fsS http://127.0.0.1:8000/health | grep -q "\"commit\":\"$nuevo\"" || fallar "el backend no corre el commit nuevo"
    for _ in $(seq 1 30); do
        [ "$(docker inspect -f '{{.State.Health.Status}}' squidmgr-updater 2>/dev/null)" = "healthy" ] && break
        sleep 4
    done
    [ "$(docker inspect -f '{{.State.Health.Status}}' squidmgr-updater)" = "healthy" ] || fallar "squidmgr-updater no volvio a estar healthy"
    docker ps -a --format '{{.Names}}' | grep -qx squidmgr-updater-run && fallar "quedo un contenedor auxiliar sin borrar" || true
}

actualizar_con "commit inocuo" "CHANGELOG.md" "<!-- e2e 1 -->"
actualizar_con "commit que cambia la imagen del propio updater (se recrea a mitad de camino)" "updater/entrypoint.sh" "# e2e 2: fuerza reconstruir la imagen del updater"

paso "OK: instalacion limpia + 2 actualizaciones desde el panel aplicadas correctamente"
rm -rf "$WORK"
