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

    # Crear directorio
    mkdir -p "$CA_DIR"

    # Generar clave privada de la CA
    openssl genrsa -out "$CA_KEY" 4096 2>/dev/null

    # Generar certificado auto-firmado de la CA (válido por 10 años)
    openssl req -new -x509 -key "$CA_KEY" -out "$CA_CERT" -days 3650 \
        -subj "/C=US/ST=Proxy/L=Manager/O=SquidManager/CN=SquidManager CA" \
        -extensions v3_ca 2>/dev/null

    # Permisos
    chmod 600 "$CA_KEY"
    chmod 644 "$CA_CERT"
    chown proxy:proxy "$CA_CERT" "$CA_KEY"

    echo "[entrypoint] CA raíz generada: $CA_CERT"
fi

# ============================================
# Inicializar directorio de certificados dinámicos (ssl_crtd)
# ============================================
SSL_CRTD_DIR="/tmp/ssl_crtd"
# NO crear el directorio - security_file_certgen lo crea el mismo
# Si ya existe, eliminarlo para que lo cree limpio
if [ -d "$SSL_CRTD_DIR" ] && [ ! -f "$SSL_CRTD_DIR/index.txt" ]; then
    rm -rf "$SSL_CRTD_DIR"
fi
if [ ! -f "$SSL_CRTD_DIR/index.txt" ]; then
    echo "[entrypoint] Inicializando ssl_crtd en /tmp..."
    /usr/lib/squid/security_file_certgen -c -s "$SSL_CRTD_DIR" -M 4MB 2>&1
    echo "[entrypoint] ssl_crtd inicializado"
fi

# ============================================
# Copiar archivos de configuración de Squid si faltan (el volumen los oculta)
# ============================================
for f in mime.conf mime.conf.default errorpage.css errorpage.css.default cachemgr.conf cachemgr.conf.default squid.conf.documented squid.conf.default mib.txt; do
    if [ ! -f "/etc/squid/$f" ]; then
        cp "/opt/squid-defaults/$f" "/etc/squid/$f" 2>/dev/null || true
    fi
done
# Copiar icons y errors si no existen
mkdir -p /etc/squid/icons /etc/squid/errors
if [ ! -f /etc/squid/icons/README ]; then
    cp -r /opt/squid-defaults/icons/* /etc/squid/icons/ 2>/dev/null || true
fi
if [ ! -d /etc/squid/errors/en ]; then
    cp -r /opt/squid-defaults/errors/* /etc/squid/errors/ 2>/dev/null || true
fi

# ============================================
# Escribir squid.conf inicial solo si NO existe
# El backend escribirá el config real con SSL Bump mediante apply
# ============================================
if [ ! -f /etc/squid/squid.conf ] || [ ! -s /etc/squid/squid.conf ] || head -1 /etc/squid/squid.conf | grep -q 'Configuración inicial temporal'; then
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
access_log /var/log/squid/access.log
cache_log /var/log/squid/cache.log
coredump_dir /var/spool/squid
visible_hostname squidmanager
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
# Iniciar Squid
# ============================================
echo "[entrypoint] Iniciando Squid en puerto ${SQUID_PORT} con SSL Bump..."
exec squid -N -d1