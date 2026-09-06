#!/bin/bash
# Consolida en un unico archivo por tipo los logs diarios ya archivados del
# mes que acaba de cerrar, para almacenamiento de largo plazo.
#
# Deliberadamente separado de la rotacion diaria (squid-logrotate): esa
# rotacion existe para que el archivo ACTIVO (el que lee la plataforma para
# graficas, tarjetas y el visor de logs) se mantenga chico dia a dia -pasar
# la rotacion a mensual haria crecer ese archivo activo un mes entero antes
# de rotar, justo lo contrario de lo que se busca-. Este script no toca ese
# mecanismo en absoluto: opera solo sobre /var/log/squid/archive, adonde van
# a parar los diarios ya rotados y que la plataforma nunca lee (el codigo de
# lectura de logs apunta unicamente al access.log activo). Es puro
# almacenamiento en frio, sin relacion con lo que se muestra en el panel.
#
# Se instala en /etc/cron.monthly/, el mecanismo estandar de Debian/Ubuntu
# para tareas que deben correr una vez al mes: no hace falta editar ningun
# crontab a mano, run-parts ya ejecuta todo lo que hay ahi.
set -euo pipefail

ARCHIVE_DIR="/var/log/squid/archive"
MONTHLY_DIR="$ARCHIVE_DIR/monthly"

# Sin directorio de archivo todavia no hay nada que consolidar -por ejemplo,
# en una instalacion recien hecha que todavia no llego a su primera rotacion
# diaria-. No es un error, solo no hay trabajo que hacer.
[ -d "$ARCHIVE_DIR" ] || exit 0

# /etc/cron.monthly corre el dia 1 del mes, asi que "el mes anterior" es
# siempre el que acaba de cerrar del todo.
MES="$(date -d 'last month' +%Y%m)"

mkdir -p "$MONTHLY_DIR"

for TIPO in access cache; do
    # El glob no se expande si no hay coincidencias (sin nullglob activado):
    # queda como el patron literal, que nunca existe como archivo real, asi
    # que el chequeo de -e detecta bien el caso de "no hay nada que juntar".
    ARCHIVOS=("$ARCHIVE_DIR/${TIPO}.log-${MES}"*.gz)
    [ -e "${ARCHIVOS[0]}" ] || continue

    DESTINO="$MONTHLY_DIR/${TIPO}-${MES}.log.gz"
    if [ -e "$DESTINO" ]; then
        # Ya se consolido antes (una corrida anterior, o el cron se disparo
        # mas de una vez): no duplicar contenido volviendo a concatenar.
        logger -t squidmanager-log-archive \
            "Ya existe $DESTINO; no se vuelve a consolidar $TIPO de $MES"
        continue
    fi

    # Los .gz de logrotate son streams gzip independientes; concatenarlos
    # produce un .gz valido con varios miembros (gunzip/zcat los descomprime
    # todos seguidos, tal como si fuera uno solo). Evita descomprimir y
    # volver a comprimir un mes entero solo para juntarlo.
    cat "${ARCHIVOS[@]}" > "$DESTINO.tmp"
    mv "$DESTINO.tmp" "$DESTINO"
    rm -f "${ARCHIVOS[@]}"
    logger -t squidmanager-log-archive \
        "Consolidados ${#ARCHIVOS[@]} archivos de $TIPO de $MES en $DESTINO"
done
