FROM python:3.12-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    apache2-utils \
    curl \
    ca-certificates \
    gnupg \
    gosu \
    && rm -rf /var/lib/apt/lists/*

# Cliente de Docker y plugin de Compose.
#
# El backend recrea el contenedor de Squid cuando cambia el puerto de escucha,
# y lo hace invocando `docker compose up -d squid` contra el socket del host
# (en realidad contra docker-socket-proxy, ver docker-compose.yml: DOCKER_HOST
# apunta ahi y ni el CLI ni el SDK necesitan saberlo). Se usa Compose y no el
# SDK a propósito: así la recreación aplica el docker-compose.yml completo y
# no solo los campos que el código recuerde copiar, que era como se perdían
# opciones en silencio.
RUN install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc \
    && chmod a+r /etc/apt/keyrings/docker.asc \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
       > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends docker-ce-cli docker-compose-plugin \
    && rm -rf /var/lib/apt/lists/*

# Usuario sin privilegios para correr la aplicación. Mismo uid/gid 13 que usa
# Squid en su propia imagen (squid/Dockerfile) y que install-nativo.sh fija
# para el usuario 'proxy' del sistema: los archivos que este backend escribe
# en los volúmenes compartidos (squid_passwd, squid_digest, el keytab de
# Kerberos...) tienen que quedar legibles por Squid sin depender de que este
# proceso pueda hacer chown a un uid distinto del propio -algo que ya no va a
# poder, precisamente por dejar de ser root.
# El grupo 'proxy' (gid 13) ya viene de fábrica en python:3.12-slim
# (paquete base-passwd de Debian) con ese mismo gid: no hace falta crearlo,
# alcanza con sumar el usuario nuevo a él.
RUN useradd -u 999 -g proxy -m -d /home/squidmgr -s /usr/sbin/nologin squidmgr
# El CLI `docker` escribe su config (~/.docker/config.json) al primer uso;
# sin un HOME real y escribible, esa escritura falla y con ella cualquier
# `docker compose ...` lanzado por el backend.
ENV HOME=/home/squidmgr

# Copiar requirements e instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY . .
RUN chmod +x entrypoint.sh

# Exponer puerto de la API
EXPOSE 8000

# El contenedor arranca como root (necesario para el chown de arranque en
# entrypoint.sh) y baja privilegios a 'squidmgr' antes de ejecutar uvicorn.
# Sin --reload: en producción reinicia el proceso ante cualquier escritura en
# el código, corta las peticiones en curso y vacía el estado en memoria.
# Para desarrollo, examples/docker-compose.override.yml lo vuelve a activar.
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
