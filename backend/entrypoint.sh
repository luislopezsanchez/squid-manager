#!/bin/bash
# El contenedor arranca como root para poder corregir el dueño de
# /etc/squid (el único volumen compartido en el que este backend ESCRIBE:
# squid_passwd, squid_digest, el keytab de Kerberos, el propio squid.conf) y
# después baja privilegios al usuario 'squidmgr' antes de ejecutar la
# aplicación de verdad. Sin este paso, una instalación que ya existía antes
# de que el backend dejara de correr como root se quedaría sin poder
# escribir ahí (Docker solo aplica los permisos de la imagen la PRIMERA vez
# que un volumen nombrado se crea vacío; uno ya poblado conserva el dueño
# viejo, root, para siempre si nadie lo corrige).
#
# squid-spool y squid-logs NO se tocan a propósito: este backend solo LEE de
# ahí (estadísticas de disco, logs), nunca escribe, y ambos ya quedan
# legibles por el grupo 'proxy' (gid 13, el mismo que usa este usuario) sin
# necesidad de chown. Hacer un chown -R sobre squid-spool además sería
# potencialmente muy lento: es el directorio de caché de Squid, que puede
# tener cientos de miles de archivos.
set -euo pipefail

mkdir -p /etc/squid
chown -R squidmgr:proxy /etc/squid

# PROJECT_DIR es un bind-mount del directorio del proyecto en el HOST (no un
# volumen de Docker): su dueño es quien lo haya clonado ahí, casi siempre
# root. sync_env_port() escribe el .env con un fichero temporal en el MISMO
# directorio (para el rename atómico), así que hace falta permiso de
# escritura tanto en el .env como en el directorio que lo contiene -no
# alcanza con tocar solo el archivo.
#
# Se corrige SOLO el directorio de nivel superior (no recursivo) y el propio
# .env: el resto del repo (backend/, frontend/, .git/...) no lo toca este
# proceso para nada y no hace falta tocarle el dueño, que además rompería
# los permisos con los que un admin humano espera encontrarse el checkout
# de git en el host.
if [ -n "${PROJECT_DIR:-}" ] && [ -d "$PROJECT_DIR" ]; then
    chown squidmgr:proxy "$PROJECT_DIR"
    [ -f "$PROJECT_DIR/.env" ] && chown squidmgr:proxy "$PROJECT_DIR/.env"
fi

exec gosu squidmgr "$@"
