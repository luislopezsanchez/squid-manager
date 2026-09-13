#!/bin/bash
# Actualiza una instalacion nativa (sin Docker) de SquidManager: backup
# previo de la base de datos, trae el codigo nuevo de forma segura, y
# vuelve a correr install-nativo.sh -que es quien sabe instalar pgvector,
# reparar sudoers/systemd/cron y reiniciar el servicio si hace falta- ya
# sobre el checkout recien actualizado.
#
# Por que un script aparte y no basta con re-correr install-nativo.sh
# directamente (que ya es seguro de re-ejecutar sobre una instalacion que
# existe, ver docs/actualizacion.md): install-nativo.sh hace git
# checkout/fetch/reset SOBRE SI MISMO como parte de la actualizacion. Si la
# version ya instalada difiere de la version destino en la logica del
# propio script -exactamente lo que paso al probar main -> pruebas en
# vivo, porque esta seccion de install-nativo.sh cambio entre una y otra-,
# bash sigue ejecutando en memoria el codigo VIEJO durante el resto de la
# corrida mientras los archivos de disco -el propio script incluido- ya
# cambiaron por debajo. Consecuencia real, observada en 172.30.36.63
# (2026-09-08): el aviso de "actualizado" nunca aparecio (se vio el de
# instalacion nueva), pgvector no se instalo, y el servicio nunca se
# reinicio de verdad -"systemctl enable --now" no hace nada si el servicio
# ya esta activo-: el backend siguio corriendo el codigo y las migraciones
# de ANTES del upgrade, sin ningun error visible que lo delatara.
# Corriendolo una segunda vez, ya con la version nueva instalada de punta a
# punta y sin salto de version del propio script por medio, todo funciono
# como se espera -asi se aislo que el bug era ese, y no otro-.
#
# Este script evita el problema por diseno: NUNCA se modifica a si mismo.
# El "git checkout/reset" de aqui abajo actua sobre INSTALL_DIR, pero quien
# ejecuta esos comandos es ESTE proceso, que no cambia bajo sus propios
# pies. Una vez que el checkout esta al dia, se invoca -como proceso
# nuevo, nunca "source"- el install-nativo.sh que quedo ahi: en ese
# momento ya es 100% la version destino, sin ambiguedad posible.
#
# Aun asi, el paso final de este script vuelve a comprobar el commit que
# /health reporta de verdad, y reintenta un reinicio si no coincide: en
# pruebas repetidas (con y sin INSTALL_DIR por defecto) el primer reinicio
# de install-nativo.sh, dentro de la misma corrida, a veces seguia
# sirviendo el commit anterior un rato -sin __pycache__ de por medio, ya
# descartado como causa- y un reinicio posterior, ya fuera del script,
# siempre mostro el commit correcto. No se pudo aislar la causa exacta con
# certeza suficiente para explicarla aca; verificar y reintentar es lo
# unico honesto de hacer sin esa certeza.
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[AVISO]${NC} $1"; }
fail()  { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }
paso()  { echo; echo -e "${BLUE}=== $1 ===${NC}"; }

# Mismo criterio que upgrade-docker.sh con PROJECT_DIR: si no se pasa
# INSTALL_DIR explicito por variable de entorno, se usa el directorio donde
# vive ESTE script -no una ruta fija-. No todas las instalaciones estan en
# /opt/squid-manager: la forma documentada de correr esto (bajar el script
# dentro del directorio de la instalacion y `sudo bash upgrade-nativo.sh`
# ahi) hace que el directorio del script sea siempre la ruta correcta. El
# chequeo de mas abajo ($INSTALL_DIR/.git) aborta con un mensaje claro si
# aun asi no es un checkout de SquidManager.
INSTALL_DIR="${INSTALL_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
BRANCH="${BRANCH:-main}"

[ -d "$INSTALL_DIR/.git" ] || fail "No hay una instalacion de SquidManager en $INSTALL_DIR (o no es un checkout git). Corre este script desde el directorio donde esta instalado SquidManager, o pasa la ruta con INSTALL_DIR=/tu/ruta. Para instalar desde cero usa install-nativo.sh, no este script."
[ -x "$INSTALL_DIR/install-nativo.sh" ] || fail "$INSTALL_DIR/install-nativo.sh no existe o no es ejecutable; no se puede completar la actualizacion."

# Comprobacion de modo ANTES de tocar nada (backup, git reset): el path
# /opt/squid-manager es el default de LOS DOS modos, asi que correr el que
# no toca es un error facil. Simetrico a la comprobacion de upgrade-docker.sh.
_MODO="$(sed -n 's/^DEPLOY_MODE=//p' "$INSTALL_DIR/.env" 2>/dev/null | head -1 | tr -d '[:space:]' | tr 'A-Z' 'a-z')"
if [ "$_MODO" = "docker" ]; then
    fail "El .env dice DEPLOY_MODE=docker: esta es una instalacion con Docker. Usa upgrade-docker.sh, no este script."
fi
if command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^squidmgr-'; then
    fail "Hay contenedores 'squidmgr-*' corriendo: esto parece una instalacion con Docker. Usa upgrade-docker.sh (para en su caso con 'docker compose down' si esta convirtiendo a nativo)."
fi
command -v systemctl >/dev/null 2>&1 || fail "No hay 'systemctl': una instalacion nativa se gobierna con systemd. Revisa que sea el modo correcto."

# --- Blindaje contra corte de SSH --------------------------------------------
# La recompilacion de Squid (install-nativo.sh, paso de build) tarda 10+ min.
# Corrido como `ssh host "bash upgrade-nativo.sh"`, si la conexion se cae el
# script recibe SIGHUP y muere a mitad: git YA actualizado, install-nativo.sh
# a medio correr -paquetes puestos, migraciones quiza aplicadas, servicio
# NO reiniciado o reiniciado sobre un build incompleto-. El checkout en disco
# queda por delante de lo que corre y sin una senal clara de que fallo. Caso
# real: un upgrade Docker en produccion quedo asi, y en una VM de prueba el
# script murio con "Remote side unexpectedly closed network connection".
# Para evitarlo el script se re-lanza desligado de la terminal (setsid,
# salida a un log) y esta primera invocacion sale enseguida diciendo como
# seguirlo. Opt-out: SQUIDMGR_UPGRADE_FOREGROUND=1 (util en tmux/screen o en
# consola local, donde no hay riesgo de corte).
if [ -z "${SQUIDMGR_UPGRADE_DETACHED:-}" ] && [ -z "${SQUIDMGR_UPGRADE_FOREGROUND:-}" ] \
        && command -v setsid >/dev/null 2>&1; then
    _LOG="$INSTALL_DIR/upgrade-nativo-$(date +%Y%m%d_%H%M%S).log"
    echo "La actualizacion corre en SEGUNDO PLANO para sobrevivir a un corte de SSH."
    echo "  Log:    $_LOG"
    echo "  Seguir: tail -f \"$_LOG\""
    echo "  Al terminar, el log dice si quedo OK. Primer plano: SQUIDMGR_UPGRADE_FOREGROUND=1 sudo -E bash \"$0\""
    SQUIDMGR_UPGRADE_DETACHED=1 setsid bash "$0" "$@" >"$_LOG" 2>&1 </dev/null &
    echo "  PID:    $!"
    exit 0
fi
# ---------------------------------------------------------------------------

cd "$INSTALL_DIR"

paso "1. Backup antes de actualizar"
if [ -x "$INSTALL_DIR/backup-database.sh" ]; then
    "$INSTALL_DIR/backup-database.sh" || warn "El backup fallo; se continua igual, pero revisa el motivo antes de confiar en el upgrade."
else
    warn "No se encontro backup-database.sh; se continua sin backup previo."
fi

paso "2. Trayendo el codigo nuevo (rama $BRANCH)"
# git 2.35.2+ se niega a operar sobre un repo cuyo dueno no es quien corre
# git ("detected dubious ownership"). Pasa cuando el checkout lo hizo un
# usuario de despliegue (o el propio APP_USER) y este script se corre como
# root, o al reves. Se declara el directorio como confiable antes de tocar
# nada -install-nativo.sh, que se invoca despues, hereda esta config del
# mismo usuario-. Idempotente: solo se agrega si no estaba.
git config --global --get-all safe.directory 2>/dev/null | grep -qxF "$INSTALL_DIR" \
    || git config --global --add safe.directory "$INSTALL_DIR"

# Mismo mecanismo, y el mismo bug real de fondo, que en upgrade-docker.sh:
# `git checkout` se niega a cambiar de rama si eso pisaria una modificacion
# local -aunque el `reset --hard` de abajo la fuera a descartar de todas
# formas-, y sin descartarla ANTES el script entero aborta. `git clean -fd`
# respeta .gitignore: no toca `.env` ni nada gitignored.
git checkout --quiet -- . 2>/dev/null || true
git clean -fdq
git fetch --all --quiet
git checkout --quiet "$BRANCH"
git reset --hard --quiet "origin/$BRANCH"

# __pycache__ esta en .gitignore, asi que "git clean -fd" (que respeta el
# .gitignore a proposito, para no llevarse .env ni node_modules/) nunca lo
# toca. Un .pyc viejo ahi puede quedar sirviendo al proceso reiniciado con
# codigo de ANTES del upgrade -visto en pruebas repetidas sobre el mismo
# checkout en 172.30.36.63-. Encontrar la causa exacta de cuando pasa no
# vale lo que cuesta: borrarlo es gratis y siempre correcto, porque Python
# lo regenera solo en el primer import.
find "$INSTALL_DIR/backend" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

ok "Codigo actualizado a $(git log --oneline -1)"

paso "3. Aplicando la actualizacion"
info "De aqui en mas continua install-nativo.sh de la version nueva (paquetes, pgvector, permisos, migraciones, reinicio de servicios)."
# INSTALL_DIR y BRANCH se pasan explicitos para que el comportamiento no
# dependa de que el entorno los tenga ya exportados -por ejemplo si este
# script se invoco con `sudo` sin `-E`-. install-nativo.sh vuelve a hacer
# su propio fetch/checkout/reset sobre el mismo commit al que ya lo
# dejamos: es un no-op (ya esta todo al dia), no un problema.
INSTALL_DIR="$INSTALL_DIR" BRANCH="$BRANCH" bash "$INSTALL_DIR/install-nativo.sh"

paso "4. Confirmando que el servicio quedo sirviendo el codigo nuevo"
# install-nativo.sh ya reinicia squidmanager (paso 10) y verifica que
# responda, pero eso solo confirma que ALGO responde en /health -no que sea
# el commit que se acaba de dejar en el checkout-. Visto en vivo mas de una
# vez, en mas de un checkout, con __pycache__ ya descartado como causa: el
# primer reinicio dentro de la misma corrida puede quedar sirviendo todavia
# el commit anterior un rato -no se pudo aislar la causa exacta con
# certeza, asi que en vez de dar el upgrade por bueno a ciegas, se verifica
# y se reintenta una vez si hace falta, que es lo unico honesto de hacer
# sin esa certeza-. Un restart mas tarde, ya fuera del script, siempre
# mostro el commit correcto.
if [ -f "$INSTALL_DIR/.env" ]; then
    WEB_PORT="$(grep -m1 '^WEB_PORT=' "$INSTALL_DIR/.env" 2>/dev/null | cut -d= -f2-)"
fi
WEB_PORT="${WEB_PORT:-3000}"

COMMIT_ESPERADO="$(git -C "$INSTALL_DIR" rev-parse --short HEAD)"
COMMIT_SERVIDO="$(curl -fsS -m 10 "http://127.0.0.1:${WEB_PORT}/health" 2>/dev/null | grep -oE '"commit":\s*"[^"]*"' | grep -oE '[0-9a-f]{7,}' || echo "")"

if [ "$COMMIT_SERVIDO" != "$COMMIT_ESPERADO" ]; then
    warn "El panel respondio con el commit '$COMMIT_SERVIDO', no '$COMMIT_ESPERADO'. Reintentando un reinicio."
    systemctl restart squidmanager
    sleep 5
    COMMIT_SERVIDO="$(curl -fsS -m 10 "http://127.0.0.1:${WEB_PORT}/health" 2>/dev/null | grep -oE '"commit":\s*"[^"]*"' | grep -oE '[0-9a-f]{7,}' || echo "")"
fi

echo
if [ "$COMMIT_SERVIDO" = "$COMMIT_ESPERADO" ]; then
    ok "El panel confirma que esta sirviendo $COMMIT_SERVIDO."
    echo
    echo "=================================================="
    echo " ACTUALIZACION COMPLETADA (rama $BRANCH, $COMMIT_ESPERADO)"
    echo "=================================================="
    echo " El navegador puede seguir mostrando la version anterior por cache:"
    echo " forza recarga (Ctrl+Shift+R) y volve a iniciar sesion."
else
    warn "El panel sigue reportando '$COMMIT_SERVIDO' en vez de '$COMMIT_ESPERADO' despues de reintentar. Revisa a mano: systemctl restart squidmanager && curl http://127.0.0.1:${WEB_PORT}/health"
    echo
    echo "=================================================="
    echo " LA ACTUALIZACION NO TERMINO BIEN"
    echo "=================================================="
    echo " Revisa: journalctl -u squidmanager -n 50"
    exit 1
fi
