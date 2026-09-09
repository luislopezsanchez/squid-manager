#!/bin/bash
# Aplica una actualizacion de SquidManager si -y solo si- el panel dejo una
# aprobada y ya llego su hora. Corre como root (temporizador systemd cada
# minuto, y bajo demanda via la unica linea de sudoers que lo permite),
# nunca a partir de una peticion HTTP directa.
#
# Diseno deliberado, no accidental -leer antes de tocar-:
#
# - Este script NUNCA confia en quien lo invoco. Tanto si lo dispara el
#   temporizador como si lo dispara "sudo" desde el panel (boton "Actualizar
#   ahora"), hace exactamente la misma verificacion antes de actuar: ¿hay
#   algo aprobado en el archivo de estado, y ya llego la hora? El panel web
#   (usuario sin privilegios) puede ADELANTAR cuando este script se fija esa
#   condicion, pero jamas decirle que hacer -nunca lee un comando ni una
#   ruta del archivo de estado, solo un booleano y una fecha-.
#
# - La actualizacion real (upgrade-nativo.sh) se lanza como una unidad
#   systemd aparte ("systemd-run"), fuera del cgroup de este script y del
#   de squidmanager.service. Es imprescindible: la propia actualizacion
#   reinicia squidmanager.service, y si el proceso que la lanzo viviera
#   dentro de ese mismo servicio, se mataria a si mismo a mitad de camino.
#
# - Nunca se re-lee el mismo campo del JSON para decidir DOS VECES cosas
#   distintas en la misma corrida (evita condiciones de carrera entre "hay
#   que lanzarla" y "ya se lanzo"): cada corrida hace UNA sola cosa, o
#   revisa si la que esta en curso termino, o lanza una nueva -nunca las dos-.
#
# - Python (ya es dependencia obligatoria del proyecto) para leer/escribir
#   el JSON, nunca jq -no esta entre los paquetes que instala
#   install-nativo.sh, y no vale la pena sumarlo solo para esto-.
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/squid-manager}"
ESTADO="$INSTALL_DIR/backend/.update_state.json"
UNIDAD="squidmanager-autoupdate-run"
LOG_TAG="squidmanager-autoupdate"

log() { logger -t "$LOG_TAG" "$1"; }

[ -f "$ESTADO" ] || exit 0  # nada corrio nunca una comprobacion: nada que hacer

PY="$INSTALL_DIR/backend/.venv/bin/python3"
[ -x "$PY" ] || PY="python3"

leer_campo() {
    # $1: ruta separada por puntos dentro del JSON (ej "apply.status")
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
    # $1=status $2=commit(o vacio) $3=log_tail(o vacio)
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

ESTADO_APPLY="$(leer_campo apply.status)"

# --- Caso 1: ya habia una actualizacion en curso -> ver si termino --------
if [ "$ESTADO_APPLY" = "running" ]; then
    ACTIVA="$(systemctl is-active "$UNIDAD" 2>/dev/null || true)"
    if [ "$ACTIVA" = "active" ] || [ "$ACTIVA" = "activating" ]; then
        exit 0  # sigue en curso, nada que hacer todavia
    fi

    CODIGO="$(systemctl show "$UNIDAD" -p ExecMainStatus --value 2>/dev/null || echo 1)"
    # journalctl a veces mete una linea de ruido propia ("Failed to open
    # /run/systemd/transient/....service: No such file or directory") si la
    # unidad transient (--collect) ya se autolimpio para el momento en que
    # esto corre -no es parte del log real de la actualizacion, es un aviso
    # de journalctl sobre si misma-. Se descarta explicitamente.
    COLA="$(journalctl -u "$UNIDAD" --no-pager -n 40 -o cat 2>/dev/null \
        | grep -v 'Failed to open /run/systemd/transient' \
        | tail -c 4000 | sed "s/'/ /g")"
    COMMIT_FINAL="$(git -C "$INSTALL_DIR" rev-parse --short HEAD 2>/dev/null || echo "")"

    if [ "$CODIGO" = "0" ]; then
        log "Actualizacion completada (commit $COMMIT_FINAL)"
        escribir_apply "ok" "$COMMIT_FINAL" "$COLA"
    else
        log "Actualizacion fallo (codigo $CODIGO); ver journalctl -u $UNIDAD"
        escribir_apply "error" "$COMMIT_FINAL" "$COLA"
    fi
    exit 0
fi

# --- Caso 2: no hay nada en curso -> ¿hay algo aprobado y ya vencido? -----
APROBADO="$(leer_campo request.approved)"
[ "$APROBADO" = "True" ] || exit 0

PROGRAMADO="$(leer_campo request.scheduled_at)"
[ -n "$PROGRAMADO" ] || exit 0

AHORA_EPOCH="$(date -u +%s)"
PROGRAMADO_EPOCH="$(date -d "$PROGRAMADO" +%s 2>/dev/null || echo 0)"
[ "$PROGRAMADO_EPOCH" -gt 0 ] || exit 0
[ "$AHORA_EPOCH" -ge "$PROGRAMADO_EPOCH" ] || exit 0  # todavia no llega la hora

RAMA="$(git -C "$INSTALL_DIR" branch --show-current 2>/dev/null || echo main)"
[ -n "$RAMA" ] || RAMA="main"

log "Lanzando actualizacion aprobada (rama $RAMA)"
consumir_request
escribir_apply "running" "" ""

# --collect: la unidad se limpia sola una vez inactiva (no queda acumulando
# unidades transient). Corre en su propio cgroup, independiente del de este
# script y del de squidmanager.service -imprescindible, ver nota de diseno
# arriba-.
systemd-run --unit="$UNIDAD" --collect --property=Type=oneshot \
    --setenv=INSTALL_DIR="$INSTALL_DIR" --setenv=BRANCH="$RAMA" \
    bash "$INSTALL_DIR/upgrade-nativo.sh" \
    || log "systemd-run fallo al lanzar la actualizacion"
