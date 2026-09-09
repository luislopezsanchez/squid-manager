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

# Si ya hay un .env de una instalacion anterior, sus valores tienen prioridad
# sobre los valores por defecto de mas abajo -pero NUNCA sobre una variable
# que quien invoca el script ya haya exportado a proposito (BRANCH=pruebas
# sudo -E ./install-nativo.sh sigue funcionando igual)-.
#
# Sin esto, volver a correr este script -que es exactamente lo que
# docs/actualizacion.md recomienda como forma de actualizar una instalacion
# nativa, porque de paso repara sudoers/systemd/cron/pgvector si algo de eso
# quedo desactualizado- reescribia el .env entero con valores de fabrica en
# cada corrida: rotaba el SECRET_KEY (cerraba la sesion de todo el mundo sin
# aviso) y podia perder un CORS_ORIGINS o un WEB_PORT personalizados. Bug
# real, encontrado probando el upgrade en vivo antes de recomendar este
# camino como "el" procedimiento de actualizacion.
_ENV_PREVIO="$INSTALL_DIR/.env"
if [ -f "$_ENV_PREVIO" ]; then
    for _VAR in SECRET_KEY DATA_KEY WEB_PORT CORS_ORIGINS TRUSTED_PROXY_HOSTS DEBUG BCRYPT_COST ACCESS_TOKEN_EXPIRE_MINUTES; do
        if [ -z "${!_VAR:-}" ]; then
            _VALOR="$(grep -m1 "^${_VAR}=" "$_ENV_PREVIO" 2>/dev/null | cut -d= -f2-)"
            [ -n "$_VALOR" ] && export "$_VAR=$_VALOR"
        fi
    done
    # DB_PASS no se guarda como linea propia: vive embebida en DATABASE_URL
    # (postgresql+psycopg://usuario:CONTRASEÑA@host/base). Se extrae de ahi
    # para no rotarla en cada actualizacion sin necesidad -aunque rotarla
    # tampoco rompe nada por si sola (el ALTER ROLE de mas abajo usa el mismo
    # valor nuevo), es churn de un secreto sin motivo real.
    if [ -z "${DB_PASS:-}" ]; then
        _DB_PASS_PREVIA="$(grep -m1 '^DATABASE_URL=' "$_ENV_PREVIO" 2>/dev/null | sed -E 's#.*://[^:]+:([^@]+)@.*#\1#')"
        [ -n "$_DB_PASS_PREVIA" ] && export "DB_PASS=$_DB_PASS_PREVIA"
    fi
fi

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
    # sudo: lo usa el propio script mas abajo (crear la base como el usuario
    # postgres, "visudo -cf" al final) y, en tiempo de ejecucion, el backend
    # (squidmgr necesita "sudo -n" para las 4 acciones con privilegio -ver
    # runtime/native_runtime.py-). Las imagenes de Ubuntu Server lo traen de
    # fabrica, pero un Debian minimo/netinstall NO -bug real, encontrado
    # instalando en un Debian 12 limpio (172.30.36.88, 2026-09-09): el script
    # fallaba en "sudo: command not found" en el primer uso, mucho antes de
    # llegar a la parte que de verdad necesita privilegios-.
    sudo
    # gnupg: hace falta para importar la clave del repositorio PGDG mas abajo
    # (gpg --dearmor), solo relevante en Debian pero barato de tener siempre.
    gnupg
)
info "Paquetes: ${PAQUETES[*]}"
apt-get install -y -qq "${PAQUETES[@]}" >/dev/null || fail "No se pudieron instalar los paquetes."

# pgvector: el paquete es especifico de la version mayor de Postgres
# (postgresql-16-pgvector, postgresql-17-pgvector...), asi que se instala
# aparte una vez que ya sabemos cual quedo instalada. Lo usa el asistente de
# IA para buscar en la documentacion por significado, no solo por palabra
# exacta -sin esto la extension no existe y esa funcion no puede activarse-.
PG_MAJOR="$(sudo -u postgres psql -tAc 'SHOW server_version;' | cut -d. -f1 | tr -d '[:space:]')"

# En Debian, el paquete de pgvector NO esta en los repos propios de la
# distribucion -recien entro al archivo de Debian a partir de trixie
# (Debian 13); en bookworm (Debian 12) no existe bajo ningun nombre-, asi
# que "apt-get install postgresql-${PG_MAJOR}-pgvector" siempre falla ahi
# con "Unable to locate package", aunque el resto de la instalacion haya
# ido bien. Bug real reportado por un usuario en Debian 12: la doc promete
# soporte para Debian 12 (ver README) pero el script nunca agregaba el
# repositorio que ese paquete necesita en esa distro.
# En Ubuntu no hace falta nada de esto: postgresql-${PG_MAJOR}-pgvector ya
# esta en el repo "universe" de la propia distro (verificado en 22.04 y
# 24.04), asi que ahi no se toca ningun apt source.
if [ "${ID:-}" = "debian" ] && [ ! -f /etc/apt/sources.list.d/pgdg.list ]; then
    info "Debian no trae pgvector en sus propios repos; agregando el repositorio oficial de PostgreSQL (PGDG) solo para ese paquete."
    install -d /usr/share/keyrings
    curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
        | gpg --dearmor -o /usr/share/keyrings/postgresql.gpg \
        || fail "No se pudo importar la clave del repositorio de PostgreSQL (PGDG)."
    echo "deb [signed-by=/usr/share/keyrings/postgresql.gpg] https://apt.postgresql.org/pub/repos/apt ${VERSION_CODENAME}-pgdg main" \
        > /etc/apt/sources.list.d/pgdg.list

    # Sin esto, PGDG reemplaza silenciosamente el Postgres que ya trae
    # Debian: sus paquetes llevan un numero de version mayor (Postgres 18
    # hoy) y, con la prioridad por defecto, apt prefiere ESE en cualquier
    # instalacion futura de "postgresql" a secas -exactamente lo que hace
    # este mismo script en cada re-corrida (paso 2, PAQUETES)-. Bug real,
    # reproducido en 172.30.36.88: una segunda corrida de este script tras
    # la primera (con el repo PGDG ya agregado) instalo postgresql-18 al
    # lado del 15 que ya tenia los datos, y el cluster 15 quedo sin
    # servicio.
    #
    # El pineo tiene que ser especifico del metapaquete "postgresql", no
    # de todo el origen PGDG -bajar la prioridad de TODO el repo (como
    # sugiere la receta generica de wiki.postgresql.org/wiki/Apt) rompe la
    # instalacion de postgresql-15-pgvector: su propia dependencia
    # "postgresql-15" queda marcada como no instalable porque el resolver
    # de apt no puede reconciliar el pineo bajo con el paquete ya instalado
    # -reproducido tambien en 172.30.36.88, "E: Unable to correct problems,
    # you have held broken packages"-. Bloquear solo "postgresql" a secas
    # evita el salto de version mayor sin tocar nada mas: postgresql-15,
    # postgresql-client-15 y postgresql-15-pgvector siguen resolviendo
    # libremente contra PGDG -incluso pueden actualizarse ahi dentro de la
    # misma version mayor 15, que es seguro-, solo el metapaquete que no
    # fija version quedas atado a lo que trae Debian.
    cat > /etc/apt/preferences.d/pgdg.pref <<EOF
Package: postgresql
Pin: release o=apt.postgresql.org
Pin-Priority: -1
EOF

    apt-get update -qq
fi

apt-get install -y -qq "postgresql-${PG_MAJOR}-pgvector" >/dev/null \
    || fail "No se pudo instalar postgresql-${PG_MAJOR}-pgvector."
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
    ES_ACTUALIZACION=1
    info "Ya existe un checkout en $INSTALL_DIR; actualizando a $BRANCH"
    # Se descarta cualquier cambio local ANTES de cambiar de rama, no
    # despues: `git checkout` se niega a cambiar de rama si eso pisaria una
    # modificacion local (aunque el reset --hard de abajo la iba a borrar
    # de todas formas), y aborta el script entero -bug real, encontrado
    # probando el upgrade en vivo: un `pip install`/`npm install` corrido a
    # mano deja el lockfile con una version resuelta distinta a la
    # commiteada, y sin este paso cualquier actualizacion posterior fallaba
    # con "Your local changes... would be overwritten by checkout". Un
    # script de actualizacion no puede depender de que el checkout este
    # impoluto: es exactamente lo que viene a resolver.
    git -C "$INSTALL_DIR" checkout --quiet -- . 2>/dev/null || true
    git -C "$INSTALL_DIR" clean -fdq
    git -C "$INSTALL_DIR" fetch --all --quiet
    git -C "$INSTALL_DIR" checkout --quiet "$BRANCH"
    git -C "$INSTALL_DIR" reset --hard --quiet "origin/$BRANCH"
else
    mkdir -p "$(dirname "$INSTALL_DIR")"
    # Esperar a que el DNS resuelva de verdad, no una cantidad fija de
    # segundos: el reinicio de systemd-resolved que dispara needrestart tras
    # el apt-get de mas arriba puede tardar mas de lo que un margen fijo
    # cubre, y eso era lo que hacia fallar el clon con el DNS ya recuperado
    # unos segundos despues (justo lo que se ve al volver a clonar a mano
    # inmediatamente despues de que el instalador se rinda).
    HOST_REPO="$(echo "$REPO_URL" | sed -E 's#^[a-z]+://([^/]+)/.*#\1#')"
    DNS_LISTO=0
    for _ in $(seq 1 30); do
        if getent hosts "$HOST_REPO" >/dev/null 2>&1; then
            DNS_LISTO=1
            break
        fi
        sleep 2
    done
    [ "$DNS_LISTO" = "1" ] || warn "El DNS no resolvio $HOST_REPO en 60 s; se intenta clonar de todos modos."

    if ! git clone --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"; then
        rm -rf "$INSTALL_DIR"
        fail "No se pudo clonar $REPO_URL (rama $BRANCH). Revisa el error de git de arriba: si es de DNS, prueba 'getent hosts $HOST_REPO' a mano."
    fi
fi
ok "Codigo en $INSTALL_DIR ($(git -C "$INSTALL_DIR" rev-parse --short HEAD))"

# El repo lo clona root, pero el backend corre como $APP_USER: git rechaza
# cualquier operacion sobre un repositorio cuyo dueño no coincide con quien
# lo consulta ("dubious ownership"), salvo que se declare una excepcion
# explicita. Sin esto, el panel (que ejecuta 'git rev-parse' para mostrar el
# commit desplegado en /health) lo veria siempre como "desconocido", aunque
# el .git este ahi. Se usa --system (no --global) porque $APP_USER no tiene
# permiso de escritura en su propio $HOME (que es $INSTALL_DIR, propiedad de
# root) para crear un .gitconfig ahi; --system la deja en /etc/gitconfig,
# que este script ya puede escribir por correr como root.
git config --system --add safe.directory "$INSTALL_DIR"

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
    # UTF8 explicito, no heredado de template1: sin esto la base sale con la
    # codificacion que initdb eligio segun el locale del sistema en el momento
    # de instalar postgresql, y en un servidor sin locale UTF-8 generado eso
    # es SQL_ASCII. Con SQL_ASCII, psycopg3 devuelve bytes en vez de str en
    # ciertas consultas, y SQLAlchemy revienta al detectar la version del
    # servidor ("cannot use a string pattern on a bytes-like object"): el
    # backend queda en crash-loop desde el primer arranque.
    #
    # template0 es obligatorio para fijar la codificacion: template1 ya trae
    # grabada la del cluster y no se puede pisar. El collate/ctype en C es a
    # proposito: UTF8 + C es una combinacion valida y evita depender de que el
    # servidor tenga generado un locale UTF-8, que es justo lo que falta
    # cuando aparece este error.
    sudo -u postgres createdb -O "$DB_USER" -E UTF8 -T template0 --lc-collate=C --lc-ctype=C "$DB_NAME"
fi
sudo -u postgres psql -qc "ALTER DATABASE \"$DB_NAME\" OWNER TO \"$DB_USER\";" >/dev/null

# El rol de la app ($DB_USER) no es superusuario a proposito -principio de
# menor privilegio-, y CREATE EXTENSION exige serlo. Se crea aca, como
# postgres, antes de que Alembic corra ninguna migracion: la migracion que
# usa esta extension no puede crearla ella misma con el rol de la app.
sudo -u postgres psql -d "$DB_NAME" -qc "CREATE EXTENSION IF NOT EXISTS vector;" >/dev/null
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

# Helper de autenticacion Digest (RFC 2617), solo usuarios locales.
install -o root -g root -m 755 "$INSTALL_DIR/squid/digest_auth_helper.py" \
    /usr/lib/squid/squidmanager_digest_helper
ok "Helper de autenticacion Digest instalado"

# Kerberos/Negotiate: el helper negotiate_kerberos_auth usa libkrb5, que sin
# un /etc/krb5.conf usa valores por defecto que en Ubuntu 24.04 (MIT Kerberos
# 1.20) rechazan RC4-HMAC -el tipo de cifrado mas comun en un AD real- con
# "Bad encryption type", y ademas elimino el soporte de DES del todo. El panel
# escribe /etc/squid/krb5.conf (junto al resto de su configuracion, en el
# volumen/directorio que ya gobierna) cuando se activa Kerberos; esta variable
# le dice al proceso de Squid donde leerlo, sin tocar el /etc/krb5.conf del
# sistema por si algo mas en la maquina lo usa. Comprobado en vivo contra un
# AD real: sin esto, la autenticacion Negotiate fallaba siempre pidiendo
# usuario y contrasena pese a un keytab correcto.
mkdir -p /etc/systemd/system/squid.service.d
cat > /etc/systemd/system/squid.service.d/squidmanager-kerberos.conf <<'EOF'
[Service]
Environment=KRB5_CONFIG=/etc/squid/krb5.conf
EOF
systemctl daemon-reload
ok "Variable KRB5_CONFIG configurada para Squid (Kerberos/Negotiate)"

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

# Consolidacion mensual de los logs ya archivados (almacenamiento en frio,
# aparte de la rotacion diaria de arriba: no toca el archivo activo que lee
# el panel). Va a /etc/cron.monthly porque run-parts ya ejecuta todo lo que
# hay ahi una vez al mes, sin tener que declarar una entrada de cron propia.
install -o root -g root -m 755 "$INSTALL_DIR/squid/consolidate-monthly-logs.sh" \
    /etc/cron.monthly/squidmanager-log-archive

# Indexador de estadisticas del mes consolidado (index.json), usado por el
# modulo de historico del panel. Fuera de cron.monthly a proposito: es una
# libreria que invoca el script de arriba, no una tarea que deba correr sola.
mkdir -p /usr/local/lib/squidmanager
install -o root -g root -m 755 "$INSTALL_DIR/squid/build_monthly_index.py" \
    /usr/local/lib/squidmanager/build_monthly_index.py
ok "Consolidacion mensual de logs archivados configurada"

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
# Actualizaciones (ver docs/actualizaciones.md): el panel NUNCA ejecuta la
# actualizacion en si, solo puede adelantar CUANDO este script -que decide
# por su cuenta si corresponde actuar, leyendo el estado que el propio panel
# dejo- se fija esa condicion. Sin argumentos: no hay forma de pedirle otra
# cosa distinta de "revisa ahora".
${APP_USER} ALL=(root) NOPASSWD: /usr/local/lib/squidmanager/autoupdate-check.sh
EOF
chmod 440 /etc/sudoers.d/squidmanager
visudo -cf /etc/sudoers.d/squidmanager >/dev/null || fail "El fichero de sudoers generado no es valido."
ok "sudoers: 4 ordenes concedidas a $APP_USER"

# El script que de verdad aplica la actualizacion (root, invocado por el
# temporizador de abajo o bajo demanda via la linea de sudoers de arriba).
# Mismo directorio que build_monthly_index.py: una libreria del sistema, no
# parte del checkout que git pueda tocar en caliente.
install -o root -g root -m 700 "$INSTALL_DIR/autoupdate-check.sh" \
    /usr/local/lib/squidmanager/autoupdate-check.sh

# Temporizador que revisa cada 5 minutos si hay una actualizacion aprobada y
# ya vencida. Es la unica forma en la que una actualizacion se aplica sola:
# el panel web jamas ejecuta nada con privilegios (ver la nota de diseno en
# autoupdate-check.sh y en app/services/update_service.py).
cat > /etc/systemd/system/squidmanager-autoupdate.service <<'EOF'
[Unit]
Description=SquidManager - Comprobar y aplicar actualizacion aprobada

[Service]
Type=oneshot
ExecStart=/usr/local/lib/squidmanager/autoupdate-check.sh
EOF

cat > /etc/systemd/system/squidmanager-autoupdate.timer <<'EOF'
[Unit]
Description=SquidManager - Revisar actualizaciones pendientes cada minuto

[Timer]
OnBootSec=1min
OnUnitActiveSec=1min
AccuracySec=10s

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now squidmanager-autoupdate.timer >/dev/null 2>&1 \
    || warn "No se pudo activar squidmanager-autoupdate.timer"
ok "Temporizador de actualizaciones activo (cada 5 min)"

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
# Cifra en reposo las credenciales de terceros (LDAP, SMTP, Telegram, IA,
# proxy padre, keytab) -deliberadamente una clave DISTINTA de SECRET_KEY,
# ver la nota en .env.example. Preservada entre actualizaciones por el
# bucle de arriba, igual que SECRET_KEY: regenerarla dejaria indescifrable
# cualquier credencial ya cifrada con la anterior.
DATA_KEY="${DATA_KEY:-$(openssl rand -hex 32)}"
ADMIN_INITIAL_PASSWORD="${ADMIN_INITIAL_PASSWORD:-$(openssl rand -base64 12 | tr -d '/+=' | cut -c1-14)}"
ACCESS_TOKEN_EXPIRE_MINUTES="${ACCESS_TOKEN_EXPIRE_MINUTES:-480}"
BCRYPT_COST="${BCRYPT_COST:-12}"
TRUSTED_PROXY_HOSTS="${TRUSTED_PROXY_HOSTS:-localhost}"
DEBUG="${DEBUG:-false}"

cat > "$INSTALL_DIR/.env" <<EOF
# Generado por install-nativo.sh el $(date -Iseconds)
DEPLOY_MODE=native
NATIVE_SQUID_SERVICE=squid
DATABASE_URL=postgresql+psycopg://${DB_USER}:${DB_PASS}@127.0.0.1:5432/${DB_NAME}
SECRET_KEY=${SECRET_KEY}
DATA_KEY=${DATA_KEY}
ACCESS_TOKEN_EXPIRE_MINUTES=${ACCESS_TOKEN_EXPIRE_MINUTES}
ADMIN_INITIAL_PASSWORD=${ADMIN_INITIAL_PASSWORD}
BCRYPT_COST=${BCRYPT_COST}
CORS_ORIGINS=${CORS_ORIGINS:-}
TRUSTED_PROXY_HOSTS=${TRUSTED_PROXY_HOSTS}
DEBUG=${DEBUG}
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

    # Sin esta regla, /health cae en el catch-all de la SPA y devuelve 200 con
    # el HTML del panel: un monitor externo veria verde con el backend muerto.
    location = /health {
        proxy_pass http://127.0.0.1:${API_PORT}/health;
        access_log off;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:${API_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        # 300s, no 120s: reindexar la documentacion del Asistente de IA hace
        # una llamada real a Jina por fragmento (~200 con el corpus actual),
        # y con el limite de velocidad de Jina (100/min) mas los reintentos
        # ante un 429/503 puede superar los 120s. Con el timeout corto, nginx
        # cortaba la conexion a mitad de camino sin ningun error visible -la
        # peticion del navegador simplemente se interrumpia- mientras el
        # backend seguia trabajando de fondo. Visto en vivo, 172.30.36.33.
        proxy_read_timeout 300s;
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

# "enable --now" solo garantiza que el servicio termine activo -si ya lo
# estaba, no hace nada-, no que este corriendo el codigo que acaba de
# quedar en disco. En una instalacion nueva da igual (no hay nada corriendo
# todavia), pero en un upgrade es el bug real: el codigo se actualiza pero
# el proceso viejo sigue en pie, sirviendo la version y las migraciones de
# ANTES, sin ningun error que lo delate -confirmado en vivo en
# 172.30.36.63, 2026-09-08, con upgrade-nativo.sh-. "restart" fuerza el
# reinicio siempre, y en un servicio que todavia no existe equivale a
# arrancarlo, asi que sirve igual para instalacion nueva y upgrade.
systemctl enable squid >/dev/null 2>&1 || true
systemctl restart squid >/dev/null 2>&1 || warn "Squid no arranco; revisa: journalctl -u squid"
systemctl enable squidmanager >/dev/null 2>&1 || true
systemctl restart squidmanager >/dev/null 2>&1 || warn "El panel no arranco; revisa: journalctl -u squidmanager"
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
    # Margen amplio a proposito: aplicar la configuracion definitiva reinicia
    # Squid, y pararlo tarda lo que diga shutdown_lifetime (30 s por defecto),
    # asi que un reinicio completo son treinta y pico segundos en los que el
    # servicio no esta activo sin que pase nada malo.
    ACTIVO=0
    for _ in $(seq 1 60); do
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
if [ "${ES_ACTUALIZACION:-0}" = "1" ]; then
    if [ "$FALLOS" -eq 0 ]; then
        echo -e "${GREEN} SquidManager actualizado (modo nativo, sin Docker)${NC}"
    else
        echo -e "${YELLOW} SquidManager actualizado con $FALLOS aviso(s)${NC}"
    fi
    echo "================================================"
    echo
    echo "  Panel:    http://${IP:-127.0.0.1}:${WEB_PORT}"
    echo "  Tu configuracion (usuarios, ACLs, reglas, contraseñas) se conservo"
    echo "  tal cual. La clave de 'admin' sigue siendo la que ya tenias -la"
    echo "  linea de abajo es solo el valor por defecto para una instalacion"
    echo "  nueva, no aplica aca-."
    echo
    echo "  Servicios:  systemctl status squid squidmanager nginx"
    echo "  Registros:  journalctl -u squidmanager -f"
    echo "  Ajustes:    ${INSTALL_DIR}/.env"
    echo
else
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
fi
