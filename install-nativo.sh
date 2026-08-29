#!/bin/bash
# ============================================
# SquidManager - Instalacion nativa (sin Docker)
# ============================================
# Despliega SquidManager directamente sobre Ubuntu/Debian, con Squid, el panel
# y PostgreSQL corriendo como servicios del sistema.
#
# Uso (descarga, revisa y ejecuta: no lo canalices directo a bash):
#   wget https://raw.githubusercontent.com/luislopezsanchez/squid-manager/main/install-nativo.sh
#   less install-nativo.sh    # revisa que va a hacer en tu servidor
#   chmod +x install-nativo.sh
#   sudo ./install-nativo.sh
#
# Variables opcionales:
#   BRANCH=main WEB_PORT=3000 PROXY_PORT=3128 sudo -E ./install-nativo.sh
# ============================================

set -euo pipefail

# Colores para output
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC} $1"; }
ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[AVISO]${NC} $1"; }
fail()  { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }
paso()  { echo; echo -e "${BLUE}=== $1 ===${NC}"; }

# ============================================
# Parametros
# ============================================
REPO_URL="${REPO_URL:-https://github.com/luislopezsanchez/squid-manager.git}"
BRANCH="${BRANCH:-main}"
INSTALL_DIR="${INSTALL_DIR:-/opt/squid-manager}"
APP_USER="${APP_USER:-squidmgr}"
WEB_PORT="${WEB_PORT:-3000}"
PROXY_PORT="${PROXY_PORT:-3128}"
DB_NAME="${DB_NAME:-squidmanager}"
DB_USER="${DB_USER:-squid}"
API_PORT="${API_PORT:-8000}"

SQUID_BIN="/usr/sbin/squid"
CERTGEN="/usr/lib/squid/security_file_certgen"
CA_DIR="/etc/squid/ssl_cert"
CRTD_DIR="/var/lib/ssl_crtd/db"

# ============================================
# 1. Requisitos
# ============================================
paso "1. Comprobando requisitos"

[ "$(id -u)" -eq 0 ] || fail "Ejecuta este script como root (sudo)."

[ -f /etc/os-release ] || fail "No se pudo identificar el sistema operativo."
. /etc/os-release
case "${ID:-}${ID_LIKE:-}" in
    *debian*|*ubuntu*) ok "Sistema: ${PRETTY_NAME}" ;;
    *) fail "Solo se admite Debian/Ubuntu. Detectado: ${PRETTY_NAME:-desconocido}" ;;
esac

[ "$(uname -m)" = "x86_64" ] || warn "Arquitectura $(uname -m): no probada, se continua."

if command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^squidmgr-'; then
    fail "Hay contenedores de SquidManager corriendo. Esta instalacion es la alternativa a Docker, no un complemento: parala antes con 'docker compose down'."
fi

# ============================================
# 2. Paquetes del sistema
# ============================================
paso "2. Instalando paquetes"

export DEBIAN_FRONTEND=noninteractive
# needrestart reinicia systemd-resolved en cuanto termina el apt, y el clon
# del paso 4 se queda sin DNS ("Could not resolve host: github.com").
# Suspenderlo aqui no deja nada a medias: los servicios que instalamos se
# arrancan explicitamente en el paso 10.
export NEEDRESTART_MODE=a
export NEEDRESTART_SUSPEND=1
apt-get update -qq

# squid-openssl, NO squid: el paquete 'squid' a secas es la variante GnuTLS,
# que no trae SSL bump ni el generador de certificados. Se comprueba mas abajo.
PAQUETES=(
    squid-openssl squid-langpack
    postgresql
    python3 python3-venv python3-pip python3-bcrypt python3-ldap3
    nginx
    nodejs npm
    # apache2-utils trae htpasswd, que es con lo que el panel genera el hash de
    # cada usuario del proxy. Sin el, crear un usuario falla y el mensaje ni
    # siquiera tiene sentido en esta instalacion ("reconstruye la imagen").
    apache2-utils
    openssl ca-certificates logrotate cron git curl
)
info "Paquetes: ${PAQUETES[*]}"
apt-get install -y -qq "${PAQUETES[@]}" >/dev/null || fail "No se pudieron instalar los paquetes."
ok "Paquetes instalados"

# Squid tiene que estar compilado con OpenSSL o el SSL bump del panel no
# funcionara, y el fallo aparecera mucho mas tarde y sin relacion aparente.
OPCIONES="$($SQUID_BIN -v 2>&1 || true)"
echo "$OPCIONES" | grep -q -- "--with-openssl" || fail "El Squid instalado no tiene --with-openssl. Instala squid-openssl."
[ -x "$CERTGEN" ] || fail "Falta $CERTGEN: el paquete de Squid no trae el generador de certificados."
ok "Squid $($SQUID_BIN -v 2>&1 | head -1 | grep -oE '[0-9]+\.[0-9]+' | head -1) con SSL bump"

# Binarios que el backend ejecuta en tiempo de ejecucion. Se comprueban aqui a
# proposito: si falta alguno, es mejor que la instalacion se pare ahora que
# descubrirlo el dia que alguien intente crear un usuario y reciba un error que
# no dice nada util.
for BIN in htpasswd openssl; do
    command -v "$BIN" >/dev/null 2>&1 || fail "Falta el comando '$BIN', que el panel necesita en marcha."
done
ok "Herramientas del panel disponibles (htpasswd, openssl)"

NODE_MAJOR="$(node -v 2>/dev/null | sed 's/^v//' | cut -d. -f1 || echo 0)"
if [ "${NODE_MAJOR:-0}" -lt 18 ]; then
    warn "Node ${NODE_MAJOR} es demasiado antiguo para compilar el panel; instalando Node 20."
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - >/dev/null 2>&1 \
        || fail "No se pudo anadir el repositorio de Node 20."
    apt-get install -y -qq nodejs >/dev/null || fail "No se pudo instalar Node 20."
fi
ok "Node $(node -v)"

# ============================================
# 3. Usuarios
# ============================================
paso "3. Creando usuarios del sistema"

# 'proxy' viene de base-passwd, pero puede faltar si alguien lo borro.
getent group proxy >/dev/null || groupadd -r -g 13 proxy
id proxy >/dev/null 2>&1 || useradd -r -u 13 -g proxy -s /usr/sbin/nologin -d /nonexistent proxy
ok "Usuario proxy: uid=$(id -u proxy) gid=$(id -g proxy)"

# El panel corre con su propio usuario, cuyo grupo primario es 'proxy'. Asi
# puede escribir los ficheros que Squid necesita leer (htpasswd, LDAP) sin
# tener que hacer chown, que exigiria ser root.
if ! id "$APP_USER" >/dev/null 2>&1; then
    useradd -r -g proxy -s /usr/sbin/nologin -d "$INSTALL_DIR" "$APP_USER"
fi
ok "Usuario del panel: $APP_USER (grupo primario: $(id -gn "$APP_USER"))"

# ============================================
# 4. Codigo
# ============================================
paso "4. Obteniendo el codigo"

if [ -d "$INSTALL_DIR/.git" ]; then
    info "Ya existe un checkout en $INSTALL_DIR; actualizando a $BRANCH"
    git -C "$INSTALL_DIR" fetch --all --quiet
    git -C "$INSTALL_DIR" checkout --quiet "$BRANCH"
    git -C "$INSTALL_DIR" reset --hard --quiet "origin/$BRANCH"
else
    mkdir -p "$(dirname "$INSTALL_DIR")"
    # Aunque needrestart este suspendido, la resolucion puede tardar un
    # instante en estar lista tras instalar paquetes de red. Se reintenta
    # antes de rendirse: fallar aqui deja la maquina a medias.
    CLONADO=0
    for INTENTO in 1 2 3 4 5; do
        if git clone --quiet --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR" 2>/dev/null; then
            CLONADO=1
            break
        fi
        rm -rf "$INSTALL_DIR"
        info "Clon fallido (intento $INTENTO/5); reintentando en 5 s..."
        sleep 5
    done
    [ "$CLONADO" = "1" ] || fail "No se pudo clonar $REPO_URL (rama $BRANCH) tras 5 intentos."
fi
ok "Codigo en $INSTALL_DIR ($(git -C "$INSTALL_DIR" rev-parse --short HEAD))"

# ============================================
# 5. Base de datos
# ============================================
paso "5. Configurando PostgreSQL"

systemctl enable --now postgresql >/dev/null 2>&1 || true

DB_PASS="${DB_PASS:-$(openssl rand -hex 16)}"

if sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1; then
    info "El rol $DB_USER ya existe; se actualiza su contrasena."
    sudo -u postgres psql -qc "ALTER ROLE \"$DB_USER\" WITH LOGIN PASSWORD '$DB_PASS';" >/dev/null
else
    sudo -u postgres psql -qc "CREATE ROLE \"$DB_USER\" WITH LOGIN PASSWORD '$DB_PASS';" >/dev/null
fi

if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1; then
    sudo -u postgres createdb -O "$DB_USER" "$DB_NAME"
fi
sudo -u postgres psql -qc "ALTER DATABASE \"$DB_NAME\" OWNER TO \"$DB_USER\";" >/dev/null
ok "Base de datos $DB_NAME lista (usuario $DB_USER)"

# ============================================
# 6. Squid
# ============================================
paso "6. Preparando Squid"

systemctl stop squid >/dev/null 2>&1 || true

mkdir -p "$CA_DIR" /var/log/squid /var/spool/squid /var/lib/ssl_crtd

# La CA con la que Squid firma los certificados que genera al interceptar.
if [ ! -f "$CA_DIR/squid-ca.crt" ] || [ ! -f "$CA_DIR/squid-ca.key" ]; then
    info "Generando la CA raiz de Squid (4096 bits, 10 anos)"
    openssl genrsa -out "$CA_DIR/squid-ca.key" 4096 2>/dev/null
    openssl req -new -x509 -key "$CA_DIR/squid-ca.key" -out "$CA_DIR/squid-ca.crt" \
        -days 3650 -subj "/C=US/ST=Proxy/L=Manager/O=SquidManager/CN=SquidManager CA" \
        -extensions v3_ca 2>/dev/null
    ok "CA generada en $CA_DIR/squid-ca.crt"
else
    ok "La CA ya existia; se conserva"
fi
chmod 600 "$CA_DIR/squid-ca.key"; chmod 644 "$CA_DIR/squid-ca.crt"
chown proxy:proxy "$CA_DIR/squid-ca.crt" "$CA_DIR/squid-ca.key"

# Base de certificados dinamicos. El directorio DEBE pertenecer a proxy: el
# helper hereda el usuario de Squid y si es de root no puede escribir su
# indice, que era el origen de los errores "Database search failure".
if [ ! -f "$CRTD_DIR/index.txt" ]; then
    info "Inicializando la base de certificados dinamicos"
    rm -rf "$CRTD_DIR"
    "$CERTGEN" -c -s "$CRTD_DIR" -M 4MB >/dev/null
fi
chown -R proxy:proxy /var/lib/ssl_crtd
chmod -R u+rwX /var/lib/ssl_crtd
ok "Base de certificados en $CRTD_DIR"

# Helper de autenticacion (htpasswd local + LDAP).
install -o root -g root -m 755 "$INSTALL_DIR/squid/auth_helper.py" \
    /usr/lib/squid/squidmanager_auth_helper
ok "Helper de autenticacion instalado"

# /etc/squid pertenece al grupo proxy y el panel escribe ahi. El bit setgid
# hace que todo lo que se cree dentro herede el grupo, que es lo que permite a
# Squid leer los ficheros que escribe el panel sin necesidad de chown.
chown root:proxy /etc/squid
chmod 2770 /etc/squid

# Configuracion minima para que Squid arranque; el panel escribira la de
# verdad en el primer «Aplicar cambios».
# El paquete instala su propio squid.conf de ejemplo, de casi 10.000 lineas.
# Hay que reconocerlo y sustituirlo: si se conserva, Squid arranca con la
# politica de fabrica (deja pasar a localhost sin autenticar) y el panel parece
# instalado cuando en realidad no gobierna nada.
es_config_de_fabrica() {
    [ -f /etc/squid/squid.conf ] || return 0
    [ -s /etc/squid/squid.conf ] || return 0
    grep -q "SquidManager" /etc/squid/squid.conf 2>/dev/null && return 1
    head -3 /etc/squid/squid.conf 2>/dev/null | grep -qi "WELCOME TO SQUID" && return 0
    [ -f /etc/squid/squid.conf.default ] && cmp -s /etc/squid/squid.conf /etc/squid/squid.conf.default && return 0
    return 1
}

if es_config_de_fabrica; then
    cat > /etc/squid/squid.conf <<EOF
# SquidManager - Configuracion inicial temporal
http_port ${PROXY_PORT}
# Este arranque NIEGA todo salvo localhost, a proposito. Es la configuracion
# que rige entre que Squid arranca y que el panel escribe la definitiva con
# autenticacion. Permitir aqui la LAN dejaba un proxy ABIERTO a 10/8,
# 172.16/12 y 192.168/16 hasta que alguien pulsara "aplicar" en el panel.
acl SSL_ports port 443
acl Safe_ports port 80
acl Safe_ports port 443
acl CONNECT method CONNECT
http_access deny !Safe_ports
http_access deny CONNECT !SSL_ports
http_access allow localhost
http_access deny all
cache_mem 128 MB
access_log stdio:/var/log/squid/access.log
cache_log /var/log/squid/cache.log
cache_store_log none
coredump_dir /var/spool/squid
visible_hostname squidmanager
error_default_language es
# De la rotacion se encarga logrotate, no Squid.
logfile_rotate 0
EOF
    ok "Configuracion inicial escrita (puerto ${PROXY_PORT})"
else
    ok "Se conserva el squid.conf existente"
fi
# El propietario es el panel, que reescribe este fichero cada vez que se
# aplican cambios; Squid lo lee por grupo. Con propietario root y 640 el panel
# podia leerlo pero no escribirlo, y «Aplicar cambios» fallaba con un 500.
chown "$APP_USER":proxy /etc/squid/squid.conf; chmod 640 /etc/squid/squid.conf

chown -R proxy:proxy /var/log/squid /var/spool/squid
[ -d /var/spool/squid/00 ] || $SQUID_BIN -z --foreground >/dev/null 2>&1 || true

# Rotacion de logs. El fichero del paquete se aparta: el nuestro es el que
# fuerza a Squid a reabrir el log, sin lo cual el panel se queda a cero.
if [ -f /etc/logrotate.d/squid ] && ! grep -q "SquidManager" /etc/logrotate.d/squid 2>/dev/null; then
    mv /etc/logrotate.d/squid /etc/logrotate.d/squid.dpkg-orig
    info "El logrotate del paquete se guardo como /etc/logrotate.d/squid.dpkg-orig"
fi
install -o root -g root -m 644 "$INSTALL_DIR/squid/squid-logrotate.native" /etc/logrotate.d/squid
ok "Rotacion diaria de logs configurada"

# ============================================
# 7. Permisos del panel sobre Squid
# ============================================
paso "7. Concediendo permisos al panel"

# Sin comodines a proposito: son las tres ordenes exactas que ejecuta el
# backend, y nada mas. Es bastante menos de lo que concede montar el socket de
# Docker, que es lo que hace falta en el otro modo.
cat > /etc/sudoers.d/squidmanager <<EOF
# Permisos minimos del panel SquidManager sobre Squid.
${APP_USER} ALL=(root) NOPASSWD: ${SQUID_BIN} -f /etc/squid/squid.conf -k reconfigure
${APP_USER} ALL=(root) NOPASSWD: ${SQUID_BIN} -k parse -f /etc/squid/squid.conf.candidate
${APP_USER} ALL=(root) NOPASSWD: /usr/bin/systemctl restart squid
EOF
chmod 440 /etc/sudoers.d/squidmanager
visudo -cf /etc/sudoers.d/squidmanager >/dev/null || fail "El fichero de sudoers generado no es valido."
ok "sudoers: 3 ordenes concedidas a $APP_USER"

# ============================================
# 8. Backend
# ============================================
paso "8. Instalando el backend"

cd "$INSTALL_DIR/backend"
python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt || fail "No se pudieron instalar las dependencias de Python."
ok "Entorno virtual listo"

SECRET_KEY="${SECRET_KEY:-$(openssl rand -hex 32)}"
ADMIN_INITIAL_PASSWORD="${ADMIN_INITIAL_PASSWORD:-$(openssl rand -base64 12 | tr -d '/+=' | cut -c1-14)}"

cat > "$INSTALL_DIR/.env" <<EOF
# Generado por install-nativo.sh el $(date -Iseconds)
DEPLOY_MODE=native
NATIVE_SQUID_SERVICE=squid
DATABASE_URL=postgresql+psycopg://${DB_USER}:${DB_PASS}@127.0.0.1:5432/${DB_NAME}
SECRET_KEY=${SECRET_KEY}
ACCESS_TOKEN_EXPIRE_MINUTES=480
ADMIN_INITIAL_PASSWORD=${ADMIN_INITIAL_PASSWORD}
BCRYPT_COST=12
CORS_ORIGINS=
TRUSTED_PROXY_HOSTS=localhost
DEBUG=false
SQUID_CONFIG_PATH=/etc/squid/squid.conf
WEB_PORT=${WEB_PORT}
# PROXY_PORT no se escribe a proposito: en modo nativo el puerto vive solo
# en el squid.conf, y aqui solo lo lee docker-compose. Tenerlo aqui era una
# segunda copia que nadie actualizaba y que mentia en cuanto se cambiaba el
# puerto desde el panel.
EOF
chown root:"$(id -gn "$APP_USER")" "$INSTALL_DIR/.env"
chmod 640 "$INSTALL_DIR/.env"
ok "Fichero .env escrito"

chown -R "$APP_USER":"$(id -gn "$APP_USER")" "$INSTALL_DIR/backend"

cat > /etc/systemd/system/squidmanager.service <<EOF
[Unit]
Description=SquidManager - API del panel
After=network.target postgresql.service
Wants=postgresql.service

[Service]
Type=simple
User=${APP_USER}
Group=$(id -gn "$APP_USER")
WorkingDirectory=${INSTALL_DIR}/backend
EnvironmentFile=${INSTALL_DIR}/.env
ExecStart=${INSTALL_DIR}/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port ${API_PORT} --proxy-headers
Restart=on-failure
RestartSec=5

# El panel escribe en /etc/squid y lee los logs de Squid; el resto del sistema
# no tiene por que estar a su alcance.
NoNewPrivileges=no
ProtectHome=yes
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
EOF
ok "Unidad systemd creada"

# ============================================
# 9. Frontend
# ============================================
paso "9. Compilando el panel web"

cd "$INSTALL_DIR/frontend"
npm install --silent --no-audit --no-fund >/dev/null 2>&1 || fail "npm install fallo."
npm run build >/dev/null 2>&1 || fail "La compilacion del frontend fallo."
[ -f dist/index.html ] || fail "La compilacion no genero dist/index.html."
ok "Panel compilado en $INSTALL_DIR/frontend/dist"

# nginx sirve los estaticos y hace de pasarela hacia la API, igual que en el
# modo Docker: el backend nunca se expone directamente.
cat > /etc/nginx/sites-available/squidmanager <<EOF
server {
    listen ${WEB_PORT};
    listen [::]:${WEB_PORT};
    server_name _;
    root ${INSTALL_DIR}/frontend/dist;
    index index.html;

    server_tokens off;
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "same-origin" always;

    client_max_body_size 10m;

    location /api/ {
        proxy_pass http://127.0.0.1:${API_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120s;
    }

    location /assets/ {
        add_header Cache-Control "public, max-age=31536000, immutable" always;
        try_files \$uri =404;
    }

    location = /index.html {
        add_header Cache-Control "no-cache, must-revalidate" always;
        try_files \$uri =404;
    }

    location / {
        add_header Cache-Control "no-cache, must-revalidate" always;
        try_files \$uri \$uri/ /index.html;
    }
}
EOF
ln -sf /etc/nginx/sites-available/squidmanager /etc/nginx/sites-enabled/squidmanager
nginx -t >/dev/null 2>&1 || fail "La configuracion de nginx no es valida."
ok "nginx configurado en el puerto ${WEB_PORT}"

# nginx necesita atravesar el directorio para servir los estaticos.
chmod 755 "$INSTALL_DIR" "$INSTALL_DIR/frontend"

# ============================================
# 10. Arranque
# ============================================
paso "10. Arrancando los servicios"

systemctl daemon-reload
systemctl enable --now squid >/dev/null 2>&1 || warn "Squid no arranco; revisa: journalctl -u squid"
systemctl enable --now squidmanager >/dev/null 2>&1 || warn "El panel no arranco; revisa: journalctl -u squidmanager"
systemctl reload-or-restart nginx

sleep 5

FALLOS=0

# Primero se espera a que el backend sustituya el arranque provisional por la
# configuracion definitiva. Importa el orden: esa configuracion lleva SSL Bump,
# asi que se aplica REINICIANDO Squid, y comprobar los servicios antes pillaba
# a Squid a medio arrancar y avisaba de que estaba caido sin estarlo.
#
# El arranque provisional solo permite localhost. Si se quedara ahi, el proxy no
# serviria a nadie y el sintoma —"no navego"— no apuntaria a ninguna parte.
AUTENTICA=0
for _ in $(seq 1 30); do
    if grep -q "^auth_param" /etc/squid/squid.conf 2>/dev/null; then
        AUTENTICA=1
        break
    fi
    sleep 3
done

for s in postgresql squid squidmanager nginx; do
    # Margen para el reinicio que acaba de provocar la configuracion definitiva.
    ACTIVO=0
    for _ in $(seq 1 15); do
        if systemctl is-active --quiet "$s"; then
            ACTIVO=1
            break
        fi
        sleep 2
    done
    if [ "$ACTIVO" = "1" ]; then
        ok "$s: activo"
    else
        warn "$s: NO activo"
        FALLOS=$((FALLOS + 1))
    fi
done

if [ "$AUTENTICA" = "1" ]; then
    ok "Proxy con autenticacion activa"
else
    warn "El proxy sigue con la configuracion de arranque (solo localhost)."
    warn "Entra al panel y pulsa «Aplicar cambios» para activarlo."
    FALLOS=$((FALLOS + 1))
fi

# Se comprueban las dos capas por separado: si solo respondiera una, el
# sintoma en el navegador seria el mismo (un panel en blanco) y la causa muy
# distinta.
if curl -fsS -m 10 "http://127.0.0.1:${API_PORT}/health" >/dev/null 2>&1; then
    ok "La API responde en el puerto ${API_PORT}"
else
    warn "La API no responde; revisa: journalctl -u squidmanager -n 50"
    FALLOS=$((FALLOS + 1))
fi

if curl -fsS -m 10 -o /dev/null "http://127.0.0.1:${WEB_PORT}/"; then
    ok "El panel responde en el puerto ${WEB_PORT}"
else
    warn "El panel no responde; revisa: nginx -t && journalctl -u nginx -n 50"
    FALLOS=$((FALLOS + 1))
fi

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"

echo
echo "================================================"
if [ "$FALLOS" -eq 0 ]; then
    echo -e "${GREEN} SquidManager instalado (modo nativo, sin Docker)${NC}"
else
    echo -e "${YELLOW} SquidManager instalado con $FALLOS aviso(s)${NC}"
fi
echo "================================================"
echo
echo "  Panel:    http://${IP:-127.0.0.1}:${WEB_PORT}"
echo "  Proxy:    ${IP:-127.0.0.1}:${PROXY_PORT}"
echo "  Usuario:  admin"
echo "  Clave:    ${ADMIN_INITIAL_PASSWORD}"
echo
echo "  Se te pedira cambiarla en el primer acceso."
echo
echo "  El proxy EXIGE usuario y contrasena, y todavia no hay ninguno:"
echo "  hasta que crees el primero en el panel (Usuarios > Nuevo usuario)"
echo "  no navegara nadie. Es a proposito: recien instalado no queda"
echo "  abierto a la red."
echo
echo "  Servicios:  systemctl status squid squidmanager nginx"
echo "  Registros:  journalctl -u squidmanager -f"
echo "  Ajustes:    ${INSTALL_DIR}/.env"
echo
