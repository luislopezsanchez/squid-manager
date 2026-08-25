#!/bin/bash
# ============================================
# SquidManager - Script de instalación
# ============================================
# Despliega SquidManager desde cero en un servidor Ubuntu/Debian.
# Uso (descarga, revisa y ejecuta: no lo canalices directo a bash):
#   wget https://raw.githubusercontent.com/luislopezsanchez/squid-manager/main/install.sh
#   less install.sh          # revisa qué va a hacer en tu servidor
#   chmod +x install.sh
#   sudo ./install.sh
# ============================================

set -euo pipefail

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[AVISO]${NC} $1"; }
fail()  { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# ============================================
# 1. Verificar requisitos
# ============================================
info "Verificando requisitos del sistema..."

# Comprobar root
if [[ $EUID -ne 0 ]]; then
    fail "Este script debe ejecutarse como root (sudo ./install.sh)"
fi

# Comprobar SO
if [[ ! -f /etc/os-release ]]; then
    fail "Sistema operativo no soportado"
fi
source /etc/os-release
if [[ "$ID" != "ubuntu" && "$ID" != "debian" ]]; then
    warn "SO detectado: $PRETTY_NAME. Se recomienda Ubuntu/Debian. Continuando..."
fi

# Comprobar arquitectura
ARCH=$(uname -m)
if [[ "$ARCH" != "x86_64" && "$ARCH" != "aarch64" ]]; then
    fail "Arquitectura no soportada: $ARCH (se requiere x86_64 o aarch64)"
fi

# ============================================
# 2. Instalar Docker si no está
# ============================================
if ! command -v docker &>/dev/null; then
    info "Docker no encontrado. Instalando Docker Engine..."
    apt-get update
    apt-get install -y ca-certificates curl gnupg

    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/$ID/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg

    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/$ID $(. /etc/os-release && echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list

    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    ok "Docker instalado correctamente"
else
    ok "Docker ya instalado: $(docker --version)"
fi

# Verificar Docker Compose
if ! docker compose version &>/dev/null; then
    fail "Docker Compose no disponible. Instala docker-compose-plugin"
fi
ok "Docker Compose: $(docker compose version)"

# ============================================
# 3. Obtener el código
# ============================================
# Dónde se instala.
#
# Si este script se está ejecutando desde dentro de un clon del repositorio, se
# usa ESE directorio. Antes la ruta estaba fija en /opt/squid-manager, así que
# quien clonaba en otro sitio y ejecutaba ./install.sh acababa con dos copias:
# el instalador descargaba una segunda a /opt y trabajaba allí, dejando el clon
# original sin usar y sin avisar de nada.
#
# Se puede forzar otra ruta con: INSTALL_DIR=/donde/sea ./install.sh
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ -n "${INSTALL_DIR:-}" ]]; then
    info "Ruta indicada por INSTALL_DIR: $INSTALL_DIR"
elif [[ -d "$SCRIPT_DIR/.git" && -f "$SCRIPT_DIR/docker-compose.yml" ]]; then
    INSTALL_DIR="$SCRIPT_DIR"
    info "Instalador ejecutado desde un clon: se usará $INSTALL_DIR"
else
    INSTALL_DIR="/opt/squid-manager"
fi

if [[ -d "$INSTALL_DIR/.git" ]]; then
    info "Actualizando SquidManager en $INSTALL_DIR..."
    cd "$INSTALL_DIR"
    # Un git pull sobre cambios locales los pisa sin avisar.
    if [[ -n "$(git status --porcelain)" ]]; then
        # El respaldo se deja junto al proyecto, no en /opt: con la ruta fija
        # acababa en un sitio que no tenía nada que ver con la instalación.
        BACKUP="${INSTALL_DIR%/}-backup-$(date +%Y%m%d-%H%M%S)"
        warn "Hay cambios locales sin confirmar. Copia de seguridad en $BACKUP"
        cp -a "$INSTALL_DIR" "$BACKUP"
        fail "Revisa tus cambios locales (git status) y vuelve a ejecutar el instalador."
    fi
    git pull origin main
else
    info "Clonando SquidManager a $INSTALL_DIR..."
    git clone https://github.com/luislopezsanchez/squid-manager.git "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi
ok "Código obtenido en $INSTALL_DIR"

# ============================================
# 4. Configurar .env
# ============================================
if [[ ! -f ".env" ]]; then
    # Un .env nuevo trae una DB_PASS nueva, y eso choca con una base que ya
    # exista: PostgreSQL solo aplica POSTGRES_PASSWORD cuando crea la base
    # vacía, así que un volumen heredado de otra instalación conserva su
    # contraseña anterior y el backend no puede entrar. Como Compose nombra los
    # volúmenes por el directorio del proyecto, basta con reinstalar en otra
    # ruta con el mismo nombre de carpeta para tropezar con esto.
    PGDATA_VOL="$(basename "$INSTALL_DIR")_pgdata"
    if docker volume inspect "$PGDATA_VOL" &>/dev/null; then
        warn "Existe el volumen de base de datos '$PGDATA_VOL' de una instalación anterior,"
        warn "pero no hay un .env con su contraseña."
        echo
        echo "  Si genero una contraseña nueva, PostgreSQL seguirá esperando la anterior"
        echo "  y el backend no podrá arrancar. Elige una de las dos:"
        echo
        echo "  1) Empezar de cero. BORRA LOS DATOS de esa instalación:"
        echo "       docker volume rm $PGDATA_VOL"
        echo "     y vuelve a ejecutar el instalador."
        echo
        echo "  2) Conservar los datos: recupera el .env anterior (con su DB_PASS),"
        echo "     déjalo en $INSTALL_DIR y vuelve a ejecutar el instalador."
        echo
        fail "Instalación detenida para no dejar el sistema a medias."
    fi

    info "Creando archivo .env desde .env.example..."
    cp .env.example .env

    # Generar SECRET_KEY aleatoria
    SECRET_KEY=$(openssl rand -hex 32 2>/dev/null || head -c 64 /dev/urandom | tr -dc 'a-f0-9')
    sed -i "s|SECRET_KEY=.*|SECRET_KEY=$SECRET_KEY|" .env

    # Generar contraseña aleatoria para DB
    DB_PASS=$(openssl rand -hex 16 2>/dev/null || head -c 32 /dev/urandom | tr -dc 'a-f0-9')
    sed -i "s|DB_PASS=.*|DB_PASS=$DB_PASS|" .env

    ok ".env creado con SECRET_KEY y DB_PASS aleatorias"
else
    # Un .env que viene de una versión anterior puede traer la clave de
    # ejemplo, con la que cualquiera puede firmarse un token de admin.
    if grep -qE '^SECRET_KEY=(|change-me-in-production|changeme-in-production-please|dev-secret-key-change-in-production-2026)$' .env; then
        warn "El .env tiene una SECRET_KEY insegura. Generando una nueva..."
        NEW_KEY=$(openssl rand -hex 32)
        sed -i "s|^SECRET_KEY=.*|SECRET_KEY=$NEW_KEY|" .env
        warn "SECRET_KEY regenerada: las sesiones abiertas se cerrarán."
    fi
    if grep -qE '^DB_PASS=(|squidpass123)$' .env; then
        warn "El .env usa la contraseña de base de datos de ejemplo. Cámbiala manualmente:"
        warn "  1) edita DB_PASS en .env"
        warn "  2) ALTER USER squid WITH PASSWORD '...' en PostgreSQL"
        warn "  3) docker compose up -d"
    fi
    ok ".env ya existe. Manteniendo el resto de la configuración."
fi

# PROJECT_DIR tiene que apuntar siempre al sitio real del proyecto: el backend
# lo usa para recrear el contenedor de Squid con Compose cuando cambias el
# puerto desde el panel. Se reescribe en cada ejecución por si el proyecto se
# movió de directorio desde la instalación anterior.
if grep -qE '^PROJECT_DIR=' .env; then
    sed -i "s|^PROJECT_DIR=.*|PROJECT_DIR=$INSTALL_DIR|" .env
else
    printf '\n# Ruta absoluta del proyecto (la usa el backend para invocar Compose)\nPROJECT_DIR=%s\n' "$INSTALL_DIR" >> .env
fi
ok "PROJECT_DIR apunta a $INSTALL_DIR"

# ============================================
# 5. Desplegar contenedores
# ============================================
info "Desplegando contenedores (la primera vez compila Squid, ~10-15 min)..."
docker compose up -d

ok "Contenedores desplegados"

# ============================================
# 6. Esperar al backend y recoger la contraseña del admin
# ============================================
# La contraseña del administrador la genera el backend la primera vez que
# arranca, y solo la escribe una vez en su log. Se espera a que termine para
# poder mostrarla en el resumen: sin esta espera, el resumen remitía a un
# comando que todavía no devolvía nada, y no había forma de distinguir «aún no
# ha arrancado» de «ha fallado».
echo ""
info "Esperando a que el backend termine de arrancar..."

ADMIN_PASS=""
BACKEND_LISTO=""

for _ in $(seq 1 90); do
    LOG_BACKEND="$(docker compose logs backend 2>/dev/null || true)"

    if grep -q "Administrador inicial" <<< "$LOG_BACKEND"; then
        ADMIN_PASS="$(grep -A3 'Administrador inicial' <<< "$LOG_BACKEND" \
            | grep 'Contrase' | tail -1 \
            | sed 's/.*Contrase[^:]*:[[:space:]]*//' | tr -d '\r')"
        BACKEND_LISTO="si"
        break
    fi

    # Arrancó bien pero sin crear administrador: ya existía de antes.
    if grep -q "Migraciones aplicadas" <<< "$LOG_BACKEND"; then
        BACKEND_LISTO="si"
        break
    fi

    if [[ "$(docker inspect squidmgr-backend --format '{{.State.Status}}' 2>/dev/null)" == "exited" ]]; then
        break
    fi

    sleep 2
done

# ============================================
# 7. Resumen
# ============================================
IP_SERVIDOR="$(hostname -I 2>/dev/null | awk '{print $1}')"
[[ -z "$IP_SERVIDOR" ]] && IP_SERVIDOR="localhost"
WEB_PORT_ACTUAL="$(grep -E '^WEB_PORT=' .env | cut -d= -f2 | tr -d ' \r')"
PROXY_PORT_ACTUAL="$(grep -E '^PROXY_PORT=' .env | cut -d= -f2 | tr -d ' \r')"

echo ""
info "Estado de los contenedores:"
docker compose ps

echo ""
if [[ -z "$BACKEND_LISTO" ]]; then
    warn "=========================================="
    warn "  El backend no llegó a arrancar"
    warn "=========================================="
    echo ""
    echo "  El resto de la instalación está hecha, pero el panel no funcionará"
    echo "  hasta resolverlo. Mira qué pasó con:"
    echo ""
    echo "      docker compose logs backend"
    echo ""
    exit 1
fi

ok "=========================================="
ok "  SquidManager instalado correctamente"
ok "=========================================="
echo ""
echo "  Panel web:   http://${IP_SERVIDOR}:${WEB_PORT_ACTUAL:-3000}"
echo "  Proxy:       ${IP_SERVIDOR}:${PROXY_PORT_ACTUAL:-3128}"
echo ""
echo "  Acceso al panel:"
echo "    Usuario:     admin"
if [[ -n "$ADMIN_PASS" ]]; then
    echo "    Contraseña:  $ADMIN_PASS"
    echo ""
    echo "    Se te pedirá cambiarla al entrar. Queda en el historial de esta"
    echo "    terminal: bórralo si el equipo no es solo tuyo."
else
    echo "    El usuario admin ya existía de una instalación anterior:"
    echo "    entra con la contraseña que ya tenías."
fi
echo ""
echo "  Siguiente paso — para filtrar HTTPS:"
echo "    El proxy descifra el tráfico HTTPS con su propio certificado, así que"
echo "    hay que instalarlo en los equipos cliente:"
echo ""
echo "        Panel web → Certificado CA → descargar"
echo ""
echo "    Hay instaladores listos para Windows, macOS e iOS. Sin ese"
echo "    certificado, los sitios HTTPS fallarán en los clientes."
echo ""
