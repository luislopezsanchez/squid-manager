# Servicio de actualizacion (Docker): hace lo mismo que el temporizador del servidor
# (docker-autoupdate-check.sh), pero como un contenedor mas del stack. Asi llega a CUALQUIER
# despliegue por el simple hecho de ejecutar `docker compose up`, sin depender de systemd ni de
# haber ejecutado install.sh / upgrade-docker.sh en el host (la causa de que "Actualizar ahora"
# dejara la orden pendiente para siempre en instalaciones sin temporizador).
#
# Los scripts van HORNEADOS en la imagen, no se leen del checkout: el checkout lo puede escribir el
# usuario del backend, y este contenedor tiene acceso al socket de Docker. La imagen se reconstruye
# desde un checkout recien restablecido con git (ver upgrade-docker.sh), nunca desde uno sin verificar.
FROM docker:27-cli

RUN apk add --no-cache bash git python3 curl coreutils util-linux ca-certificates tzdata \
    && mkdir -p /usr/local/lib/squidmanager /etc/systemd/system \
    # El proyecto montado lo posee el usuario del backend (uid 999), no root: sin esto git se niega a leerlo
    # ("detected dubious ownership"), no se puede saber la rama y la actualizacion iria a una rama equivocada.
    && git config --system --add safe.directory '*'

COPY docker-autoupdate-check.sh upgrade-docker.sh backup-database.sh /usr/local/lib/squidmanager/
COPY updater/entrypoint.sh /usr/local/bin/updater-entrypoint.sh
RUN chmod 755 /usr/local/lib/squidmanager/*.sh /usr/local/bin/updater-entrypoint.sh

ENV SQUIDMGR_UPDATER=1
ENTRYPOINT ["/usr/local/bin/updater-entrypoint.sh"]
