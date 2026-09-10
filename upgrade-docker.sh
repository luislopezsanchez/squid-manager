#!/bin/bash
# Actualiza una instalacion Docker de SquidManager: backup previo de la
# base de datos, trae el codigo nuevo de forma segura, reconstruye y
# levanta los contenedores, reconstruye los indices de la base (necesario
# por el cambio de imagen de Postgres, ver el paso 4) y verifica que el
# panel responda al final.
#
# Se corre desde el directorio de la instalacion (no una ruta fija): usa el
# directorio donde vive ESTE script como PROJECT_DIR, salvo que se pase uno
# explicito por variable de entorno.
#
# Complementario a install-nativo.sh (que ya es seguro de re-ejecutar como
# forma de actualizar en modo nativo, ver docs/actualizacion.md): en Docker
# el equivalente documentado ya era corto (`git pull && docker compose up -d
# --build`), pero no incluia ni un backup previo ni la misma robustez ante
# cambios locales sin commitear -el mismo tipo de "git checkout aborta" que
# se encontro y corrigio para el instalador nativo puede pasar aca tambien,
# es el mismo mecanismo de git de por medio-.
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
cd "$PROJECT_DIR"
BRANCH="${BRANCH:-main}"

if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    . "$PROJECT_DIR/.env"
    set +a
fi
WEB_PORT="${WEB_PORT:-3000}"

# Comprobacion de modo ANTES de tocar nada (backup, git reset): el path
# /opt/squid-manager es el default de LOS DOS modos, y los dos scripts se
# recomiendan en la doc, asi que correr el que no toca es un error facil.
# Sin este chequeo, el script hacia el backup y el `git reset --hard`
# -mutando el checkout- y recien moria en el paso 3 con un
# "docker: command not found" que no explica nada.
_MODO="$(printf '%s' "${DEPLOY_MODE:-}" | tr -d '[:space:]' | tr 'A-Z' 'a-z')"
if [ "$_MODO" = "native" ]; then
    echo "ERROR: el .env dice DEPLOY_MODE=native. Esta es una instalacion nativa" >&2
    echo "       (sin Docker). Usa upgrade-nativo.sh, no este script." >&2
    exit 1
fi
if ! command -v docker >/dev/null 2>&1; then
    echo "ERROR: no se encontro el comando 'docker'. Si esta es una instalacion" >&2
    echo "       nativa (sin Docker), usa upgrade-nativo.sh. Si es Docker, revisa" >&2
    echo "       que 'docker' este en el PATH del usuario que corre este script." >&2
    exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
    echo "ERROR: 'docker compose' (plugin v2) no esta disponible. Este script lo" >&2
    echo "       necesita para reconstruir los contenedores." >&2
    exit 1
fi

echo "=== 1. Backup antes de actualizar ==="
if [ -x "$PROJECT_DIR/backup-database.sh" ]; then
    "$PROJECT_DIR/backup-database.sh" || echo "AVISO: el backup fallo; se continua igual, pero revisa el motivo antes de confiar en el upgrade."
else
    echo "AVISO: no se encontro backup-database.sh; se continua sin backup previo."
fi

echo
echo "=== 2. Trayendo el codigo nuevo (rama $BRANCH) ==="
# git 2.35.2+ se niega a operar sobre un repo cuyo dueno no es quien corre
# git ("detected dubious ownership"), y en Docker eso es LO NORMAL, no la
# excepcion: entrypoint.sh del backend le hace chown de este directorio al
# usuario sin privilegios (uid 999) en cada arranque, y este script se corre
# como root (sudo). Se declara el directorio como confiable antes de tocar
# nada. Idempotente: solo se agrega si no estaba.
git config --global --get-all safe.directory 2>/dev/null | grep -qxF "$PROJECT_DIR" \
    || git config --global --add safe.directory "$PROJECT_DIR"

# Se descarta cualquier cambio local ANTES de cambiar de rama, no despues:
# `git checkout` se niega a cambiar de rama si eso pisaria una modificacion
# local (aunque el `reset --hard` de mas abajo la iba a descartar de todas
# formas), y sin este paso el script entero abortaria -mismo bug real
# encontrado y corregido en install-nativo.sh-. `git clean -fd` respeta
# .gitignore: no toca `.env`, `node_modules/` ni nada gitignored.
git checkout --quiet -- . 2>/dev/null || true
git clean -fdq
git fetch --all --quiet
git checkout --quiet "$BRANCH"
git reset --hard --quiet "origin/$BRANCH"
echo "Codigo actualizado a $(git log --oneline -1)"

echo
echo "=== 3. Reconstruyendo y levantando los contenedores ==="
# --build no es opcional: sin el, Docker reutiliza las imagenes que ya
# tiene y el codigo nuevo no llega a ejecutarse aunque el git de arriba
# haya ido bien.
docker compose up -d --build

echo
echo "=== 4. Reconstruyendo los indices de la base ==="
# Hasta 0.21.0 la imagen de Postgres era postgres:16-alpine (musl); desde
# 0.22.0 es pgvector/pgvector:pg16 (glibc). musl NO registra version de
# collation, asi que al cambiar de imagen Postgres NO avisa de nada -no hay
# version previa que comparar-, pero el ORDEN con el que compara texto SI
# cambia: los indices btree de columnas de texto (entre ellos el UNIQUE de
# proxy_users.username) quedan fisicamente ordenados con el criterio viejo
# y son logicamente corruptos -un lookup por indice puede no encontrar una
# fila, el UNIQUE puede dejar pasar un duplicado-. REINDEX los reconstruye
# con el criterio actual. Es rapido (los indices de este esquema son
# chicos) e idempotente: en una instalacion que no lo necesita -una nueva
# creada ya con locale C.UTF-8, o una ya reindexada- es un no-op barato. No
# es fatal si falla: se avisa como hacerlo a mano.
DB_USER="${DB_USER:-squid}"
DB_NAME="${DB_NAME:-squidmanager}"
_db_lista=0
for _ in $(seq 1 30); do
    if docker compose exec -T db pg_isready -U "$DB_USER" >/dev/null 2>&1; then
        _db_lista=1
        break
    fi
    sleep 2
done
if [ "$_db_lista" = "1" ] && docker compose exec -T db \
        psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1 -qc "REINDEX DATABASE \"$DB_NAME\";" >/dev/null 2>&1; then
    echo "OK: indices reconstruidos."
else
    echo "AVISO: no se pudieron reconstruir los indices automaticamente. Hazlo a mano:"
    echo "  docker compose exec -T db psql -U $DB_USER -d $DB_NAME -c 'REINDEX DATABASE \"$DB_NAME\";'"
fi

echo
echo "=== 5. Verificando ==="
# Unos segundos de margen: el backend puede tardar un poco en aplicar
# migraciones y quedar listo para responder despues de un rebuild.
sleep 5
if curl -fs "http://localhost:${WEB_PORT}/health" >/dev/null 2>&1; then
    echo "OK: el panel responde."
    curl -s "http://localhost:${WEB_PORT}/health"
    echo
else
    echo "AVISO: el panel no respondio en http://localhost:${WEB_PORT}/health."
    echo "Revisa 'docker compose logs backend' antes de dar la actualizacion por buena."
fi
