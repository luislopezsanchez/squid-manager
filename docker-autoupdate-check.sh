#!/bin/bash
# Equivalente de autoupdate-check.sh para instalaciones Docker: aplica una
# actualizacion de SquidManager si -y solo si- el panel dejo una aprobada y
# ya llego su hora, nunca a partir de una peticion HTTP directa.
#
# Corre de DOS maneras, con la misma logica:
#
# 1. Servicio `updater` del docker-compose.yml (SQUIDMGR_UPDATER=1, ver updater/Dockerfile): un
#    contenedor del propio stack que ejecuta este script cada pocos segundos. Es el camino
#    principal: llega a cualquier despliegue por el solo hecho de hacer `docker compose up`,
#    sin depender de systemd ni de haber ejecutado install.sh/upgrade-docker.sh en el host
#    (un servidor sin temporizador dejaba "Actualizar ahora" pendiente para siempre).
#    La actualizacion real NO la corre este contenedor sino uno AUXILIAR desacoplado
#    (squidmgr-updater-run, SQUIDMGR_APPLY=1): al reconstruir el stack, compose recrea este mismo
#    servicio y, si la actualizacion viviera aqui dentro, se cortaria a si misma a mitad de camino.
# 2. Temporizador de systemd del HOST (ver install.sh/upgrade-docker.sh): respaldo y camino de las
#    instalaciones anteriores. Cede el turno mientras el servicio `updater` este vivo
#    (.updater_alive reciente) y ambos se coordinan con un bloqueo (.update.lock), de modo que
#    una orden nunca se aplica dos veces.
#
# Las observaciones siguientes describen el modo 2 (el temporizador del host) y siguen valiendo.
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
# 1 dentro del contenedor `updater`; SQUIDMGR_APPLY=1 ademas en el contenedor auxiliar que aplica.
EN_CONTENEDOR="${SQUIDMGR_UPDATER:-0}"
APLICAR_YA="${SQUIDMGR_APPLY:-0}"
AUXILIAR="squidmgr-updater-run"
# En Docker el estado vive en la RAIZ del proyecto (no en backend/): el backend corre dentro del
# contenedor con el proyecto montado en esta misma ruta, y solo el directorio raiz le pertenece.
ESTADO="$PROJECT_DIR/.update_state.json"
LOG_TAG="squidmanager-docker-autoupdate"

log() {
    logger -t "$LOG_TAG" "$1" 2>/dev/null || true
    # En el contenedor no hay syslog: el registro es `docker logs squidmgr-updater`.
    if [ "$EN_CONTENEDOR" = "1" ]; then echo "[$(date -u +%FT%TZ)] $1"; fi
}

# Hay un contenedor auxiliar aplicando una actualizacion ahora mismo.
auxiliar_en_curso() {
    command -v docker >/dev/null 2>&1 || return 1
    [ -n "$(docker ps -q --filter "name=^${AUXILIAR}\$" 2>/dev/null)" ]
}

# Latido: en CADA tic, antes de cualquier salida anticipada, se anota la hora en $PROJECT_DIR/.update_heartbeat. El panel lo lee para saber
# si ESTE temporizador esta vivo: sin esto, "Actualizar ahora" deja una orden que nadie recoge y desde el panel no hay
# forma de verlo (un servidor desplegado a mano, sin install.sh ni upgrade-docker.sh, nunca tuvo el temporizador). Si no se puede escribir,
# no pasa nada: nunca debe impedir aplicar una actualizacion.
LATIDO="$PROJECT_DIR/.update_heartbeat"
escribir_marca() {  # $1: archivo
    { date -u +%s > "$1.tmp" && chmod 644 "$1.tmp" && mv -f "$1.tmp" "$1"; } 2>/dev/null || true
}
if [ "$APLICAR_YA" != "1" ]; then
    escribir_marca "$LATIDO"
    # Solo el servicio `updater` escribe esta: el temporizador del host la lee para ceder el turno.
    if [ "$EN_CONTENEDOR" = "1" ]; then escribir_marca "$PROJECT_DIR/.updater_alive"; fi
fi

# El temporizador del host cede mientras el servicio `updater` este vivo: hace el mismo trabajo y
# no hace falta que dos procesos compitan por la misma orden.
if [ "$EN_CONTENEDOR" != "1" ] && [ -r "$PROJECT_DIR/.updater_alive" ]; then
    _VIVO="$(cat "$PROJECT_DIR/.updater_alive" 2>/dev/null || echo 0)"
    case "$_VIVO" in ''|*[!0-9]*) _VIVO=0 ;; esac
    if [ $(( $(date -u +%s) - _VIVO )) -le 180 ]; then
        exit 0
    fi
fi

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
    SM_STATUS="$1" SM_COMMIT="$2" SM_LOG="$3" "$PY" -c "
import json, os
from datetime import datetime, timezone

with open('$ESTADO', encoding='utf-8') as f:
    datos = json.load(f)

ahora = datetime.now(timezone.utc).replace(tzinfo=None).isoformat() + 'Z'
apply = datos.setdefault('apply', {})
status = os.environ['SM_STATUS']
if status == 'running':
    apply['status'] = 'running'
    apply['started_at'] = ahora
    apply['finished_at'] = None
    apply['commit'] = None
    apply['log_tail'] = None
else:
    apply['status'] = status
    apply['finished_at'] = ahora
    if os.environ['SM_COMMIT']:
        apply['commit'] = os.environ['SM_COMMIT']
    apply['log_tail'] = os.environ['SM_LOG']

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

# Ejecuta la actualizacion y deja el resultado en el estado. En el temporizador del host corre aqui
# mismo, en primer plano; en el servicio `updater` lo hace el contenedor auxiliar (ver arriba).
aplicar_actualizacion() {
    # Primer plano (bloqueante): este proceso es ajeno al ciclo de vida de los contenedores que
    # reinicia, asi que no se corta a si mismo. SQUIDMGR_UPGRADE_FOREGROUND evita que
    # upgrade-docker.sh se vuelva a re-lanzar en segundo plano (ese modo es para invocacion
    # interactiva por SSH, no hace falta aca).
    # La actualizacion tiene que seguir la rama que este checkout tiene activa (main, pruebas...). Sin
    # pasarla, upgrade-docker.sh usaba "main" por defecto y una instalacion que seguia otra rama
    # se "actualizaba" a main: codigo viejo sobre una base de datos ya migrada, y el backend en
    # bucle de reinicios. (autoupdate-check.sh, el de nativo, ya lo hacia.)
    if [ "$EN_CONTENEDOR" = "1" ] && ! git -C "$PROJECT_DIR" rev-parse --git-dir >/dev/null 2>&1; then
        # Sin poder leer el repositorio no se sabe en que rama esta: suponer "main" actualizaria a una rama
        # equivocada (codigo distinto sobre una base de datos ya migrada). Mejor fallar y decirlo.
        log "No se puede leer el repositorio de $PROJECT_DIR; no se actualiza"
        escribir_apply "error" "" "El servicio de actualizacion no puede leer el repositorio git de $PROJECT_DIR (permisos o propiedad del directorio). No se hizo ningun cambio."
        return 0
    fi
    RAMA="$(git -C "$PROJECT_DIR" branch --show-current 2>/dev/null || true)"
    [ -n "$RAMA" ] || RAMA="main"

    # Se ejecuta la copia propiedad de root (la instalan install.sh y upgrade-docker.sh, o la imagen del
    # servicio `updater`); si aun no existe (instalacion anterior a este cambio), la del checkout, como antes.
    SCRIPT_UPGRADE="${SQUIDMGR_UPGRADE_SCRIPT:-/usr/local/lib/squidmanager/upgrade-docker.sh}"  # la variable es para las pruebas
    [ -x "$SCRIPT_UPGRADE" ] || SCRIPT_UPGRADE="$PROJECT_DIR/upgrade-docker.sh"

    SALIDA=0
    LOG_TMP="$(mktemp)"
    # 9>&-: el bloqueo (.update.lock) no se hereda a los procesos hijos.
    if SQUIDMGR_UPGRADE_FOREGROUND=1 PROJECT_DIR="$PROJECT_DIR" BRANCH="$RAMA" SQUIDMGR_IN_UPDATER="$EN_CONTENEDOR" \
            bash "$SCRIPT_UPGRADE" >"$LOG_TMP" 2>&1 9>&-; then
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
}

# Lanza el contenedor auxiliar que aplica la actualizacion, desacoplado de este servicio.
lanzar_auxiliar() {
    local imagen proyecto
    local -a args
    docker rm -f "$AUXILIAR" >/dev/null 2>&1 || true
    # Misma imagen que este servicio (por id: no cambia aunque el servicio se reconstruya).
    imagen="$(docker inspect --format '{{.Image}}' "$(hostname)" 2>/dev/null || true)"
    [ -n "$imagen" ] || imagen="$(docker inspect --format '{{.Image}}' squidmgr-updater 2>/dev/null || true)"
    [ -n "$imagen" ] || return 1
    # Nombre real del proyecto de compose, leido de los contenedores que ya existen: si el
    # directorio no se llama como el predeterminado, usar otro nombre crearia un segundo stack.
    proyecto="$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project"}}' squidmgr-backend 2>/dev/null || true)"
    [ -n "$proyecto" ] || proyecto="${COMPOSE_PROJECT_NAME:-}"
    args=(run -d --rm --init --name "$AUXILIAR" -w "$PROJECT_DIR"
          -v "$PROJECT_DIR:$PROJECT_DIR" -v /var/run/docker.sock:/var/run/docker.sock
          -e "PROJECT_DIR=$PROJECT_DIR" -e SQUIDMGR_UPDATER=1 -e SQUIDMGR_APPLY=1
          -e HTTP_PROXY -e HTTPS_PROXY -e NO_PROXY -e http_proxy -e https_proxy -e no_proxy)
    if [ -n "$proyecto" ]; then args+=(-e "COMPOSE_PROJECT_NAME=$proyecto"); fi
    # Con tiempo limite (2 h por defecto: compilar Squid en hardware modesto puede tardar): si algo se cuelga
    # (red caida, descarga de una imagen) la actualizacion no se queda "en curso" para siempre; al terminar el
    # contenedor sin escribir resultado, el servicio la marca como interrumpida pasados 10 minutos.
    docker "${args[@]}" --entrypoint timeout "$imagen" "${SQUIDMGR_UPDATE_TIMEOUT:-7200}" \
        bash /usr/local/lib/squidmanager/docker-autoupdate-check.sh >/dev/null
}

# --- Flujo principal -------------------------------------------------------

# El contenedor auxiliar solo aplica: la orden ya fue consumida por quien lo lanzo.
if [ "$APLICAR_YA" = "1" ]; then
    aplicar_actualizacion
    exit 0
fi

# Un unico proceso a la vez decide y consume (servicio y temporizador comparten este archivo).
BLOQUEO="$PROJECT_DIR/.update.lock"
if { exec 9>"$BLOQUEO"; } 2>/dev/null; then
    if command -v flock >/dev/null 2>&1; then flock -n 9 || exit 0; fi
fi

# Un "running" que ya estaba en el estado cuando esta corrida arranca es de una corrida ANTERIOR que
# nunca llego a escribir su resultado final (murio a mitad de camino: reinicio del host, OOM, kill -9).
# Sin este chequeo, un corte a mitad de una actualizacion dejaba "Actualizacion en curso" en el panel
# para siempre, sin ningun camino para salir de ahi salvo editar el JSON a mano.
# Salvo que el contenedor auxiliar siga vivo: entonces la actualizacion sigue en curso de verdad (el
# servicio `updater` se recrea a mitad de camino, que es lo normal al reconstruir el stack).
if [ "$(leer_campo apply.status)" = "running" ]; then
    if auxiliar_en_curso; then
        exit 0
    fi
    # El servicio `updater` se recrea a mitad de una actualizacion que NO lanzo el (la aplica el
    # temporizador del host, p. ej. el de una version anterior que no usa contenedor auxiliar): sin margen
    # lo daria por muerta cuando sigue en curso. Se espera 10 minutos antes de darla por interrumpida.
    if [ "$EN_CONTENEDOR" = "1" ]; then
        _INICIO="$(leer_campo apply.started_at)"
        _EDAD=$(( $(date -u +%s) - $(date -d "$_INICIO" +%s 2>/dev/null || echo 0) ))
        if [ -n "$_INICIO" ] && [ "$_EDAD" -ge 0 ] && [ "$_EDAD" -lt 600 ]; then
            exit 0
        fi
    fi
    log "Se encontro una actualizacion 'running' de una corrida anterior que no termino -se marca como interrumpida"
    escribir_apply "error" "" "La actualizacion se interrumpio antes de terminar (reinicio del host u otro corte). Revisa el estado del servidor a mano antes de reintentar."
fi

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

if [ "$EN_CONTENEDOR" = "1" ]; then
    if ! lanzar_auxiliar; then
        log "No se pudo lanzar el contenedor auxiliar de actualizacion"
        escribir_apply "error" "" "El servicio de actualizacion no pudo lanzar el contenedor auxiliar (revisa: docker logs squidmgr-updater)."
        exit 0
    fi
    log "Contenedor auxiliar $AUXILIAR lanzado; la actualizacion sigue alli"
    exit 0
fi

aplicar_actualizacion
