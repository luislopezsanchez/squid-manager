# Guía de Producción — SquidManager

Esta guía cubre los aspectos necesarios para desplegar SquidManager en un entorno de producción real.

---

## Despliegue rápido

### Con el script de instalación

```bash
curl -fsSL https://raw.githubusercontent.com/luislopezsanchez/squid-manager/main/install.sh | sudo bash
```

El script:
1. Instala Docker si no está
2. Clona el repositorio a `/opt/squid-manager`
3. Genera `.env` con `SECRET_KEY` y `DB_PASS` aleatorias
4. Despliega los contenedores

### Manualmente

```bash
git clone https://github.com/luislopezsanchez/squid-manager.git
cd squid-manager
cp .env.example .env
nano .env  # Editar valores
docker compose up -d
```

---

## Comandos útiles (Makefile)

```bash
make help       # Ver todos los comandos
make up         # Levantar contenedores
make down       # Detener (sin borrar datos)
make logs       # Ver logs
make backup     # Backup de la BD a ./backups/
make restore FILE=backups/xxx.sql  # Restaurar BD
make test       # Ejecutar tests del backend
make status     # Estado + uso de recursos
```

---

## Seguridad en producción

### 1. Cambiar credenciales por defecto

```bash
# Cambiar contraseña del admin (desde el panel o manualmente)
docker exec squidmgr-backend python3 -c "
from app.database import SessionLocal
from app.models.admin import Admin
from app.services.auth_service import get_password_hash
db = SessionLocal()
admin = db.query(Admin).filter(Admin.username == 'admin').first()
admin.password_hash = get_password_hash('NUEVA_CONTRASEÑA')
db.commit()
"
```

### 2. SECRET_KEY segura

```bash
openssl rand -hex 32
# Poner el resultado en .env: SECRET_KEY=...
```

### 3. Rate limiting

El backend incluye rate limiting por IP:
- **Login:** máximo 10 intentos por minuto por IP (anti fuerza bruta)
- **API general:** máximo 60 peticiones por minuto por IP

Configurable en `backend/app/middleware/__init__.py`.

### 4. HTTPS para el panel

El panel web usa HTTP en el puerto 3000. Para HTTPS en producción:

**Opción A — Nginx reverse proxy + Let's Encrypt:**

```nginx
server {
    listen 443 ssl;
    server_name proxy.miempresa.com;

    ssl_certificate /etc/letsencrypt/live/proxy.miempresa.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/proxy.miempresa.com/privkey.pem;

    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $remote_addr;
    }
}
```

**Opción B — No exponer el panel a internet:** usar un túnel SSH o VPN para acceder solo desde la red interna.

### 5. Restringir el puerto de la API

En producción, considera no exponer el puerto 8000 al público. Solo el frontend necesita acceder a la API (dentro de la red Docker). Edita `docker-compose.yml` y quita:

```yaml
ports:
  - "8000:8000"
```

### 6. Docker socket

El backend monta `/var/run/docker.sock` para controlar Squid. Esto da al backend control total sobre Docker. En un entorno de alta seguridad, considera:
- Usar un proxy Docker Socket restringido (ej: `docker-socket-proxy`)
- O ejecutar el backend en un namespace aislado

---

## Backups

### Backup de la base de datos

```bash
make backup
```

Crea `backups/squidmanager_YYYYMMDD_HHMMSS.sql`.

### Backup automático (cron)

```bash
# Añadir a crontab: backup diario a las 2am
0 2 * * * cd /opt/squid-manager && make backup >> /var/log/squidmanager-backup.log 2>&1
```

### Backup de la configuración (JSON)

Desde el panel: **💾 Backup/Migrar** → **📥 Descargar Backup (JSON)**

---

## Monitorización

### Healthchecks de Docker

Todos los contenedores tienen healthchecks:
- **db:** `pg_isready`
- **backend:** `GET /health`
- **frontend:** `GET /`

Ver estado:
```bash
docker compose ps
```

### Dashboard en tiempo real

El panel tiene un dashboard con:
- Tráfico de red en tiempo real
- CPU, RAM, disco
- Top usuarios y sitios
- Logs en vivo

---

## Actualización

```bash
cd /opt/squid-manager
git pull origin main
docker compose build
docker compose up -d
```

---

## Logs y diagnóstico

```bash
# Ver logs de todos los contenedores
make logs

# Ver logs solo de Squid
make logs-squid

# Ver logs del backend
docker compose logs -f backend
```

---

## Tests automatizados

```bash
# Ejecutar tests del backend
make test
# o directamente
docker exec squidmgr-backend pytest -v
```

Los tests cubren:
- Parser del access.log de Squid
- Generador de squid.conf (Jinja2)
- Lógica de filtrado de logs
