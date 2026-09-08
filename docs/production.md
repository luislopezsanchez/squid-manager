# Guía de Producción — SquidManager

Esta guía cubre los aspectos necesarios para desplegar SquidManager en un entorno de producción real.

> **Los ejemplos de esta guía son del despliegue con Docker.** Casi todo vale
> igual para la instalación nativa —TLS por delante del panel, copias de
> seguridad, límites de intentos, monitorización—; lo que cambia son las órdenes
> de operación (`systemctl` en lugar de `docker compose`) y que ahí el panel no
> necesita el socket de Docker. Ver [instalacion-nativa.md](instalacion-nativa.md).

---

## Despliegue rápido

### Con el script de instalación

Descarga y revisa el script antes de ejecutarlo — no lo canalices directo a un intérprete con privilegios de root:

```bash
wget https://raw.githubusercontent.com/luislopezsanchez/squid-manager/main/install.sh
less install.sh          # revisa qué va a hacer en tu servidor
chmod +x install.sh
sudo ./install.sh
```

El script:
1. Instala Docker si no está
2. Clona el repositorio a `/opt/squid-manager`
3. Genera `.env` con `SECRET_KEY` y `DB_PASS` aleatorias
4. Si ya existe un `.env` con la clave de firma de ejemplo, la regenera
5. Despliega los contenedores
6. Muestra dónde leer la contraseña inicial del admin (no la imprime en claro)

### Manualmente

```bash
git clone https://github.com/luislopezsanchez/squid-manager.git
cd squid-manager
cp .env.example .env
nano .env  # DB_PASS y SECRET_KEY son obligatorios
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

### 1. Contraseña del admin

No hay contraseña por defecto: se genera al azar en el primer arranque y se pide cambiarla antes de poder usar el panel. Para cambiarla después, usa siempre el panel (icono de llave en la barra lateral) — así se invalidan las sesiones abiertas en otros navegadores. Evita escribir `password_hash` directamente en la base de datos: el cambio de contraseña también registra cuándo ocurrió, y saltarse ese registro deja tokens antiguos utilizables.

### 2. SECRET_KEY segura

```bash
openssl rand -hex 32
# Poner el resultado en .env: SECRET_KEY=...
```

Si arrancas con `DEBUG=false` (el valor por defecto) y la `SECRET_KEY` sigue siendo la de ejemplo, el backend genera una temporal en cada arranque y avisa en el log — las sesiones se cerrarán en cada reinicio hasta que definas una propia.

### 3. Rate limiting

El backend incluye rate limiting por IP y por cuenta:
- **Login por IP:** máximo 10 intentos por minuto
- **Login por cuenta:** máximo 5 intentos por minuto, independiente de la IP de origen — evita que rotar la IP sirva para esquivar el límite
- **API general:** máximo 120 peticiones por minuto por IP

Solo se confía en la cabecera `X-Forwarded-For` si la petición llega desde un host listado en `TRUSTED_PROXY_HOSTS` (por defecto, el propio frontend). Configurable en `backend/app/middleware/__init__.py`.

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

### 5. Puerto de la API

El puerto 8000 del backend **ya no se publica al host** por defecto: el frontend le habla por la red interna de Docker (`squidnet`), así que no hace falta ninguna acción para restringirlo. Si en algún momento lo publicas para depurar, quítalo de `docker-compose.yml` antes de volver a producción:

```yaml
expose:
  - "8000"    # correcto: solo visible dentro de la red Docker
# ports:
#   - "8000:8000"   # evitar: publica la API al exterior
```

La documentación interactiva (`/docs`, `/openapi.json`) solo se sirve si `DEBUG=true`; con `DEBUG=false` devuelven 404.

### 6. Docker socket

El backend monta `/var/run/docker.sock` para controlar Squid. Esto da al backend control total sobre Docker. En un entorno de alta seguridad, considera:
- Usar un proxy Docker Socket restringido (ej: `docker-socket-proxy`)
- O ejecutar el backend en un namespace aislado

### 7. El backend está pensado para un único proceso — no añadir `--workers`

El indicador de "cambios pendientes" (`config_state.py`) y el contador del rate limiter (`middleware/__init__.py`) viven en variables **globales del proceso**, no en la base de datos ni en Redis. Los instaladores arrancan uvicorn sin `--workers` a propósito:

```
ExecStart=... uvicorn app.main:app --host 127.0.0.1 --port ${API_PORT} --proxy-headers
```

Si se añade `--workers 2` (o más) para "escalarlo":
- Un admin puede ver "no hay cambios pendientes" mientras otro worker sí los tiene.
- El límite de intentos de login se multiplica por el número de workers (cada uno lleva su propia cuenta).

Si algún día hace falta más de un worker, ambos estados tendrían que mudarse a la base de datos o a Redis primero — no es un ajuste de configuración, es un cambio de diseño. Para más de un nodo Squid, la unidad de escala es **una instancia completa de SquidManager por nodo**, no más workers dentro de una misma instancia.

---

## Backups

### Backup de la base de datos

```bash
make backup
```

Crea `backups/squidmanager_YYYYMMDD_HHMMSS.sql`.

### Backup automático (cron)

`backup-database.sh` funciona en los dos modos de despliegue (autodetecta
por `DEPLOY_MODE` del `.env`), guarda en `backups/` dentro del propio
proyecto, comprimido, y purga solo los más viejos que
`RETENCION_DIAS_BACKUP` (14 días por defecto):

```bash
# Añadir a crontab: backup diario a las 2am
0 2 * * * /opt/squid-manager/backup-database.sh >> /var/log/squidmanager-backup.log 2>&1
```

`make backup` (Docker) sigue disponible para un backup manual puntual, pero
no rota nada — para el backup programado, usar el script.

**Restaurar** (reemplaza la base entera, avisa 5 segundos antes de tocar
nada):

```bash
/opt/squid-manager/restore-database.sh backups/squidmanager_20260908_020000.sql.gz
```

### Backup de la configuración (JSON)

Desde el panel: **Backup y migración** → **Descargar backup (JSON)**. Incluye ACLs, reglas, delay pools, usuarios, grupos y la lista de usuarios LDAP autorizados. Ver [docs/backup-restore.md](backup-restore.md) para el detalle completo.

### Retención del registro de auditoría (cron)

Los logs de Squid tienen retención (7 días, ver más abajo); `audit_log` —quién cambió qué ajuste y cuándo— no la tenía y crecía sin límite. Se purga por fuera, igual que el backup, no desde el panel:

```bash
# Añadir a crontab: purgar mensualmente lo anterior a 12 meses (valor por defecto)
#
# Instalación nativa: DATABASE_URL no tiene valor por defecto (a propósito,
# ver "DATABASE_URL sin default" más abajo). Systemd se lo inyecta al backend
# vía EnvironmentFile=, pero cron no — hay que cargar el .env a mano antes de
# llamar al script, si no falla con "Field required: DATABASE_URL".
0 3 1 * * cd /opt/squid-manager && set -a && . ./.env && set +a && cd backend && .venv/bin/python -m scripts.purge_audit_log >> /var/log/squidmanager-purge.log 2>&1
```

En Docker, la misma tarea corre dentro del contenedor del backend:

```bash
0 3 1 * * docker exec squidmgr-backend python -m scripts.purge_audit_log >> /var/log/squidmanager-purge.log 2>&1
```

Para una retención distinta a 12 meses: `python -m scripts.purge_audit_log 6` (6 meses).

---

## Monitorización

### Healthchecks de Docker

Todos los contenedores tienen healthchecks:
- **db:** `pg_isready`
- **backend:** `GET /health` (sobre `127.0.0.1`, dentro del contenedor)
- **frontend:** `GET /` (sobre `127.0.0.1`, no `localhost` — en Alpine resuelve primero a IPv6 y el healthcheck fallaría)
- **squid:** `squid -k check`

Ver estado:
```bash
docker compose ps
```

### Dashboard en tiempo real

El panel tiene un dashboard con:
- Tráfico de red en tiempo real
- CPU, RAM, disco
- Top usuarios y sitios
- Conexiones recientes

---

## Actualización

```bash
cd /opt/squid-manager
git pull origin main
docker compose build
docker compose up -d
```

El esquema se gestiona con Alembic: las migraciones pendientes se aplican solas al arrancar el backend. Revisa el log si actualizas una instalación muy antigua:

```bash
docker compose logs backend | grep -i alembic
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

Los logs de Squid (`access.log`, `cache.log`) rotan a diario con `logrotate`, con 30 días de retención (31 en total, contando el que Squid sigue escribiendo hoy). Los rotados quedan en `/var/log/squid/archive/`, separados del que Squid está escribiendo activamente, nombrados por fecha (`access.log-20260906.gz`) en vez de por número de turno — más fácil de ubicar el de un día concreto para una auditoría, y ese directorio es lo que conviene incluir en un backup o export externo si hace falta conservar el historial más allá de esos 30 días. La retención es fija (no configurable desde el panel); para cambiarla, editar `rotate 30` en `/etc/logrotate.d/squid` en cada servidor.

**Consolidación mensual, aparte de la rotación diaria.** El día 1 de cada mes,
`/etc/cron.monthly/squidmanager-log-archive` junta los diarios ya archivados
del mes que acaba de cerrar en un único archivo por año/mes
(`archive/historical/2026/08/access-202608.log.gz`, `cache-202608.log.gz`),
con un `index.json` precalculado para el módulo **Histórico de logs** del
panel, y borra los diarios sueltos que consolidó. Es puro almacenamiento en
frío: no toca el archivo activo que lee el panel ni la rotación diaria en
absoluto, así que no tiene ningún efecto sobre el rendimiento.

**Retención del histórico: 12 meses por defecto**, purgados por el mismo
script en cada corrida (mes completo, incluido su `index.json`; nunca a
medias). Mismo criterio que el `audit_log` del panel (ver más abajo): un
límite explícito, no "para siempre" — el histórico de navegación es el dato
más sensible que maneja este sistema (IPs, usuarios, dominios visitados), y
antes no tenía ningún límite. Para cambiarlo, definir
`RETENCION_MESES_HISTORICO` en el entorno donde corre el cron (por ejemplo,
agregando `RETENCION_MESES_HISTORICO=24` antes de la línea en
`/etc/cron.monthly/squidmanager-log-archive`, o exportándolo en el mismo
archivo de entorno que usa el resto de la instalación).

Para retención más larga que unos pocos meses, sigue siendo preferible
reenviar los logs a un sistema externo (**Syslog externo** en el panel) en
vez de acumularlos localmente: un log que solo vive en el propio proxy es
más frágil como evidencia de auditoría, y nada los indexa para buscar en
ellos más allá de grep. La consolidación mensual es un respaldo local
acotado, no un reemplazo de eso.

---

## Tests automatizados

```bash
# Ejecutar tests del backend
make test
# o directamente
docker exec squidmgr-backend pytest -v
```

Los tests cubren:
- Parser del access.log de Squid, incluida la lectura del fichero desde el final
- Generador de squid.conf (Jinja2): orden de reglas, reglas SNI paralelas, exclusión de dominios del descifrado
