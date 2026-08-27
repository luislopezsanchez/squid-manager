#!/bin/bash
# ============================================
# SquidManager - Instalacion detras de un proxy corporativo
# ============================================
# Prepara el servidor cuando la salida a Internet pasa obligatoriamente por un
# proxy, y despues lanza install.sh.
#
# Configura las TRES capas que necesitan el proxy por separado. Configurar solo
# una no basta, y es el motivo habitual de que la instalacion falle a medias:
#
#   1. El host      apt y git: descargar Docker y clonar el repositorio.
#   2. El demonio   docker pull de las imagenes base. NO hereda las variables
#                   del shell, porque es un servicio de systemd: es la capa
#                   que casi todo el mundo se salta.
#   3. Los builds   apt, pip, npm y wget DENTRO de los contenedores.
#
# Uso:
#   cp proxy.conf.example proxy.conf
#   nano proxy.conf          # servidor, puerto y credenciales
#   sudo ./install-tras-proxy.sh
#
# Opciones:
#   --solo-configurar   Deja el proxy configurado y no ejecuta install.sh.
#   --sin-verificar     Se salta las comprobaciones de las tres capas.
#
# Las credenciales van en proxy.conf, que esta en .gitignore. Los archivos del
# repositorio no se tocan a proposito: install.sh aborta si encuentra cambios
# locales sin confirmar, asi que poner el proxy a mano en los Dockerfiles deja
# la instalacion bloqueada.
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

SOLO_CONFIGURAR=0
VERIFICAR=1
for arg in "$@"; do
    case "$arg" in
        --solo-configurar) SOLO_CONFIGURAR=1 ;;
        --sin-verificar)   VERIFICAR=0 ;;
        -h|--help)
            sed -n '2,30p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *) fail "Opcion desconocida: $arg (usa --help)" ;;
    esac
done

if [[ $EUID -ne 0 ]]; then
    fail "Este script debe ejecutarse como root (sudo ./install-tras-proxy.sh)"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ============================================
# 1. Leer proxy.conf
# ============================================
CONF="$SCRIPT_DIR/proxy.conf"
if [[ ! -f "$CONF" ]]; then
    fail "No existe proxy.conf. Crealo con: cp proxy.conf.example proxy.conf && nano proxy.conf"
fi

# Valores por defecto para lo que el usuario puede dejar sin escribir.
PROXY_HOST=""; PROXY_PORT=""; PROXY_USER=""; PROXY_PASS=""
PROXY_SCHEME="http"; PROXY_NO_PROXY_EXTRA=""; PROXY_CA_CERT=""
# shellcheck disable=SC1090
source "$CONF"

[[ -n "$PROXY_HOST" ]] || fail "Falta PROXY_HOST en proxy.conf"
[[ -n "$PROXY_PORT" ]] || fail "Falta PROXY_PORT en proxy.conf"
[[ "$PROXY_PORT" =~ ^[0-9]+$ ]] || fail "PROXY_PORT debe ser un numero: '$PROXY_PORT'"
[[ "$PROXY_SCHEME" == "http" || "$PROXY_SCHEME" == "https" ]] \
    || fail "PROXY_SCHEME debe ser http o https: '$PROXY_SCHEME'"

# Un fallo tipico: dejar el ejemplo sin tocar.
if [[ "$PROXY_HOST" == "192.168.1.10" && "$PROXY_PORT" == "8080" ]]; then
    warn "proxy.conf tiene todavia los valores de ejemplo. Revisa que sean los tuyos."
fi

# ============================================
# 2. Armar la URL del proxy
# ============================================
# Las credenciales viajan dentro de la URL, asi que hay que codificar los
# caracteres que ahi significan otra cosa. Una contrasena con una '@' parte la
# URL en dos y el proxy responde 407 sin decir por que: se codifica aqui para
# que el usuario no tenga que saberlo.
urlencode() {
    local cadena="$1" i car salida=""
    for (( i=0; i<${#cadena}; i++ )); do
        car="${cadena:i:1}"
        case "$car" in
            [a-zA-Z0-9.~_-]) salida+="$car" ;;
            *) printf -v car '%%%02X' "'$car"; salida+="$car" ;;
        esac
    done
    printf '%s' "$salida"
}

CREDENCIALES=""
if [[ -n "$PROXY_USER" ]]; then
    CREDENCIALES="$(urlencode "$PROXY_USER")"
    [[ -n "$PROXY_PASS" ]] && CREDENCIALES+=":$(urlencode "$PROXY_PASS")"
    CREDENCIALES+="@"
fi

PROXY_URL="${PROXY_SCHEME}://${CREDENCIALES}${PROXY_HOST}:${PROXY_PORT}"
# Version sin contrasena, para lo que se imprime por pantalla.
PROXY_URL_VISIBLE="${PROXY_SCHEME}://"
[[ -n "$PROXY_USER" ]] && PROXY_URL_VISIBLE+="${PROXY_USER}:****@"
PROXY_URL_VISIBLE+="${PROXY_HOST}:${PROXY_PORT}"

# Lo que nunca debe salir por el proxy: la propia maquina y el trafico entre
# contenedores. Sin esto, el backend intenta hablar con la base de datos a
# traves del proxy corporativo y no llega.
NO_PROXY_LIST="localhost,127.0.0.1,::1,db,backend,frontend,squid,squidmgr-db,squidmgr-backend,squidmgr-frontend,squidmgr-proxy"
[[ -n "$PROXY_NO_PROXY_EXTRA" ]] && NO_PROXY_LIST+=",${PROXY_NO_PROXY_EXTRA}"

info "Proxy: $PROXY_URL_VISIBLE"
info "Sin proxy: $NO_PROXY_LIST"

# ============================================
# 3. CA corporativa (si el proxy intercepta HTTPS)
# ============================================
# Va antes de todo lo demas: si el proxy inspecciona TLS y falta su CA, las
# comprobaciones de mas abajo fallan con un error de certificado.
if [[ -n "$PROXY_CA_CERT" ]]; then
    [[ -f "$PROXY_CA_CERT" ]] || fail "No se encuentra el certificado: $PROXY_CA_CERT"
    info "Instalando la CA corporativa en el sistema..."
    install -m 0644 "$PROXY_CA_CERT" "/usr/local/share/ca-certificates/$(basename "${PROXY_CA_CERT%.*}").crt"
    update-ca-certificates >/dev/null
    ok "CA corporativa instalada"
fi

# ============================================
# 4. Capa 1: el host (apt y git)
# ============================================
info "Configurando el proxy para apt..."
cat > /etc/apt/apt.conf.d/95proxy-squidmanager <<EOF
Acquire::http::Proxy "${PROXY_URL}";
Acquire::https::Proxy "${PROXY_URL}";
EOF
chmod 600 /etc/apt/apt.conf.d/95proxy-squidmanager
ok "apt configurado"

if command -v git &>/dev/null; then
    info "Configurando el proxy para git..."
    git config --global http.proxy  "$PROXY_URL"
    git config --global https.proxy "$PROXY_URL"
    ok "git configurado"
else
    warn "git no esta instalado todavia; install.sh lo necesitara para clonar"
fi

# Para el resto de este script y para install.sh, que se lanza al final.
export http_proxy="$PROXY_URL"   https_proxy="$PROXY_URL"   no_proxy="$NO_PROXY_LIST"
export HTTP_PROXY="$PROXY_URL"   HTTPS_PROXY="$PROXY_URL"   NO_PROXY="$NO_PROXY_LIST"

# ============================================
# 5. Capa 2: el demonio de Docker
# ============================================
# El demonio no ve las variables de arriba: corre como servicio de systemd y
# solo lee su propia configuracion. Sin esto, los docker pull siguen fallando
# aunque el resto este bien puesto.
if command -v docker &>/dev/null; then
    if command -v systemctl &>/dev/null && systemctl list-unit-files docker.service &>/dev/null; then
        info "Configurando el proxy para el demonio de Docker..."
        mkdir -p /etc/systemd/system/docker.service.d
        cat > /etc/systemd/system/docker.service.d/http-proxy.conf <<EOF
[Service]
Environment="HTTP_PROXY=${PROXY_URL}"
Environment="HTTPS_PROXY=${PROXY_URL}"
Environment="NO_PROXY=${NO_PROXY_LIST}"
EOF
        chmod 600 /etc/systemd/system/docker.service.d/http-proxy.conf
        systemctl daemon-reload
        systemctl restart docker

        # El demonio tarda un momento en volver: sin esperar, la comprobacion
        # de mas abajo falla por prisa y no por el proxy.
        for _ in $(seq 1 30); do
            docker info &>/dev/null && break
            sleep 1
        done
        docker info &>/dev/null || fail "Docker no volvio a arrancar tras aplicar el proxy. Revisa: systemctl status docker"
        ok "Demonio de Docker configurado y reiniciado"
    else
        warn "Docker no parece gestionado por systemd: configura su proxy a mano"
    fi
else
    info "Docker no esta instalado; install.sh lo instalara usando el proxy de apt"
fi

# ============================================
# 6. Capa 3: los builds
# ============================================
# Docker inyecta esto como build args predefinidos (http_proxy, https_proxy,
# no_proxy) en todos los builds. No hace falta declarar ARG en los Dockerfile,
# y ademas quedan fuera de docker history: el proxy no se hornea en la imagen,
# que es justo el problema de ponerlo con ENV en el Dockerfile.
info "Configurando el proxy para los builds de Docker..."
mkdir -p /root/.docker
CONFIG_DOCKER=/root/.docker/config.json

if [[ -s "$CONFIG_DOCKER" ]] && command -v python3 &>/dev/null; then
    # Ya hay un config.json (credenciales de registry, por ejemplo): se le
    # anade la seccion de proxies sin tocar lo demas.
    cp -a "$CONFIG_DOCKER" "${CONFIG_DOCKER}.bak-$(date +%Y%m%d-%H%M%S)"
    python3 - "$CONFIG_DOCKER" "$PROXY_URL" "$NO_PROXY_LIST" <<'PY'
import json, sys
ruta, url, sin_proxy = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    with open(ruta) as f:
        datos = json.load(f)
except (ValueError, OSError):
    datos = {}
datos.setdefault("proxies", {})["default"] = {
    "httpProxy": url,
    "httpsProxy": url,
    "noProxy": sin_proxy,
}
with open(ruta, "w") as f:
    json.dump(datos, f, indent=2)
PY
    ok "Proxy anadido al config.json existente (copia de seguridad guardada)"
else
    [[ -s "$CONFIG_DOCKER" ]] && cp -a "$CONFIG_DOCKER" "${CONFIG_DOCKER}.bak-$(date +%Y%m%d-%H%M%S)"
    cat > "$CONFIG_DOCKER" <<EOF
{
  "proxies": {
    "default": {
      "httpProxy": "${PROXY_URL}",
      "httpsProxy": "${PROXY_URL}",
      "noProxy": "${NO_PROXY_LIST}"
    }
  }
}
EOF
    ok "config.json de Docker escrito"
fi
chmod 600 "$CONFIG_DOCKER"

# ============================================
# 7. Comprobar las tres capas
# ============================================
# Merece la pena tardar un minuto aqui: si algo falla, falla con un mensaje
# que dice que capa es, en vez de a mitad de un build de quince minutos.
if [[ $VERIFICAR -eq 1 ]]; then
    info "Comprobando las tres capas (puede tardar un par de minutos)..."

    if command -v curl &>/dev/null; then
        if curl -sSf -o /dev/null --max-time 30 https://deb.debian.org 2>/dev/null; then
            ok "Capa 1 (host): salida a Internet a traves del proxy"
        else
            fail "Capa 1 (host): el proxy no deja salir. Revisa servidor, puerto y credenciales en proxy.conf"
        fi
    else
        warn "curl no disponible: no se comprueba la capa 1"
    fi

    if command -v docker &>/dev/null; then
        if docker pull -q hello-world >/dev/null 2>&1; then
            ok "Capa 2 (demonio): docker pull funciona"
            docker rmi hello-world >/dev/null 2>&1 || true
        else
            fail "Capa 2 (demonio): docker pull falla. Revisa: systemctl status docker"
        fi

        TEMP_BUILD="$(mktemp -d)"
        printf 'FROM debian:stable-slim\nRUN apt-get update\n' > "$TEMP_BUILD/Dockerfile"
        if docker build -q -t squidmanager-proxytest "$TEMP_BUILD" >/dev/null 2>&1; then
            ok "Capa 3 (builds): apt funciona dentro de los contenedores"
            docker rmi squidmanager-proxytest >/dev/null 2>&1 || true
        else
            rm -rf "$TEMP_BUILD"
            fail "Capa 3 (builds): apt no sale a Internet dentro del build. Si el proxy intercepta HTTPS, indica la CA en PROXY_CA_CERT"
        fi
        rm -rf "$TEMP_BUILD"
    fi
fi

# ============================================
# 8. Lanzar la instalacion
# ============================================
if [[ $SOLO_CONFIGURAR -eq 1 ]]; then
    ok "Proxy configurado. Para instalar: sudo -E ./install.sh"
    exit 0
fi

[[ -x "$SCRIPT_DIR/install.sh" ]] || fail "No se encuentra install.sh junto a este script"

info "Lanzando install.sh con el proxy ya configurado..."
exec "$SCRIPT_DIR/install.sh"
