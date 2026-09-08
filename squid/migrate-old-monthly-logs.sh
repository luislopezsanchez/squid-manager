#!/bin/bash
# Migra los meses ya consolidados con el layout plano anterior
# (archive/monthly/{access,cache}-AAAAMM.log.gz) al layout actual por
# año/mes (archive/historical/AAAA/MM/), generando el index.json que le
# falta a cada mes de access -el que lee el módulo de histórico del panel.
#
# Es un paso MANUAL, de una sola vez, para instalaciones que ya llevaban un
# tiempo corriendo consolidate-monthly-logs.sh antes de que existiera esta
# reorganización (ver docs/actualizacion.md). Una instalación nueva, o una
# que todavía no llegó a su primer mes consolidado, no tiene nada que
# migrar -el propio script lo detecta y no hace nada-.
#
# Idempotente: correrlo dos veces no duplica ni rompe nada. Si el destino ya
# existe, el origen se deja donde está y se avisa, en vez de sobreescribir
# o intentar adivinar cuál de los dos es el bueno.
set -euo pipefail

ARCHIVE_DIR="/var/log/squid/archive"
MONTHLY_DIR="$ARCHIVE_DIR/monthly"
HISTORICAL_DIR="$ARCHIVE_DIR/historical"
INDEXADOR="/usr/local/lib/squidmanager/build_monthly_index.py"

if [ ! -d "$MONTHLY_DIR" ]; then
    echo "Nada que migrar: $MONTHLY_DIR no existe (instalación nueva, o nunca hubo layout plano)."
    exit 0
fi

shopt -s nullglob
ARCHIVOS=("$MONTHLY_DIR"/*.log.gz)
if [ ${#ARCHIVOS[@]} -eq 0 ]; then
    echo "Nada que migrar: $MONTHLY_DIR está vacío."
    exit 0
fi

migrados=0
saltados=0

for ARCHIVO in "${ARCHIVOS[@]}"; do
    NOMBRE="$(basename "$ARCHIVO")"

    # access-202601.log.gz / cache-202601.log.gz -- mismo patrón que escribe
    # consolidate-monthly-logs.sh, en las dos versiones del script.
    if [[ "$NOMBRE" =~ ^(access|cache)-([0-9]{4})([0-9]{2})\.log\.gz$ ]]; then
        TIPO="${BASH_REMATCH[1]}"
        ANIO="${BASH_REMATCH[2]}"
        MES_NUM="${BASH_REMATCH[3]}"
    else
        echo "AVISO: '$NOMBRE' no tiene el nombre esperado (tipo-AAAAMM.log.gz); se deja donde está, revísalo a mano."
        saltados=$((saltados + 1))
        continue
    fi

    DESTINO_DIR="$HISTORICAL_DIR/$ANIO/$MES_NUM"
    DESTINO="$DESTINO_DIR/$NOMBRE"

    if [ -e "$DESTINO" ]; then
        echo "AVISO: ya existe $DESTINO; no se sobreescribe. '$ARCHIVO' se deja sin mover, revísalo a mano."
        saltados=$((saltados + 1))
        continue
    fi

    mkdir -p "$DESTINO_DIR"
    mv "$ARCHIVO" "$DESTINO"
    echo "Movido: $ARCHIVO -> $DESTINO"
    migrados=$((migrados + 1))

    # El índice solo tiene sentido para access.log -mismo motivo que en
    # consolidate-monthly-logs.sh-: cache.log es diagnóstico interno de
    # Squid, sin usuarios/dominios/estados que resumir.
    if [ "$TIPO" = "access" ]; then
        INDICE="$DESTINO_DIR/index.json"
        if [ -e "$INDICE" ]; then
            echo "  (ya tiene index.json, no se regenera)"
        elif [ ! -f "$INDEXADOR" ]; then
            echo "  AVISO: no está instalado $INDEXADOR; el mes queda migrado pero sin índice -actualiza install-nativo.sh/la imagen de Squid, o generalo a mano después-."
        elif python3 "$INDEXADOR" "$DESTINO" "$ANIO" "$((10#$MES_NUM))" "$INDICE"; then
            echo "  índice generado: $INDICE"
        else
            echo "  AVISO: no se pudo generar el índice de $DESTINO; el archivo quedó migrado igual, solo falta el resumen."
        fi
    fi
done

echo
echo "Migración terminada: $migrados archivo(s) movido(s), $saltados sin tocar (ver avisos arriba, si los hay)."

if [ -z "$(ls -A "$MONTHLY_DIR" 2>/dev/null)" ]; then
    rmdir "$MONTHLY_DIR"
    echo "$MONTHLY_DIR quedó vacío, se eliminó."
else
    echo "$MONTHLY_DIR todavía tiene archivos sin migrar (ver avisos arriba); no se elimina."
fi
