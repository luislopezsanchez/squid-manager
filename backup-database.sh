#!/bin/bash
# Backup periódico de la base de datos, con rotación, para los dos modos de
# despliegue (autodetecta por DEPLOY_MODE del .env, igual que el resto del
# proyecto -ver install-nativo.sh/docker-compose.yml-).
#
# Antes de esto, el único backup automatizado documentado era `make backup`
# (solo Docker, sin rotación: los .sql se acumulaban para siempre) y en modo
# nativo no había ninguno programado -solo el paso manual de
# docs/actualizacion.md antes de actualizar-. Ninguno de los dos tenía
# evidencia de haberse restaurado nunca (ver docs/audits, hallazgo 07-001).
#
# Uso: correrlo a mano, o vía cron (ver docs/production.md, sección
# "Backup automático"). Pensado para invocarse SIEMPRE desde el directorio
# del proyecto (o con PROJECT_DIR ya exportado), igual que el resto de
# scripts de mantenimiento periódico.
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
cd "$PROJECT_DIR"

# Carga el .env si existe: es de ahí de donde salen DEPLOY_MODE, DB_NAME y
# DB_USER. Sin esto, cron (que no hereda el entorno del shell interactivo)
# no los ve -mismo motivo por el que purge_audit_log.py necesita el mismo
# paso, ver docs/production.md-.
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    . "$PROJECT_DIR/.env"
    set +a
fi

DEPLOY_MODE="${DEPLOY_MODE:-docker}"
DB_NAME="${DB_NAME:-squidmanager}"
DB_USER="${DB_USER:-squid}"

BACKUP_DIR="$PROJECT_DIR/backups"
mkdir -p "$BACKUP_DIR"

# 14 días por defecto: suficiente para notar un problema y volver atrás sin
# tener que ir a buscar un backup de hace meses, sin dejar que la carpeta
# crezca sin límite. Configurable con RETENCION_DIAS_BACKUP en el .env, para
# quien prefiera otro criterio.
RETENCION_DIAS_BACKUP="${RETENCION_DIAS_BACKUP:-14}"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
DESTINO="$BACKUP_DIR/squidmanager_${TIMESTAMP}.sql.gz"
TMP="$DESTINO.tmp"

# Se escribe a un temporal y se renombra al final -mismo patrón que
# consolidate-monthly-logs.sh y _write_atomic en squid_service.py-: un
# pg_dump que se corta a mitad de camino (disco lleno, cron matado) no debe
# dejar un .sql.gz a medias con nombre de backup terminado, que parecería
# válido hasta que alguien intentara restaurarlo.
# --clean --if-exists: el dump incluye un DROP TABLE/SEQUENCE/etc IF EXISTS
# antes de cada CREATE. Sin esto, restaurar sobre una base que YA tiene
# datos (el caso real de una recuperación: la base sigue ahí, solo que con
# algo corrupto o borrado por error) deja una pila de "already exists" y
# "duplicate key" -confirmado en vivo, la primera version de este script no
# los tenia y la restauracion quedaba a medias-, en vez de reemplazar todo
# de verdad como promete restore-database.sh.
if [ "$DEPLOY_MODE" = "native" ]; then
    sudo -u postgres pg_dump --clean --if-exists "$DB_NAME" | gzip > "$TMP"
else
    docker exec squidmgr-db pg_dump -U "$DB_USER" --clean --if-exists "$DB_NAME" | gzip > "$TMP"
fi
mv "$TMP" "$DESTINO"
echo "Backup creado: $DESTINO ($(du -h "$DESTINO" | cut -f1))"

# Purga de backups más viejos que la retención. -mtime usa la fecha de
# modificación del archivo, no un nombre parseado: más simple y no depende
# de que el reloj del sistema coincida con el del nombre.
BORRADOS=$(find "$BACKUP_DIR" -maxdepth 1 -name 'squidmanager_*.sql.gz' -mtime "+$RETENCION_DIAS_BACKUP" -print)
if [ -n "$BORRADOS" ]; then
    echo "$BORRADOS" | xargs rm -f
    echo "Purgados $(echo "$BORRADOS" | wc -l) backup(s) más viejos que $RETENCION_DIAS_BACKUP días."
fi
