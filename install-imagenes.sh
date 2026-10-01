#!/bin/bash
# ============================================
# SquidManager - Instalacion con Docker usando imagenes ya construidas
# ============================================
# Alternativa rapida a install.sh: en vez de clonar el repositorio y compilar Squid y el panel en tu
# servidor (15-30 minutos), descarga las imagenes publicadas en ghcr.io (unos minutos) y las arranca.
#
# Uso:
#   curl -fsSL https://raw.githubusercontent.com/luislopezsanchez/squid-manager/main/install-imagenes.sh | sudo bash
#   (o descargalo, revisalo con less y ejecutalo: sudo bash install-imagenes.sh)
#
# Variables opcionales:
#   SQUIDMGR_DIR=/opt/squid-manager     donde se guardan docker-compose.yml y .env
#   SQUIDMANAGER_VERSION=latest         etiqueta de las imagenes (por ejemplo 1.0.1)
#   WEB_PORT=3000  PROXY_PORT=3128      puertos publicados
#   SQUIDMANAGER_REGISTRY=...           solo forks o pruebas: otro registro de imagenes
#
# Diferencia con install.sh: no hay copia del repositorio (.git), asi que la pantalla Actualizaciones del
# panel no puede aplicar versiones nuevas. Se actualiza con:
#   cd /opt/squid-manager && sudo docker compose pull && sudo docker compose up -d
# Ver docs/docker-imagenes.md.
# ============================================

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info() { echo -e "${BLUE}[INFO]${NC} $1"; }
ok()   { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[AVISO]${NC} $1"; }
fail() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

DIR="${SQUIDMGR_DIR:-/opt/squid-manager}"
VERSION="${SQUIDMANAGER_VERSION:-latest}"
BASE_RAW="https://raw.githubusercontent.com/luislopezsanchez/squid-manager/main"
# Para pruebas: una ruta local en lugar de la URL (la usa el CI).
FUENTE="${SQUIDMGR_FUENTE:-$BASE_RAW}"

[[ $EUID -eq 0 ]] || fail "Ejecuta este script como root (sudo)."
command -v docker >/dev/null 2>&1 || fail "Docker no esta instalado. Instalalo primero: https://docs.docker.com/engine/install/"
docker compose version >/dev/null 2>&1 || fail "Falta 'docker compose' (plugin v2). Instalalo: https://docs.docker.com/compose/install/"
command -v curl >/dev/null 2>&1 || fail "Falta curl."

obtener() {
    # $1 = nombre del fichero en el repositorio, $2 = destino
    if [[ "$FUENTE" == http* ]]; then
        curl -fsSL "$FUENTE/$1" -o "$2" || fail "No se pudo descargar $1 desde $FUENTE"
    else
        cp "$FUENTE/$1" "$2" || fail "No se encuentra $FUENTE/$1"
    fi
}

mkdir -p "$DIR"
cd "$DIR"

# --- docker-compose.yml (se descarga con ESE nombre: el panel lo usa al cambiar el puerto) ---
if [[ -f docker-compose.yml ]]; then
    warn "Ya existe docker-compose.yml en $DIR: se conserva tal cual."
    warn "Para renovarlo con la ultima version: sudo curl -fsSL $BASE_RAW/docker-compose.images.yml -o $DIR/docker-compose.yml"
else
    info "Descargando docker-compose.yml..."
    obtener docker-compose.images.yml docker-compose.yml
    ok "docker-compose.yml descargado"
fi

# --- .env con secretos aleatorios ---
if [[ ! -f .env ]]; then
    info "Creando .env con claves aleatorias..."
    obtener .env.example .env
    SECRET_KEY="$(openssl rand -hex 32)"; DB_PASS="$(openssl rand -hex 16)"; DATA_KEY="$(openssl rand -hex 32)"
    sed -i "s|^SECRET_KEY=.*|SECRET_KEY=$SECRET_KEY|; s|^DB_PASS=.*|DB_PASS=$DB_PASS|; s|^DATA_KEY=.*|DATA_KEY=$DATA_KEY|" .env
    [[ -n "${WEB_PORT:-}" ]]   && sed -i "s|^WEB_PORT=.*|WEB_PORT=$WEB_PORT|" .env
    [[ -n "${PROXY_PORT:-}" ]] && sed -i "s|^PROXY_PORT=.*|PROXY_PORT=$PROXY_PORT|" .env
    ok ".env creado"
else
    warn "Ya existe .env: se conserva tal cual (con sus claves)."
fi
if grep -qE '^PROJECT_DIR=' .env; then
    sed -i "s|^PROJECT_DIR=.*|PROJECT_DIR=$DIR|" .env
else
    printf '\n# Ruta absoluta del proyecto (la usa el backend para invocar Compose)\nPROJECT_DIR=%s\n' "$DIR" >> .env
fi
if grep -qE '^SQUIDMANAGER_VERSION=' .env; then
    sed -i "s|^SQUIDMANAGER_VERSION=.*|SQUIDMANAGER_VERSION=$VERSION|" .env
else
    printf '\n# Etiqueta de las imagenes de ghcr.io/luislopezsanchez (latest o una version, por ejemplo 1.0.1)\nSQUIDMANAGER_VERSION=%s\n' "$VERSION" >> .env
fi
if [[ -n "${SQUIDMANAGER_REGISTRY:-}" ]]; then
    # Solo para forks o pruebas: otro registro de imagenes distinto de ghcr.io/luislopezsanchez.
    if grep -qE '^SQUIDMANAGER_REGISTRY=' .env; then
        sed -i "s|^SQUIDMANAGER_REGISTRY=.*|SQUIDMANAGER_REGISTRY=$SQUIDMANAGER_REGISTRY|" .env
    else
        printf 'SQUIDMANAGER_REGISTRY=%s\n' "$SQUIDMANAGER_REGISTRY" >> .env
    fi
fi
chmod 600 .env

# --- imagenes y arranque ---
info "Descargando las imagenes (version: $VERSION)..."
docker compose pull || fail "No se pudieron descargar las imagenes. Si el servidor sale por un proxy, mira docs/instalacion-tras-proxy.md."
info "Arrancando los servicios..."
docker compose up -d --no-build

info "Esperando a que el panel responda..."
WEB_PORT_ACTUAL="$(grep -E '^WEB_PORT=' .env | cut -d= -f2 | tr -d ' \r')"
WEB_PORT_ACTUAL="${WEB_PORT_ACTUAL:-3000}"
LISTO=""
for _ in $(seq 1 90); do
    if curl -fsS -m 5 "http://127.0.0.1:${WEB_PORT_ACTUAL}/health" >/dev/null 2>&1; then LISTO="si"; break; fi
    sleep 2
done
[[ -n "$LISTO" ]] || { docker compose ps; fail "El panel no respondio a tiempo. Revisa: cd $DIR && docker compose logs backend"; }

ADMIN_PASS="$(docker compose logs backend 2>/dev/null | grep -A3 'Administrador inicial' | grep 'Contrase' | tail -1 | sed 's/.*Contrase[^:]*:[[:space:]]*//' | tr -d '\r' || true)"
IP_SERVIDOR="$(hostname -I 2>/dev/null | awk '{print $1}')"

echo ""
echo "=================================================="
echo " SquidManager instalado (imagenes ${VERSION})"
echo "=================================================="
echo "  Panel web:   http://${IP_SERVIDOR:-IP_DEL_SERVIDOR}:${WEB_PORT_ACTUAL}"
echo "  Usuario:     admin"
if [[ -n "$ADMIN_PASS" ]]; then
    echo "  Contrasena:  $ADMIN_PASS   (te pedira cambiarla al entrar)"
else
    echo "  Contrasena:  ya existia un administrador de una instalacion anterior"
fi
echo ""
echo "  Actualizar:  cd $DIR && sudo docker compose pull && sudo docker compose up -d"
echo "  Logs:        cd $DIR && docker compose logs -f backend"
echo ""
