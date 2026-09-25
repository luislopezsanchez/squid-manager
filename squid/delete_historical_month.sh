#!/bin/bash
# Borra un mes histórico consolidado (archive/historical/AAAA/MM/), invocado
# con sudo -n desde el backend -ver historical_log_service.py::delete_month().
#
# Existe porque el backend corre sin permiso de escritura en /var/log/squid a
# propósito (ver backend/entrypoint.sh y el docstring de
# historical_log_service.py: esa capa nace de solo LEER meses ya cerrados,
# sin compartir estado con nada que escriba el access.log activo). Borrar un
# mes es la única operación de escritura que ese módulo necesita, así que en
# vez de aflojarle permisos de escritura a todo el árbol de logs -o correr el
# backend con más privilegio de los que necesita el otro 99% del tiempo-, se
# abre una puerta angosta y validada, mismo criterio que ya usa el proyecto
# para reconfigurar/reiniciar Squid o disparar una actualización (ver
# install-nativo.sh, sección de sudoers).
#
# Uso: delete_historical_month.sh <year> <month-de-2-digitos>
set -euo pipefail

if [ "$#" -ne 2 ]; then
    echo "Uso: delete_historical_month.sh <year> <month>" >&2
    exit 1
fi

YEAR="$1"
MONTH="$2"

# Validación estricta antes de tocar nada: son los únicos dos valores que
# vienen de fuera de este script, y la regla de sudoers no puede validar su
# forma por sí sola (a diferencia de "conntrack -D -s *", acá no alcanza con
# un comodín porque el argumento arma una ruta de archivo).
[[ "$YEAR" =~ ^[0-9]{4}$ ]] || { echo "Año inválido: $YEAR" >&2; exit 1; }
[[ "$MONTH" =~ ^(0[1-9]|1[0-2])$ ]] || { echo "Mes inválido: $MONTH" >&2; exit 1; }

HISTORICAL_DIR="/var/log/squid/archive/historical"
DESTINO="$HISTORICAL_DIR/$YEAR/$MONTH"

[ -d "$DESTINO" ] || { echo "No existe $DESTINO" >&2; exit 1; }

# Segunda barrera, redundante a propósito: aunque YEAR/MONTH ya solo pueden
# ser dígitos con el formato exacto (nada de "..", "/", espacios), se
# resuelve la ruta real y se confirma que sigue quedando DENTRO de
# HISTORICAL_DIR antes del rm -rf. Barato, y es la diferencia entre un bug
# de validación futuro que solo tira un error y uno que borra algo que no
# debía.
REAL_DESTINO="$(realpath -e "$DESTINO")"
REAL_BASE="$(realpath -e "$HISTORICAL_DIR")"
case "$REAL_DESTINO" in
    "$REAL_BASE"/*) ;;
    *) echo "Ruta fuera de $HISTORICAL_DIR, aborto" >&2; exit 1 ;;
esac

rm -rf -- "$REAL_DESTINO"

# Si el año se queda sin meses, se retira también -mismo criterio que la
# purga por retención de consolidate-monthly-logs.sh: un directorio AAAA
# vacío no debe quedar acumulado para siempre.
ANIO_DIR="$HISTORICAL_DIR/$YEAR"
if [ -d "$ANIO_DIR" ] && [ -z "$(ls -A "$ANIO_DIR" 2>/dev/null)" ]; then
    rmdir "$ANIO_DIR"
fi
