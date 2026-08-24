#!/bin/bash
set -e

# Limpiar PID file stale
rm -f /run/squid.pid /var/run/squid.pid 2>/dev/null || true

# Puerto desde variable de entorno o 3128 por defecto
SQUID_PORT="${SQUID_PORT:-3128}"

# ============================================
# Generar CA y certificados SSL si no existen
# ============================================
CA_DIR="/etc/squid/ssl_cert"
CA_CERT="$CA_DIR/squid-ca.crt"
CA_KEY="$CA_DIR/squid-ca.key"

if [ ! -f "$CA_CERT" ] || [ ! -f "$CA_KEY" ]; then
    echo "[entrypoint] Generando CA raíz de Squid..."

    mkdir -p "$CA_DIR"

    openssl genrsa -out "$CA_KEY" 4096 2>/dev/null

    openssl req -new -x509 -key "$CA_KEY" -out "$CA_CERT" -days 3650 \
        -subj "/C=US/ST=Proxy/L=Manager/O=SquidManager/CN=SquidManager CA" \
        -extensions v3_ca 2>/dev/null

    chmod 600 "$CA_KEY"
    chmod 644 "$CA_CERT"
    chown proxy:proxy "$CA_CERT" "$CA_KEY"

    echo "[entrypoint] CA raíz generada: $CA_CERT"
fi

# ============================================
# Base de certificados dinámicos (ssl_crtd)
# ============================================
# Vive en el volumen persistente, no en /tmp: aplicar cambios reinicia el
# contenedor, y con la base en /tmp se perdía toda la caché de certificados
# en cada reinicio.
#
# El directorio DEBE pertenecer a 'proxy': el helper security_file_certgen
# hereda el usuario de Squid, y si es de root no puede escribir index.txt.
# Ese era el motivo de los errores "Database search failure" y de que el
# helper muriera una y otra vez.
# La base va en un SUBdirectorio del volumen: security_file_certgen necesita
# crear el directorio él mismo, y el punto de montaje del volumen no se puede
# borrar desde dentro del contenedor.
SSL_CRTD_VOLUME="/var/lib/ssl_crtd"
SSL_CRTD_DIR="$SSL_CRTD_VOLUME/db"

if [ ! -f "$SSL_CRTD_DIR/index.txt" ]; then
    echo "[entrypoint] Inicializando base de certificados en $SSL_CRTD_DIR..."
    rm -rf "$SSL_CRTD_DIR"
    /usr/lib/squid/security_file_certgen -c -s "$SSL_CRTD_DIR" -M 4MB 2>&1
    echo "[entrypoint] Base de certificados inicializada"
fi

# Se aplica siempre, no solo al crearla: un volumen creado por una versión
# anterior tendría los permisos equivocados, que es justo lo que impedía al
# helper escribir su índice.
chown -R proxy:proxy "$SSL_CRTD_VOLUME"
chmod -R u+rwX "$SSL_CRTD_VOLUME"

# Restos de la ubicación anterior
rm -rf /tmp/ssl_crtd 2>/dev/null || true

# ============================================
# Copiar archivos de configuración de Squid si faltan (el volumen los oculta)
# ============================================
for f in mime.conf mime.conf.default errorpage.css errorpage.css.default cachemgr.conf cachemgr.conf.default squid.conf.documented squid.conf.default mib.txt; do
    if [ ! -f "/etc/squid/$f" ]; then
        cp "/opt/squid-defaults/$f" "/etc/squid/$f" 2>/dev/null || true
    fi
done

mkdir -p /etc/squid/icons /etc/squid/errors
if [ ! -f /etc/squid/icons/README ]; then
    cp -r /opt/squid-defaults/icons/* /etc/squid/icons/ 2>/dev/null || true
fi
if [ ! -d /etc/squid/errors/en ]; then
    cp -r /opt/squid-defaults/errors/* /etc/squid/errors/ 2>/dev/null || true
fi

# ============================================
# Permisos de los ficheros con secretos
# ============================================
# El backend los escribe con modo 600; aquí se asegura el propietario para que
# Squid (usuario proxy) pueda leerlos aunque los haya creado root.
for f in /etc/squid/squid_passwd /etc/squid/ldap_helper.conf /etc/squid/ldap_allowlist; do
    if [ -f "$f" ]; then
        chown proxy:proxy "$f" 2>/dev/null || true
        chmod 600 "$f" 2>/dev/null || true
    fi
done

# ============================================
# Escribir squid.conf inicial solo si NO existe
# El backend escribirá el config real con SSL Bump mediante apply
# ============================================
if [ ! -f /etc/squid/squid.conf ] || [ ! -s /etc/squid/squid.conf ] || head -1 /etc/squid/squid.conf | grep -q 'Configuración inicial temporal' || cmp -s /etc/squid/squid.conf /etc/squid/squid.conf.default; then
    cat > /etc/squid/squid.conf << EOF
# SquidManager - Configuración inicial temporal
http_port ${SQUID_PORT}
acl localnet src 10.0.0.0/8
acl localnet src 172.16.0.0/12
acl localnet src 192.168.0.0/16
acl SSL_ports port 443
acl Safe_ports port 80
acl Safe_ports port 443
acl CONNECT method CONNECT
http_access deny !Safe_ports
http_access deny CONNECT !SSL_ports
http_access allow localnet
http_access allow localhost
http_access deny all
cache_mem 128 MB
cache_dir ufs /var/spool/squid 100 16 256
access_log stdio:/var/log/squid/access.log
cache_log /var/log/squid/cache.log
cache_store_log none
coredump_dir /var/spool/squid
visible_hostname squidmanager
error_default_language es
EOF
    echo "[entrypoint] Configuración inicial escrita (puerto ${SQUID_PORT})"
else
    echo "[entrypoint] Usando configuración existente del backend"
fi

# ============================================
# Inicializar caché si no existe
# ============================================
if [ ! -d /var/spool/squid/00 ]; then
    echo "[entrypoint] Inicializando caché de Squid..."
    squid -z 2>/dev/null || true
    sleep 1
fi

# ============================================
# Rotación de logs
# ============================================
# Sin esto, access.log y cache.log crecen sin límite hasta llenar el disco.
# cron corre en segundo plano; logrotate se encarga del resto.
if command -v cron >/dev/null 2>&1; then
    cron 2>/dev/null || true
    echo "[entrypoint] Rotación de logs activa (logrotate diario)"
fi

# ============================================
# Iniciar Squid
# ============================================
echo "[entrypoint] Iniciando Squid en puerto ${SQUID_PORT} con SSL Bump..."
exec squid -N -d1
