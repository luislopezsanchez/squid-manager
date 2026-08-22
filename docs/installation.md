# Guía de Instalación — SquidManager

Esta guía te llevará paso a paso desde un servidor vacío hasta tener SquidManager funcionando.

---

## Requisitos previos

### Sistema operativo
- Ubuntu 20.04 / 22.04 / 24.04 (recomendado)
- Cualquier Linux con Docker funcionando

### Hardware mínimo
| Recurso | Mínimo | Recomendado |
|---------|--------|-------------|
| CPU | 2 núcleos | 4 núcleos |
| RAM | 2 GB | 4 GB |
| Disco | 5 GB libres | 10 GB |
| Swap | 2 GB | 4 GB |

> ⚠️ La compilación de Squid desde el código fuente requiere al menos 2GB de RAM + 2GB de swap. Si tienes menos, la compilación puede fallar.

### Software necesario
- **Docker** 20.10 o superior
- **Docker Compose** v2 o superior
- **Git**

### Instalar Docker (si no lo tienes)

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg

sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Verificar
docker --version
docker compose version
```

---

## Instalación paso a paso

### Paso 1: Clonar el repositorio

```bash
git clone https://github.com/luislopezsanchez/squid-manager.git
cd squid-manager
```

### Paso 2: Configurar variables de entorno

```bash
cp .env.example .env
```

Edita el archivo `.env` con tus valores:

```bash
nano .env
```

**Valores importantes a cambiar para producción:**

```env
# Cambiar la contraseña de la base de datos
DB_PASS=tu_contraseña_segura_aqui

# Generar una clave secreta aleatoria
SECRET_KEY=$(openssl rand -hex 32)
```

### Paso 3: Levantar los contenedores

```bash
docker compose up -d
```

Esto creará 4 contenedores:

| Contenedor | Servicio | Puerto | Descripción |
|-----------|----------|--------|-------------|
| squidmgr-db | PostgreSQL 16 | 5432 (interno) | Base de datos |
| squidmgr-backend | FastAPI | 8000 | API REST |
| squidmgr-proxy | Squid 6.12 | 3128 | Proxy con SSL Bump |
| squidmgr-frontend | React + Nginx | 3000 | Panel web |

### Paso 4: Esperar la compilación de Squid

**⚠️ Importante:** La primera vez, el contenedor de Squid compila Squid 6.12 desde el código fuente con soporte SSL Bump (OpenSSL). Esto tarda **10-15 minutos** dependiendo del hardware.

Puedes ver el progreso:

```bash
docker compose logs -f squid
```

Cuando veas este mensaje, está listo:
```
Accepting HTTP Socket connections at conn3 local=[::]:3128
listening port: 3128
```

Presiona `Ctrl+C` para salir de los logs (el contenedor sigue corriendo).

### Paso 5: Verificar que todo funciona

```bash
# Verificar que los 4 contenedores están UP
docker compose ps

# Probar la API
curl http://localhost:8000/health
# Debe responder: {"status":"ok"}

# Probar el panel web
curl -o /dev/null -w "%{http_code}" http://localhost:3000/
# Debe responder: 200
```

### Paso 6: Acceder al panel

1. Abre tu navegador: **http://IP_DEL_SERVIDOR:3000**
2. Inicia sesión:
   - Usuario: `admin`
   - Contraseña: `admin123`
3. ¡Ya estás dentro!

---

## Configuración post-instalación

### Cambiar la contraseña del admin

Actualmente no hay una página para esto en el panel. Para cambiarla manualmente:

```bash
# Acceder al contenedor backend
docker exec -it squidmgr-backend python3 -c "
from app.database import SessionLocal
from app.models.admin import Admin
from app.services.auth_service import get_password_hash
db = SessionLocal()
admin = db.query(Admin).filter(Admin.username == 'admin').first()
admin.password_hash = get_password_hash('NUEVA_CONTRASEÑA')
db.commit()
print('Contraseña cambiada')
"
```

### Crear un usuario del proxy

Desde el panel:
1. Ve a **"👥 Usuarios"**
2. Click en **"+ Nuevo Usuario"**
3. Introduce usuario y contraseña
4. Click en **"Crear Usuario"**

### Configurar el proxy en los clientes

**En el navegador del cliente:**
- Tipo: Proxy HTTP
- Dirección: IP_DEL_SERVIDOR
- Puerto: 3128
- Usuario: el que creaste
- Contraseña: la que configuraste

**O por línea de comandos (Linux):**
```bash
export http_proxy=http://usuario:contraseña@IP_DEL_SERVIDOR:3128
export https_proxy=http://usuario:contraseña@IP_DEL_SERVIDOR:3128
```

---

## Desinstalación

```bash
# Detener y eliminar contenedores
docker compose down

# Eliminar volúmenes (¡borra todos los datos!)
docker compose down -v

# Eliminar imágenes
docker rmi squid-manager-backend squid-manager-frontend squid-manager-squid
```

---

## Actualización

```bash
git pull origin main
docker compose build
docker compose up -d
```