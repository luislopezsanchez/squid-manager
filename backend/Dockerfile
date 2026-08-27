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
    && rm -rf /var/lib/apt/lists/*

# Cliente de Docker y plugin de Compose.
#
# El backend recrea el contenedor de Squid cuando cambia el puerto de escucha,
# y lo hace invocando `docker compose up -d squid` contra el socket del host.
# Se usa Compose y no el SDK a propósito: así la recreación aplica el
# docker-compose.yml completo y no solo los campos que el código recuerde
# copiar, que era como se perdían opciones en silencio.
#
# Se instalan desde download.docker.com, que trae las versiones al dia. Muchas
# redes corporativas bloquean ese dominio -a traves del proxy responde 403 y la
# imagen no se puede construir-, asi que si no se puede llegar se recurre a los
# paquetes de Debian: docker-cli y docker-compose, que ya es Compose v2 y se
# instala como plugin, de modo que "docker compose" sigue funcionando igual.
RUN set -eu; \
    desde_docker_com() { \
        install -m 0755 -d /etc/apt/keyrings \
        && curl -fsSL --max-time 30 https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc \
        && chmod a+r /etc/apt/keyrings/docker.asc \
        && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
           > /etc/apt/sources.list.d/docker.list \
        && apt-get update \
        && apt-get install -y --no-install-recommends docker-ce-cli docker-compose-plugin; \
    }; \
    if ! desde_docker_com; then \
        echo "AVISO: no se pudo usar download.docker.com; instalando desde Debian"; \
        rm -f /etc/apt/sources.list.d/docker.list /etc/apt/keyrings/docker.asc; \
        apt-get update; \
        apt-get install -y --no-install-recommends docker-cli docker-compose; \
    fi; \
    docker --version; \
    docker compose version; \
    rm -rf /var/lib/apt/lists/*

# Copiar requirements e instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY . .

# Exponer puerto de la API
EXPOSE 8000

# Sin --reload: en producción reinicia el proceso ante cualquier escritura en
# el código, corta las peticiones en curso y vacía el estado en memoria.
# Para desarrollo, examples/docker-compose.override.yml lo vuelve a activar.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
