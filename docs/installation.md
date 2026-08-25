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

## Dos formas de instalar

Hacen lo mismo; la diferencia es quién rellena la configuración.

| | Con `install.sh` | Manual |
|---|---|---|
| Dónde se instala | Siempre en `/opt/squid-manager` | Donde tú quieras |
| `DB_PASS` y `SECRET_KEY` | Se generan solas | Las defines tú |
| `PROJECT_DIR` | Se rellena sola | **Tienes que ajustarla** |

### Con el instalador

```bash
git clone https://github.com/luislopezsanchez/squid-manager.git
cd squid-manager
sudo ./install.sh
```

El script instala en `/opt/squid-manager`, genera las claves, deja el `.env`
listo y levanta los contenedores. Si ya había una instalación ahí, la actualiza
conservando la configuración existente.

> No canalices el script directamente a `bash` desde internet: descárgalo,
> léelo y ejecútalo, que es lo que se hace arriba.

Si usas el instalador puedes saltar al [Paso 4](#paso-4-esperar-la-compilación-de-squid).
El resto de esta guía describe la instalación manual.

---

## Instalación manual, paso a paso

### Paso 1: Clonar el repositorio

```bash
git clone https://github.com/luislopezsanchez/squid-manager.git
cd squid-manager
```

Puedes clonarlo donde quieras. Apunta la ruta: hace falta en el paso siguiente.

### Paso 2: Configurar variables de entorno

```bash
cp .env.example .env
```

Edita el archivo `.env` con tus valores:

```bash
nano .env
```

**`DB_PASS` y `SECRET_KEY` son obligatorios** — el `docker-compose.yml` rechaza arrancar sin ellos. Genera ambos con:

```bash
openssl rand -hex 16   # para DB_PASS
openssl rand -hex 32   # para SECRET_KEY
```

Si dejas `ADMIN_INITIAL_PASSWORD` vacío (el valor por defecto), el backend genera una contraseña aleatoria para la cuenta `admin` la primera vez que arranca; si prefieres elegirla tú, ponla ahí antes del primer `docker compose up`.

**`PROJECT_DIR` es el tercer valor que hay que tocar**, y el que más se olvida
porque el sistema arranca igual sin él:

```bash
pwd    # copia esta ruta
```

```env
PROJECT_DIR=/la/ruta/que/te/dio/pwd
```

Viene con `/opt/squid-manager` de ejemplo, que es donde instala `install.sh`.
Si has clonado en otro sitio y no lo cambias, todo funciona con normalidad
salvo una cosa: **cambiar el puerto del proxy desde el panel deja de actualizar
el `.env`**, y el puerto vuelve al valor anterior en el siguiente
`docker compose up -d`, dejando el proxy inalcanzable sin ningún aviso.

El backend usa esa ruta para recrear el contenedor de Squid con Docker Compose,
y necesita verla en la misma ubicación que tiene en el servidor.

### Paso 3: Levantar los contenedores

```bash
docker compose up -d
```

Esto creará 4 contenedores:

| Contenedor | Servicio | Puerto publicado | Descripción |
|-----------|----------|-------------------|-------------|
| squidmgr-db | PostgreSQL 16 | ninguno (interno) | Base de datos |
| squidmgr-backend | FastAPI | ninguno (interno) | API REST |
| squidmgr-proxy | Squid 6.12 | 3128 | Proxy con SSL Bump |
| squidmgr-frontend | React + Nginx | 3000 | Panel web |

> El backend ya no publica el puerto 8000 al host: el frontend le habla por la red interna de Docker. Si necesitas acceder a la API directamente (por ejemplo para depurar), usa `docker exec` o publica el puerto tú mismo en un override de desarrollo.

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

# Probar el backend desde dentro de su propio contenedor
# (el puerto no está publicado al host)
docker exec squidmgr-backend python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/health').read())"
# Debe responder: {"status":"ok"}

# Probar el panel web
curl -o /dev/null -w "%{http_code}" http://localhost:3000/
# Debe responder: 200
```

### Paso 6: Acceder al panel

1. Abre tu navegador: **http://IP_DEL_SERVIDOR:3000**
2. Consulta la contraseña generada para `admin`:
   ```bash
   docker compose logs backend | grep -A3 "Administrador inicial"
   ```
   (Si definiste `ADMIN_INITIAL_PASSWORD` en el `.env`, usa esa.)
3. Inicia sesión con `admin` y esa contraseña
4. El panel te pedirá **cambiarla** antes de dejarte entrar — es obligatorio en el primer acceso
5. ¡Ya estás dentro!

---

## Configuración post-instalación

### Cambiar la contraseña del admin

Hazlo **siempre desde el panel**: inicia sesión → icono de llave en la barra lateral → "Cambiar contraseña". Cambiar la contraseña así invalida cualquier sesión abierta en otros navegadores.

> No la cambies escribiendo directamente en la base de datos ni con un script que solo actualice `password_hash`: el sistema también registra cuándo se cambió la contraseña para poder cerrar sesiones antiguas, y un cambio manual que se salte ese paso deja huérfanas las protecciones de sesión.

### Crear un usuario del proxy

Desde el panel:
1. Ve a **"Usuarios"**
2. Click en **"Nuevo usuario"**
3. Introduce usuario y contraseña (mínimo 8 caracteres)
4. Click en **"Crear usuario"**

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

El esquema de la base de datos se gestiona con Alembic: las migraciones pendientes se aplican automáticamente al arrancar el backend. Si actualizas una instalación muy antigua (anterior a la adopción de Alembic), revisa el log del backend tras el `up -d`:

```bash
docker compose logs backend | grep -i alembic
```
