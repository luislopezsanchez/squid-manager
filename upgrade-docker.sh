#!/bin/bash
# Actualiza una instalacion Docker de SquidManager: backup previo del la
# base de datos, trae el codigo nuevo de forma segura, reconstruye y
# levanta los contenedores, y verifica que el panel responda al final.
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

echo "=== 1. Backup antes de actualizar ==="
if [ -x "$PROJECT_DIR/backup-database.sh" ]; then
    "$PROJECT_DIR/backup-database.sh" || echo "AVISO: el backup fallo; se continua igual, pero revisa el motivo antes de confiar en el upgrade."
else
    echo "AVISO: no se encontro backup-database.sh; se continua sin backup previo."
fi

echo
echo "=== 2. Trayendo el codigo nuevo (rama $BRANCH) ==="
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
echo "=== 4. Verificando ==="
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
