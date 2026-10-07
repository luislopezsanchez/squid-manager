#!/bin/bash
# Bucle del servicio de actualizacion: cada pocos segundos ejecuta el mismo script que usa el
# temporizador del servidor. Un fallo de una pasada nunca debe tumbar el servicio.
set -u

PROJECT_DIR="${PROJECT_DIR:-/opt/squid-manager}"
export PROJECT_DIR
INTERVALO="${SQUIDMGR_UPDATER_INTERVALO:-20}"

echo "[$(date -u +%FT%TZ)] servicio de actualizacion iniciado (proyecto: $PROJECT_DIR, cada ${INTERVALO}s)"
while true; do
    bash /usr/local/lib/squidmanager/docker-autoupdate-check.sh || echo "[$(date -u +%FT%TZ)] pasada con error (codigo $?); se reintenta"
    sleep "$INTERVALO"
done
