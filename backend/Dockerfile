FROM python:3.12-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    apache2-utils \
    curl \
    && rm -rf /var/lib/apt/lists/*

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
