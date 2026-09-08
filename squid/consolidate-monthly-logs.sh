#!/bin/bash
# Consolida en un unico archivo por tipo los logs diarios ya archivados del
# mes que acaba de cerrar, para almacenamiento de largo plazo, organizados
# por anio y mes (archive/historical/AAAA/MM/) y con un indice de
# estadisticas precalculado por mes (index.json) para el modulo de historico
# del panel.
#
# Deliberadamente separado de la rotacion diaria (squid-logrotate): esa
# rotacion existe para que el archivo ACTIVO (el que lee la plataforma para
# graficas, tarjetas y el visor de logs) se mantenga chico dia a dia -pasar
# la rotacion a mensual haria crecer ese archivo activo un mes entero antes
# de rotar, justo lo contrario de lo que se busca-. Este script no toca ese
# mecanismo en absoluto: opera solo sobre /var/log/squid/archive, adonde van
# a parar los diarios ya rotados y que la plataforma nunca lee para el visor
# en vivo (el codigo de lectura de logs del dashboard/metricas apunta
# unicamente al access.log activo). El historico es una capa aparte,
# consultada solo bajo demanda -ver backend/app/services/historical_log_service.py.
#
# Se instala en /etc/cron.monthly/, el mecanismo estandar de Debian/Ubuntu
# para tareas que deben correr una vez al mes: no hace falta editar ningun
# crontab a mano, run-parts ya ejecuta todo lo que hay ahi. Mismo archivo
# para instalacion nativa y Docker (ver install-nativo.sh y Dockerfile): un
# solo cambio aqui mantiene los dos modos de despliegue al dia.
#
# Tambien purga los meses mas viejos que RETENCION_MESES_HISTORICO (ver mas
# abajo): a diferencia de los diarios (30 dias, logrotate) y del audit_log
# del panel (12 meses, backend/app/services/audit_service.py), el historico
# consolidado no tenia ningun limite y crecia para siempre -inconsistente
# con el resto del proyecto, que sí trata el historial de navegacion como
# el dato mas sensible que maneja (ver docs/production.md). Mismo criterio
# que la retencion del audit_log: un limite explicito, no "para siempre".
set -euo pipefail

ARCHIVE_DIR="/var/log/squid/archive"
HISTORICAL_DIR="$ARCHIVE_DIR/historical"
# 12 meses por defecto, igual que audit_log. Configurable por variable de
# entorno para quien prefiera otro criterio (p. ej. si ya reenvia todo a un
# syslog externo y quiere una copia local mas corta).
RETENCION_MESES_HISTORICO="${RETENCION_MESES_HISTORICO:-12}"
# Fuera de /etc/cron.monthly a proposito: cualquier archivo ahi lo ejecuta
# run-parts una vez al mes por su cuenta, y esto es una libreria que solo
# debe invocar este script, no correr solo.
INDEXADOR="/usr/local/lib/squidmanager/build_monthly_index.py"
# Si por lo que sea faltara (instalacion vieja sin actualizar, por ejemplo),
# se sigue consolidando el .gz igual y solo se avisa que no hubo indice -no
# bloquea el archivado en frio, que es lo importante para no perder logs.
[ -f "$INDEXADOR" ] || INDEXADOR=""

# Sin directorio de archivo todavia no hay nada que consolidar -por ejemplo,
# en una instalacion recien hecha que todavia no llego a su primera rotacion
# diaria-. No es un error, solo no hay trabajo que hacer.
[ -d "$ARCHIVE_DIR" ] || exit 0

# /etc/cron.monthly corre el dia 1 del mes, asi que "el mes anterior" es
# siempre el que acaba de cerrar del todo.
ANIO="$(date -d 'last month' +%Y)"
MES_NUM="$(date -d 'last month' +%m)"
MES="${ANIO}${MES_NUM}"
DESTINO_DIR="$HISTORICAL_DIR/$ANIO/$MES_NUM"

mkdir -p "$DESTINO_DIR"

for TIPO in access cache; do
    # El glob no se expande si no hay coincidencias (sin nullglob activado):
    # queda como el patron literal, que nunca existe como archivo real, asi
    # que el chequeo de -e detecta bien el caso de "no hay nada que juntar".
    ARCHIVOS=("$ARCHIVE_DIR/${TIPO}.log-${MES}"*.gz)
    [ -e "${ARCHIVOS[0]}" ] || continue

    DESTINO="$DESTINO_DIR/${TIPO}-${MES}.log.gz"
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

    # El indice de estadisticas solo tiene sentido para access.log: cache.log
    # es diagnostico interno de Squid, sin usuarios/dominios/estados que
    # resumir.
    if [ "$TIPO" = "access" ] && [ -n "$INDEXADOR" ]; then
        if python3 "$INDEXADOR" "$DESTINO" "$ANIO" "$((10#$MES_NUM))" "$DESTINO_DIR/index.json" 2>&1; then
            logger -t squidmanager-log-archive \
                "Indice generado: $DESTINO_DIR/index.json"
        else
            logger -t squidmanager-log-archive -p daemon.err \
                "No se pudo generar el indice de $DESTINO; el .gz consolidado esta bien, solo falta el resumen"
        fi
    fi
done

# --- Purga de meses mas viejos que la retencion --------------------------
# Recorre archive/historical/AAAA/MM y borra el mes entero (access, cache e
# index.json juntos) si es mas viejo que el corte. No se borra archivo por
# archivo dentro del mes: el directorio AAAA/MM es la unidad, igual que en
# el resto del modulo de historico (un mes es una unidad completa o no
# existe, nunca a medias).
if [ -d "$HISTORICAL_DIR" ]; then
    CORTE="$(date -d "-${RETENCION_MESES_HISTORICO} months" +%Y%m)"
    for ANIO_DIR in "$HISTORICAL_DIR"/*/; do
        [ -d "$ANIO_DIR" ] || continue
        ANIO_VIEJO="$(basename "$ANIO_DIR")"
        for MES_DIR in "$ANIO_DIR"*/; do
            [ -d "$MES_DIR" ] || continue
            MES_VIEJO="$(basename "$MES_DIR")"
            # Nombres no numericos (algo que no sea AAAA/MM) se ignoran en
            # vez de intentar compararlos: mejor no tocar algo que no se
            # entiende que borrar por error.
            case "$ANIO_VIEJO$MES_VIEJO" in
                ''|*[!0-9]*) continue ;;
            esac
            if [ "${ANIO_VIEJO}${MES_VIEJO}" -lt "$CORTE" ]; then
                rm -rf "$MES_DIR"
                logger -t squidmanager-log-archive \
                    "Purgado $MES_DIR (mas viejo que ${RETENCION_MESES_HISTORICO} meses)"
            fi
        done
        # Anio que quedo vacio tras purgar todos sus meses: se retira, para
        # no dejar directorios AAAA vacios acumulandose para siempre.
        rmdir "$ANIO_DIR" 2>/dev/null || true
    done
fi
