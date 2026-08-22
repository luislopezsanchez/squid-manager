#!/bin/bash
# ============================================
# SquidManager - Script de instalación
# ============================================
# Despliega SquidManager desde cero en un servidor Ubuntu/Debian.
# Uso:
#   curl -fsSL https://raw.githubusercontent.com/luislopezsanchez/squid-manager/main/install.sh | bash
#   # o descargar y ejecutar:
#   wget https://raw.githubusercontent.com/luislopezsanchez/squid-manager/main/install.sh
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
INSTALL_DIR="/opt/squid-manager"

if [[ -d "$INSTALL_DIR/.git" ]]; then
    info "Actualizando SquidManager en $INSTALL_DIR..."
    cd "$INSTALL_DIR"
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
    warn ".env ya existe. Manteniendo configuración actual."
fi

# ============================================
# 5. Desplegar contenedores
# ============================================
info "Desplegando contenedores (la primera vez compila Squid, ~10-15 min)..."
docker compose up -d

ok "Contenedores desplegados"

# ============================================
# 6. Mostrar estado
# ============================================
echo ""
info "Estado de los contenedores:"
docker compose ps

echo ""
ok "=========================================="
ok "  SquidManager instalado correctamente"
ok "=========================================="
echo ""
echo "  Panel web:   http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'localhost'):3000"
echo "  API docs:    http://localhost:8000/docs"
echo "  Proxy:       localhost:3128"
echo ""
echo "  Credenciales por defecto:"
echo "    Admin panel:  admin / admin123"
echo "    Usuario proxy: testuser / test123"
echo ""
warn "  IMPORTANTE: cambia las credenciales por defecto inmediatamente."
echo ""
info "  Para ver el progreso de la compilación de Squid:"
echo "    docker compose logs -f squid"
echo ""
info "  Cuando veas 'Accepting HTTP Socket connections', está listo."
