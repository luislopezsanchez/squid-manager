#!/bin/bash
# Restaura un backup creado por backup-database.sh. Complementario a
# propósito: un backup nunca restaurado no es un backup -ver
# docs/audits, hallazgo 07-001-.
#
# Uso: ./restore-database.sh backups/squidmanager_20260908_120000.sql.gz
#
# ADVERTENCIA: reemplaza la base de datos actual por completo. No pide
# confirmación aparte -quien lo ejecuta ya sabe lo que está haciendo, este
# no es un comando que se dispare por accidente desde el panel-, pero deja
# bien claro en la salida qué va a hacer antes de tocar nada.
set -euo pipefail

ARCHIVO="${1:-}"
if [ -z "$ARCHIVO" ] || [ ! -f "$ARCHIVO" ]; then
    echo "Uso: $0 <archivo .sql.gz de backup>" >&2
    echo "Ejemplo: $0 backups/squidmanager_20260908_120000.sql.gz" >&2
    exit 1
fi

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
cd "$PROJECT_DIR"

if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    . "$PROJECT_DIR/.env"
    set +a
fi

DEPLOY_MODE="${DEPLOY_MODE:-docker}"
DB_NAME="${DB_NAME:-squidmanager}"
DB_USER="${DB_USER:-squid}"

echo "Restaurando '$ARCHIVO' sobre la base '$DB_NAME' (modo $DEPLOY_MODE)."
echo "Esto REEMPLAZA todo lo que haya ahora en esa base. Ctrl+C en los"
echo "próximos 5 segundos para cancelar."
sleep 5

if [ "$DEPLOY_MODE" = "native" ]; then
    gunzip -c "$ARCHIVO" | sudo -u postgres psql -d "$DB_NAME"
else
    gunzip -c "$ARCHIVO" | docker exec -i squidmgr-db psql -U "$DB_USER" -d "$DB_NAME"
fi

echo "Restauración terminada. Si el backend ya estaba corriendo, reinícialo"
echo "para que vuelva a leer la configuración desde la base restaurada."
