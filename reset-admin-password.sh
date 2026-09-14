#!/bin/bash
# Última red de seguridad si se pierde el acceso web a SquidManager -mismo
# rol que `pihole -a -p` en Pi-hole-: resetea la contraseña de un admin sin
# necesitar la actual, corriendo directo en el servidor. Quien puede
# ejecutar esto ya tiene acceso a la máquina (SSH/consola), así que no es
# un agujero de seguridad nuevo -es exactamente el mismo nivel de acceso
# que ya hacía falta para tocar la base de datos a mano-.
#
# Uso:
#   ./reset-admin-password.sh                    # resetea "admin", genera contraseña
#   ./reset-admin-password.sh otro_usuario        # resetea otro admin, genera contraseña
#   ./reset-admin-password.sh admin "Clave123!"   # fija una contraseña elegida
#
# Autodetecta Docker vs nativo por DEPLOY_MODE del .env, igual que
# backup-database.sh y restore-database.sh -mismo patrón, para no sumar
# una tercera forma de resolver esto en el proyecto.
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)}"
cd "$PROJECT_DIR"

if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    . "$PROJECT_DIR/.env"
    set +a
fi

DEPLOY_MODE="${DEPLOY_MODE:-docker}"

if [ "$DEPLOY_MODE" = "native" ]; then
    # Mismo motivo que purge_audit_log.py: DATABASE_URL no tiene valor por
    # defecto, systemd se lo inyecta al backend pero invocar esto a mano no
    # lo hereda -por eso el `source .env` de arriba es imprescindible aquí,
    # no algo que se podría saltear en este modo-.
    if [ "$(id -u)" -ne 0 ]; then
        echo "Este script necesita root en instalación nativa (lee/escribe la base de datos directamente)." >&2
        echo "Probá: sudo ./reset-admin-password.sh $*" >&2
        exit 1
    fi
    PY="$PROJECT_DIR/backend/.venv/bin/python3"
    [ -x "$PY" ] || PY="python3"
    (cd "$PROJECT_DIR/backend" && "$PY" -m scripts.reset_admin_password "$@")
else
    # docker exec hereda las variables de entorno del contenedor -no hace
    # falta repetir el `source .env` de arriba, ver purge_audit_log.py-.
    docker exec squidmgr-backend python -m scripts.reset_admin_password "$@"
fi
