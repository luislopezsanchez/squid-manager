#!/bin/bash
# Prueba de extremo a extremo de "Actualizar ahora" en una instalacion NATIVA (sin Docker), en una maquina limpia.
#
# Hace lo que hace un usuario, desde cero, y falla si la version no cambia:
#   1. instala con ./install-nativo.sh (el instalador oficial) desde una copia local del commit bajo prueba;
#   2. crea un commit nuevo en el "origen" y pulsa «Actualizar ahora» (API real del panel);
#   3. exige que se aplique (commit y estado) y que el panel responda;
#   4. repite con otro commit.
#
# Uso (como root, en una maquina limpia y desechable: instala PostgreSQL, Squid y nginx):
#   sudo bash tests/e2e/update_native.sh /ruta/al/checkout/del/commit/bajo/prueba
#
# No usa GitHub: el "origen" es un repositorio bare local (REPO_URL), y la aprobacion se hace por la API del
# panel (que no consulta GitHub para aprobar).
set -euo pipefail

SRC="${1:?uso: update_native.sh /ruta/al/checkout}"
[ "$(id -u)" = "0" ] || { echo "ERROR: ejecutalo como root"; exit 1; }
INSTALL_DIR=/opt/squid-manager
[ ! -e "$INSTALL_DIR" ] || { echo "ERROR: $INSTALL_DIR ya existe: usa una maquina limpia"; exit 1; }
[ ! -e /etc/squid/squid.conf ] || { echo "ERROR: ya hay un Squid instalado: usa una maquina limpia"; exit 1; }

WORK="$(mktemp -d)"
ORIGIN="$WORK/origin.git"
CLAVE_ADMIN="E2e-Clave-12345"
TIMEOUT_ACTUALIZACION="${E2E_TIMEOUT:-900}"
export GIT_AUTHOR_NAME=e2e GIT_AUTHOR_EMAIL=e2e@localhost GIT_COMMITTER_NAME=e2e GIT_COMMITTER_EMAIL=e2e@localhost

paso() { echo; echo "=== $* ==="; }
fallar() {
    echo; echo "ERROR E2E: $*" >&2
    echo "--- servicios"; systemctl is-active squid squidmanager nginx postgresql 2>&1 | tr '\n' ' '; echo
    echo "--- estado de actualizacion"; cat "$INSTALL_DIR/backend/.update_state.json" 2>&1 | head -60
    echo "--- temporizador"; systemctl status squidmanager-autoupdate.timer --no-pager 2>&1 | head -8
    echo "--- registro del panel"; journalctl -u squidmanager --no-pager -n 30 2>&1 | tail -30
    exit 1
}

# --- 1. Origen local con el commit bajo prueba -----------------------------------------------------
paso "Preparando el origen local con el commit bajo prueba"
git init -q --bare -b main "$ORIGIN"
git -C "$SRC" push -q "$ORIGIN" HEAD:refs/heads/main

# --- 2. Instalacion limpia con el instalador oficial -----------------------------------------------
paso "Instalando con install-nativo.sh en una maquina limpia"
REPO_URL="file://$ORIGIN" BRANCH=main INSTALL_DIR="$INSTALL_DIR" bash "$SRC/install-nativo.sh" > "$WORK/install.log" 2>&1 \
    || { tail -40 "$WORK/install.log"; fallar "install-nativo.sh termino con error"; }
sed 's/\x1b\[[0-9;]*m//g' "$WORK/install.log" | grep -E '^\[(OK|AVISO|ERROR)\]' | tail -10
git -C "$INSTALL_DIR" log --oneline -1
cd "$INSTALL_DIR"

WEB_PORT="$(grep -E '^WEB_PORT=' .env | cut -d= -f2 || true)"; WEB_PORT="${WEB_PORT:-3000}"
API="http://127.0.0.1:${WEB_PORT}/api"
SALUD() { curl -fsS http://127.0.0.1:8000/health; }

paso "Esperando a que el panel responda"
for _ in $(seq 1 60); do SALUD >/dev/null 2>&1 && break; sleep 5; done
SALUD; echo
systemctl is-active --quiet squidmanager-autoupdate.timer || fallar "el temporizador de actualizaciones no esta activo"

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
    for _ in $(seq 1 30); do SALUD 2>/dev/null | grep -q "\"commit\":\"$nuevo\"" && break; sleep 4; done
    SALUD | grep -q "\"commit\":\"$nuevo\"" || fallar "el backend no corre el commit nuevo"
    systemctl is-active --quiet squid squidmanager nginx postgresql || fallar "algun servicio no quedo activo tras actualizar"
}

actualizar_con "primer commit nuevo" "CHANGELOG.md" "<!-- e2e 1 -->"
actualizar_con "segundo commit nuevo" "CHANGELOG.md" "<!-- e2e 2 -->"

paso "OK: instalacion nativa limpia + 2 actualizaciones desde el panel aplicadas correctamente"
rm -rf "$WORK"
