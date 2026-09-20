#!/bin/bash
# Equivalente de autoupdate-check.sh para instalaciones Docker: aplica una
# actualizacion de SquidManager si -y solo si- el panel dejo una aprobada y
# ya llego su hora. Corre en el HOST (no dentro de ningun contenedor,
# systemd no vive ahi) via un temporizador de systemd (ver
# install.sh/upgrade-docker.sh), nunca a partir de una peticion HTTP directa.
#
# Mas simple que autoupdate-check.sh (nativo) a proposito, no por
# descuido -leer antes de tocar-:
#
# - Nativo necesita una unidad transient APARTE para la actualizacion real
#   (systemd-run) porque el propio backend corre como servicio systemd EN EL
#   MISMO HOST que este script, y la actualizacion reinicia ese servicio: si
#   el proceso que la lanzo viviera en el mismo cgroup, se mataria a si
#   mismo a mitad de camino. Aca no hay ese problema -este script YA es un
#   proceso del host, completamente ajeno al ciclo de vida de los
#   contenedores que reinicia-, asi que puede invocar upgrade-docker.sh
#   DIRECTO y en primer plano (SQUIDMGR_UPGRADE_FOREGROUND=1) y quedarse
#   esperando su codigo de salida, sin systemd-run ni un archivo de
#   resultado intermedio.
# - Por el mismo motivo, no hace falta un caso "ya habia una en curso, ver
#   si termino": esta unidad es Type=oneshot y su temporizador rearma recien
#   cuando ESTA corrida termina (OnUnitActiveSec cuenta desde que el
#   servicio se pone inactivo) -mientras la actualizacion este en curso,
#   simplemente no se lanza una segunda.
#
# Python (ya es dependencia obligatoria del backend, y python3 esta
# practicamente garantizado en cualquier host Linux moderno) para leer/
# escribir el JSON de estado, nunca jq.
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/opt/squid-manager}"
ESTADO="$PROJECT_DIR/backend/.update_state.json"
LOG_TAG="squidmanager-docker-autoupdate"

log() { logger -t "$LOG_TAG" "$1"; }

[ -f "$ESTADO" ] || exit 0  # el backend nunca escribio nada: nada que hacer

PY="$(command -v python3 || true)"
if [ -z "$PY" ]; then
    log "python3 no esta disponible en el host; no se puede leer el estado de actualizaciones."
    exit 0
fi

leer_campo() {
    # $1: ruta separada por puntos dentro del JSON (ej "request.approved")
    "$PY" -c "
import json, sys
with open('$ESTADO', encoding='utf-8') as f:
    datos = json.load(f)
val = datos
for parte in '$1'.split('.'):
    val = val.get(parte) if isinstance(val, dict) else None
    if val is None:
        break
print(val if val is not None else '')
"
}

escribir_apply() {
    # $1=status ("running"|"ok"|"error") $2=commit(o vacio) $3=log_tail(o vacio)
    "$PY" -c "
import json, os
from datetime import datetime, timezone

with open('$ESTADO', encoding='utf-8') as f:
    datos = json.load(f)

ahora = datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + 'Z'
apply = datos.setdefault('apply', {})
status = '$1'
if status == 'running':
    apply['status'] = 'running'
    apply['started_at'] = ahora
    apply['finished_at'] = None
    apply['commit'] = None
    apply['log_tail'] = None
else:
    apply['status'] = status
    apply['finished_at'] = ahora
    if '$2':
        apply['commit'] = '$2'
    apply['log_tail'] = '''$3'''

tmp = '$ESTADO.tmp'
with open(tmp, 'w', encoding='utf-8') as f:
    json.dump(datos, f, ensure_ascii=False, indent=2)
    f.write('\n')
os.replace(tmp, '$ESTADO')
"
}

actualizar_check_tras_aplicar() {
    # $1=commit corto ya instalado (post-actualizacion). Mismo motivo que
    # en autoupdate-check.sh: sin esto, "hay una actualizacion disponible"
    # queda pegado hasta el proximo chequeo del hilo de 6hs.
    "$PY" -c "
import json, os
with open('$ESTADO', encoding='utf-8') as f:
    datos = json.load(f)
check = datos.setdefault('check', {})
nuevo_local = '$1'
check['local_commit'] = nuevo_local
remoto = check.get('remote_commit')
check['update_available'] = bool(remoto and nuevo_local and remoto != nuevo_local)
if not check['update_available']:
    check['commits'] = []
tmp = '$ESTADO.tmp'
with open(tmp, 'w', encoding='utf-8') as f:
    json.dump(datos, f, ensure_ascii=False, indent=2)
    f.write('\n')
os.replace(tmp, '$ESTADO')
"
}

consumir_request() {
    "$PY" -c "
import json, os
with open('$ESTADO', encoding='utf-8') as f:
    datos = json.load(f)
datos['request'] = {'approved': False, 'scheduled_at': None, 'requested_by': None, 'requested_at': None}
tmp = '$ESTADO.tmp'
with open(tmp, 'w', encoding='utf-8') as f:
    json.dump(datos, f, ensure_ascii=False, indent=2)
    f.write('\n')
os.replace(tmp, '$ESTADO')
"
}

APROBADO="$(leer_campo request.approved)"
[ "$APROBADO" = "True" ] || exit 0

PROGRAMADO="$(leer_campo request.scheduled_at)"
[ -n "$PROGRAMADO" ] || exit 0

AHORA_EPOCH="$(date -u +%s)"
PROGRAMADO_EPOCH="$(date -d "$PROGRAMADO" +%s 2>/dev/null || echo 0)"
[ "$PROGRAMADO_EPOCH" -gt 0 ] || exit 0
[ "$AHORA_EPOCH" -ge "$PROGRAMADO_EPOCH" ] || exit 0  # todavia no llega la hora

log "Lanzando actualizacion aprobada (Docker)"
consumir_request
escribir_apply "running" "" ""

# Primer plano (bloqueante): esta unidad YA es un proceso del host, sin
# ningun cgroup que la actualizacion pudiera cortarse a si misma al
# reiniciar. SQUIDMGR_UPGRADE_FOREGROUND evita que upgrade-docker.sh se
# vuelva a re-lanzar en segundo plano (ese modo es para invocacion
# interactiva por SSH, no hace falta aca).
SALIDA=0
LOG_TMP="$(mktemp)"
if SQUIDMGR_UPGRADE_FOREGROUND=1 PROJECT_DIR="$PROJECT_DIR" \
        bash "$PROJECT_DIR/upgrade-docker.sh" >"$LOG_TMP" 2>&1; then
    SALIDA=0
else
    SALIDA=$?
fi

COLA="$(tail -c 4000 "$LOG_TMP" | sed "s/'/ /g")"
rm -f "$LOG_TMP"
COMMIT_FINAL="$(git -C "$PROJECT_DIR" rev-parse --short HEAD 2>/dev/null || echo "")"

if [ "$SALIDA" = "0" ]; then
    log "Actualizacion completada (commit $COMMIT_FINAL)"
    escribir_apply "ok" "$COMMIT_FINAL" "$COLA"
    actualizar_check_tras_aplicar "$COMMIT_FINAL"
else
    log "Actualizacion fallo (codigo $SALIDA); ver $PROJECT_DIR/upgrade-docker-*.log"
    escribir_apply "error" "$COMMIT_FINAL" "$COLA"
fi
