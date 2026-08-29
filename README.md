# SquidManager

**Español · [English](README.en.md) · [Português](README.pt.md)**

<p align="center">
  <strong>Panel web de gestión para Squid Proxy, con FastAPI, React y SSL Bump</strong><br>
  Se despliega <strong>con Docker</strong> o <strong>sin Docker</strong>
</p>

<p align="center">
  <img alt="License" src="https://img.shields.io/badge/license-Apache--2.0-blue.svg">
  <img alt="Squid" src="https://img.shields.io/badge/Squid-6.12-green">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0.115-teal">
  <img alt="React" src="https://img.shields.io/badge/React-18-blue">
  <img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-16-blue">
  <img alt="Docker" src="https://img.shields.io/badge/Docker-Compose-blue">
</p>

> ### 🌍 Idiomas de la documentación
>
> | | Español | English | Português |
> |---|---|---|---|
> | **README** | este | [README.en.md](README.en.md) | [README.pt.md](README.pt.md) |
> | **Instalación con Docker** | [ver](docs/installation.md) | [view](docs/installation.en.md) | [ver](docs/installation.pt.md) |
> | **Instalación sin Docker** | [ver](docs/instalacion-nativa.md) | [view](docs/instalacion-nativa.en.md) | [ver](docs/instalacion-nativa.pt.md) |
>
> El resto de la documentación está solo en español. El **panel y los mensajes
> de la API** sí hablan los tres idiomas: se elige en el selector de la barra
> superior — ver [docs/idiomas.md](docs/idiomas.md).

---

## 📋 Tabla de contenidos

- [Descripción](#-descripción)
- [Características](#-características)
- [Arquitectura](#-arquitectura)
- [Requisitos](#-requisitos)
- [Instalación](#-instalación)
  - [Modo A — con Docker](#modo-a--con-docker)
  - [Modo B — sin Docker (nativa)](#modo-b--sin-docker-instalación-nativa)
- [Actualizar](#-actualizar)
- [Configuración](#-configuración)
- [Primeros pasos](#-primeros-pasos)
- [SSL Bump (HTTPS)](#-ssl-bump-https)
- [Panel web](#-panel-web)
- [API REST](#-api-rest)
- [Estructura del proyecto](#-estructura-del-proyecto)
- [Documentación](#-documentación)
- [Solución de problemas](#-solución-de-problemas)
- [Licencia](#-licencia)

---

## 📖 Descripción

**SquidManager** es una plataforma completa de gestión de Squid Proxy que permite a los administradores de red configurar y administrar un proxy Squid desde una interfaz web amigable, sin necesidad de editar archivos de configuración manualmente.

El sistema está pensado para ser **escalable y modular**: la base de datos es la fuente de verdad, el archivo `squid.conf` se genera dinámicamente desde la web, y todo funciona en contenedores Docker **o como servicios del sistema**, según el modo de despliegue que elijas.

---

## ✨ Características

### Gestión de proxy
- **ACLs visuales** — Crea listas de control de acceso por dominio, IP, horario, regex, puerto, método HTTP y más (27 tipos soportados)
- **Reglas de acceso** — Ordena reglas `http_access` con botones de subir/bajar
- **Grupos de usuarios** — Agrupa usuarios locales o LDAP y aplica políticas de acceso a todo el grupo de una vez
- **Delay Pools** — Control de ancho de banda por usuario con interfaz visual (sin necesidad de entender el formato `64000/64000 64000/32000`)
- **Configuración general** — Puerto, caché, logging, realm, hostname visible, todo editable desde la web

### Autenticación
- **Usuarios locales** — Gestión completa de usuarios con autenticación básica (htpasswd), con fecha de caducidad opcional
- **LDAP / Active Directory** — Integración con directorio externo, con test de conexión integrado y sincronización paginada
- **Panel seguro** — Login con JWT, roles (superadmin / admin / solo lectura) y cambio de contraseña obligatorio en el primer acceso

### Seguridad
- **SSL Bump** — Intercepta y filtra tráfico HTTPS (no solo HTTP)
- **Bloqueo HTTPS por SNI** — Bloquea dominios antes de desencriptar (ej: Facebook, YouTube por HTTPS)
- **Exclusión de dominios sensibles** — Banca, sanidad o apps con *certificate pinning* pueden excluirse del descifrado
- **Auditoría completa** — Log de todos los cambios: quién, qué, cuándo
- **Certificado CA** — Generación automática + descarga desde el panel, con instaladores para Windows, macOS e iOS

### Operación
- **Aplicar cambios en caliente** — Valida la configuración contra Squid antes de escribirla; recarga o reinicia según haga falta
- **Cambio de puerto automático** — Detecta cambios de puerto y recrea el contenedor sin perder la configuración si algo falla
- **Dashboard** — Tráfico en tiempo real, top usuarios y dominios, estado del sistema
- **Backup y migración** — Exporta toda la configuración a JSON (incluidos grupos y usuarios LDAP) o importa un `squid.conf` tradicional
- **Notificaciones** — Avisos por email o Telegram cuando se aplican cambios o se detecta actividad sospechosa

### Despliegue e idiomas
- **Dos modos de despliegue** — Con Docker (un solo comando levanta todo) o **sin Docker**, con Squid, el panel y PostgreSQL como servicios del sistema. Se elige con `DEPLOY_MODE` y el resto del producto es idéntico — ver [docs/instalacion-nativa.md](docs/instalacion-nativa.md)
- **Sin root** — En modo nativo el panel corre con su propio usuario y un sudoers de tres órdenes, bastante menos de lo que concede el socket de Docker
- **Panel en tres idiomas** — Español, inglés y portugués, seleccionable desde el propio panel. Los mensajes de error de la API también se traducen, y las páginas de error que ven los usuarios del proxy siguen su propio idioma — ver [docs/idiomas.md](docs/idiomas.md)

---

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────────────┐
│                    Docker Network                        │
│                                                          │
│  ┌──────────┐     ┌──────────┐     ┌──────────┐        │
│  │ Frontend  │     │ Backend  │     │ Squid    │        │
│  │ (React)  │────▶│ (FastAPI)│────▶│ Proxy    │        │
│  │ :3000    │     │ :8000    │     │ :3128    │        │
│  └──────────┘     └────┬─────┘     └──────────┘        │
│                        │                                 │
│                   ┌────▼─────┐                          │
│                   │PostgreSQL│                          │
│                   │  :5432   │                          │
│                   └──────────┘                          │
└─────────────────────────────────────────────────────────┘

Flujo de configuración:
  Admin → Panel web → API REST → PostgreSQL → Jinja2 → squid.conf → Squid
```

**Principio clave:** La base de datos es la fuente de verdad. El `squid.conf` se genera dinámicamente con Jinja2 desde los datos en PostgreSQL. Al pulsar "Aplicar Cambios", el backend genera el archivo, lo **valida ejecutando `squid -k parse` dentro del contenedor de Squid**, y solo si es válido lo escribe y recarga.

> El puerto 8000 del backend es interno: el frontend habla con la API por la red Docker, no se publica al host.

Para más detalles, ver [docs/architecture.md](docs/architecture.md).

---

## ✅ Requisitos

Los requisitos dependen del modo de despliegue.

### Con Docker

- **Sistema:** Linux (Ubuntu 24.04 recomendado), o cualquier sistema con Docker
- **Docker** 20.10+ ([instalación](https://docs.docker.com/engine/install/))
- **Docker Compose** v2+ ([instalación](https://docs.docker.com/compose/install/))
- **Git** (para clonar el repo)

### Sin Docker (instalación nativa)

- **Sistema:** Ubuntu 22.04 / 24.04 o Debian 12, x86_64 — **no** vale cualquier
  Linux, porque hace falta el paquete `squid-openssl`
- **Acceso root** y salida a internet para descargar paquetes
- Nada más: el instalador pone Squid, PostgreSQL, nginx, Node y Python

### Hardware mínimo
- **CPU:** 2 núcleos (4 recomendado; con Docker se compila Squid al construir la imagen)
- **RAM:** 2 GB (4 GB recomendado)
- **Disco:** 5 GB libres
- **Red:** Puerto 3128 accesible para los clientes del proxy

---

## 🚀 Instalación

**Lo primero es elegir el modo de despliegue.** Hay dos, y son excluyentes: en
una misma máquina se usa uno **o** el otro, nunca los dos.

| | **Modo A — con Docker** | **Modo B — sin Docker (nativo)** |
|---|---|---|
| Qué levanta | 4 contenedores | Servicios del sistema, con systemd |
| Qué exige | Docker 20.10+ y Compose v2+ | Ubuntu 22.04 / 24.04 o Debian 12, x86_64 |
| Squid | Se compila al construir la imagen | Paquete `squid-openssl`; **no compila nada** |
| Cuánto tarda | 15-30 min la primera vez, porque compila Squid | 3-5 min |
| Qué privilegios tiene el panel | El socket de Docker, que equivale a root en la máquina | Un usuario propio y tres órdenes de `sudo` |
| Hay que clonar el repo | Sí | No: basta con descargar un script |
| Elígelo si | Quieres el aislamiento de los contenedores y Docker no es problema | La política interna no permite Docker, o el equipo ya hace de proxy y una capa más sobra |

Las dos guías completas, paso a paso, están en
[docs/installation.md](docs/installation.md) (Docker) y en
[docs/instalacion-nativa.md](docs/instalacion-nativa.md) (nativa).

---

### Modo A — con Docker

Hay dos caminos. Hacen lo mismo; la diferencia es quién rellena la configuración.

| | A1: con `install.sh` | A2: manual |
|---|---|---|
| Dónde se instala | Donde hayas clonado | Donde tú quieras |
| `DB_PASS` y `SECRET_KEY` | Se generan solas | Las defines tú |
| `PROJECT_DIR` | Se rellena sola | **Tienes que ajustarla** |

#### A1 — con el instalador

Genera las claves, deja el `.env` listo y levanta los contenedores.

```bash
git clone https://github.com/luislopezsanchez/squid-manager.git
cd squid-manager
sudo ./install.sh
```

**Se instala en el directorio donde hayas clonado**, no en una ruta fija. Si
ejecutas el script suelto, fuera de un clon, usa `/opt/squid-manager`. Y puedes
imponer la ruta que quieras:

```bash
sudo INSTALL_DIR=/srv/squid ./install.sh
```

Si ya había una instalación en esa ruta, la actualiza conservando la
configuración; si tienes cambios locales sin confirmar, hace copia y se detiene
en lugar de pisarlos.

> No canalices el script directamente a `bash` desde internet: descárgalo,
> léelo y ejecútalo, que es lo que se hace arriba.

##### Si el servidor sale a internet por un proxy

`install.sh` da por hecho que hay salida directa. Cuando la red obliga a pasar
por un proxy corporativo, hay **tres** capas que necesitan configurarse por
separado —el host, el demonio de Docker y los builds— y configurar solo una
deja la instalación a medias, normalmente con un `Could not resolve` en mitad
de un `apt-get`. De eso se encarga otro script:

```bash
cp proxy.conf.example proxy.conf
```

Pon tus datos en `proxy.conf` (servidor, puerto y, si hacen falta, usuario y
contraseña; los caracteres especiales no hay que escaparlos) y ejecuta:

```bash
sudo ./install-tras-proxy.sh
```

Configura las tres capas, comprueba que cada una sale a internet y solo
entonces lanza `install.sh`. Las credenciales viven en `proxy.conf`, que está
en `.gitignore`: no se edita ningún archivo del repositorio, porque un cambio
local sin confirmar haría abortar al instalador.

Esto es solo para **instalar**. Para que Squid salga a internet a través del
proxy corporativo una vez instalado, se configura desde el panel en
**Proxy padre** — ver [docs/proxy-padre.md](docs/proxy-padre.md).

El procedimiento manual equivalente, con qué toca cada paso y qué hacer si el
proxy inspecciona TLS, está en
[docs/instalacion-tras-proxy.md](docs/instalacion-tras-proxy.md).

#### A2 — manual

Elige esta si quieres el proyecto en otra ruta o prefieres controlar cada paso.

```bash
# 1. Clonar el repositorio (en la ruta que prefieras)
git clone https://github.com/luislopezsanchez/squid-manager.git
cd squid-manager

# 2. Copiar la configuración de ejemplo
cp .env.example .env

# 3. Editar el .env (ver más abajo qué es obligatorio)
nano .env

# 4. Levantar todo el sistema
docker compose up -d

# 5. Esperar a que Squid compile (primera vez: ~10-15 minutos)
#    Ver progreso:
docker compose logs -f squid

# 6. Cuando veas "Accepting HTTP Socket connections", está listo
```

**Tres valores hay que tocar sí o sí en el `.env`:**

```env
DB_PASS=            # obligatorio: openssl rand -hex 16
SECRET_KEY=         # obligatorio: openssl rand -hex 32
PROJECT_DIR=        # la ruta ABSOLUTA donde acabas de clonar el proyecto
```

> **`PROJECT_DIR` es el que se olvida.** Viene con `/opt/squid-manager` de
> ejemplo. Si clonaste en otro sitio y no lo cambias, el sistema arranca y
> funciona con normalidad, pero **cambiar el puerto del proxy desde el panel
> deja de actualizar el `.env`**, y el puerto vuelve al valor anterior en el
> siguiente `docker compose up -d`. Comprueba con `pwd` y pon esa ruta exacta.
> (Con A1 no tienes que preocuparte: la rellena el instalador.)

#### Acceso y primer inicio de sesión (Docker)

| Servicio | URL |
|----------|-----|
| **Panel web** | http://IP_DEL_SERVIDOR:3000 |
| **Proxy Squid** | IP_DEL_SERVIDOR:3128 |

No hay contraseña por defecto. El usuario `admin` se crea con una **contraseña
aleatoria** que aparece **una sola vez** en el log del backend:

```bash
docker compose logs backend | grep -A3 "Administrador inicial"
```

Se te pedirá cambiarla antes de poder usar el panel. Si prefieres fijarla tú,
define `ADMIN_INITIAL_PASSWORD` en el `.env` antes del primer arranque.

> La API del backend (puerto 8000) no se publica al host: el panel habla con
> ella por la red interna de Docker. La documentación interactiva (`/docs`)
> solo está disponible si arrancas con `DEBUG=true` en el `.env`.

---

### Modo B — sin Docker (instalación nativa)

Squid, el panel, PostgreSQL y nginx corriendo como servicios del sistema. **No
hay que clonar el repositorio, ni editar ningún `.env`, ni compilar nada**: el
instalador se encarga de todo.

Sobre un Ubuntu 22.04 / 24.04 o Debian 12 recién instalado, con acceso root:

```bash
# 1. Descargar el instalador
wget https://raw.githubusercontent.com/luislopezsanchez/squid-manager/main/install-nativo.sh

# 2. Leerlo antes de ejecutarlo como root (siempre, venga de donde venga)
less install-nativo.sh

# 3. Darle permisos de ejecución
chmod +x install-nativo.sh

# 4. Ejecutarlo
sudo ./install-nativo.sh
```

Tarda entre tres y cinco minutos. Al terminar imprime la URL del panel, el
usuario y la contraseña inicial.

**Si quieres otros puertos**, se indican como variables de entorno (fíjate en
el `-E`, que es lo que hace que `sudo` las conserve):

```bash
WEB_PORT=8080 PROXY_PORT=3130 sudo -E ./install-nativo.sh
```

| Variable | Por defecto | Qué es |
|---|---|---|
| `WEB_PORT` | `3000` | Puerto del panel |
| `PROXY_PORT` | `3128` | Puerto del proxy |
| `API_PORT` | `8000` | Puerto interno de la API (solo escucha en localhost) |
| `INSTALL_DIR` | `/opt/squid-manager` | Dónde vive el código |
| `APP_USER` | `squidmgr` | Usuario con el que corre el panel |

#### Qué hace el instalador, en orden

1. Comprueba que el sistema es compatible.
2. Instala los paquetes: `squid-openssl`, PostgreSQL, nginx, Node, Python y
   `apache2-utils`. **`squid-openssl`, no `squid`**: el paquete a secas es la
   variante GnuTLS, sin SSL bump ni generador de certificados.
3. Crea el usuario `squidmgr`, con `proxy` como grupo primario.
4. Clona el código en `/opt/squid-manager`.
5. Crea la base de datos PostgreSQL.
6. Genera la CA para SSL Bump e instala el helper de autenticación.
7. Escribe un sudoers con **tres órdenes literales**, sin comodines.
8. Prepara el entorno de Python, el `.env` y la unidad de systemd.
9. Compila el panel web y configura nginx.
10. Arranca los servicios y comprueba que responden.

#### Acceso y primer inicio de sesión (nativo)

El instalador termina imprimiendo exactamente esto:

```
  Panel:    http://IP_DEL_SERVIDOR:3000
  Proxy:    IP_DEL_SERVIDOR:3128
  Usuario:  admin
  Clave:    <contraseña generada al azar>
```

Esa contraseña **no se vuelve a mostrar**, y el panel te pedirá cambiarla en el
primer acceso. Si la pierdes antes de entrar, está en el log:

```bash
journalctl -u squidmanager | grep -A3 "Administrador inicial"
```

Para operar el servicio después:

```bash
systemctl status squid squidmanager nginx    # estado
journalctl -u squidmanager -f                # registros del panel
```

Las diferencias de comportamiento frente a Docker —dónde vive el puerto, cómo
se mide el tráfico, qué estado muestra el panel— están en
[docs/instalacion-nativa.md](docs/instalacion-nativa.md).

---

### Después de instalar, con cualquiera de los dos modos

**1. Abre el puerto del proxy en el firewall del servidor.** No lo hace ni el
instalador ni el panel:

```bash
sudo ufw allow 3128/tcp
```

Sin esa regla Squid funciona pero los clientes no llegan, y el síntoma es una
conexión que se queda colgada sin ningún mensaje de error.

**2. Crea el primer usuario del proxy**, en *Usuarios → Nuevo usuario*. Hasta
entonces no navegará nadie: el proxy exige credenciales desde el minuto uno y
todavía no existe ninguna. Es a propósito, y está explicado arriba en
[Primeros pasos](#-primeros-pasos).

---

## 🔄 Actualizar

```bash
cd /ruta/a/squid-manager && git pull && docker compose up -d --build
```

Las migraciones de base de datos se aplican solas al arrancar el backend, y **tu
configuración se conserva**: usuarios, reglas, puertos y certificados no se
tocan.

> **El `--build` no es opcional.** Sin él, Docker reutiliza las imágenes que ya
> tiene y el código nuevo no llega a ejecutarse, aunque el `git pull` haya ido
> bien. Todo parece correcto —repositorio al día, contenedores arrancados— pero
> sigues usando la versión anterior.

Para comprobar que fue bien:

```bash
cd /ruta/a/squid-manager && git log --oneline -1 && git status --porcelain | wc -l && docker compose ps
```

Debes ver el commit esperado, **0** ficheros pendientes y los cuatro
contenedores en `healthy`.

Ver [docs/actualizacion.md](docs/actualizacion.md) para verificar la revisión de
la base de datos, resolver un `git pull` que aborta, una migración que falla, o
volver a una versión anterior.

---

## 🔧 Configuración

Todas las configuraciones se manejan a través del archivo `.env`:

```env
# PostgreSQL
DB_NAME=squidmanager
DB_USER=squid
DB_PASS=                    # OBLIGATORIO: openssl rand -hex 16

# Seguridad del panel
SECRET_KEY=                 # OBLIGATORIO: openssl rand -hex 32
TOKEN_EXPIRE=480
ADMIN_INITIAL_PASSWORD=     # vacío = se genera al azar, visible una vez en el log
BCRYPT_COST=12

# Red y CORS
CORS_ORIGINS=                     # vacío si el panel se sirve desde su propia URL
TRUSTED_PROXY_HOSTS=frontend      # hosts de los que se acepta X-Forwarded-For
DEBUG=false                       # true expone /docs sin autenticación

# Rutas
PROJECT_DIR=/opt/squid-manager    # ruta ABSOLUTA de este directorio; install.sh la rellena

# Puertos
WEB_PORT=3000
PROXY_PORT=3128                   # puerto del proxy; lo actualiza el panel al cambiarlo
```

> `PROJECT_DIR` debe apuntar a donde está el proyecto: el backend la usa para
> recrear el contenedor de Squid con Compose al cambiar el puerto. `install.sh`
> la escribe sola; si instalas a mano o mueves el proyecto, ajústala.

Para ver todas las opciones, ver [docs/configuration.md](docs/configuration.md).

---

## 📚 Primeros pasos

Después de la instalación:

> **Recién instalado, el proxy no deja pasar a nadie, y es a propósito.**
> Squid arranca negando todo salvo `localhost`; el panel lo sustituye enseguida
> por la configuración definitiva, que exige usuario y contraseña. Hasta que
> crees el primer usuario del proxy no navegará nadie. Vale para los dos modos
> de despliegue: una instalación recién hecha no puede quedar abierta a la red
> mientras su dueño ni siquiera ha entrado al panel.

1. **Abre el panel** → http://localhost:3000
2. **Inicia sesión** con `admin` y la contraseña generada (ver arriba)
3. **Cambia la contraseña** cuando el panel te lo pida
4. **Crea un usuario del proxy** → Página "Usuarios" → "Nuevo usuario"
5. **Configura tu navegador** con el proxy:
   - IP: `localhost` (o la IP del servidor)
   - Puerto: `3128`
   - Usuario: el que creaste
   - Contraseña: la que configuraste
6. **Navega** → Tu tráfico pasa por Squid
7. **Crea una ACL** → Página "ACLs" → "Nueva ACL" (ej: bloquear `.facebook.com`)
8. **Crea una regla** → Página "Reglas de acceso" → "Nueva regla" → `deny` + tu ACL
9. **Aplica cambios** → Botón "Aplicar cambios" en el sidebar
10. **Prueba** → Intenta navegar a Facebook → debería bloquearse

---

## 🔐 SSL Bump (HTTPS)

SquidManager incluye **SSL Bump**, que permite interceptar y filtrar tráfico HTTPS.

### Cómo funciona:
1. Squid genera una **CA raíz** automáticamente al arrancar
2. Para cada conexión HTTPS, Squid genera un certificado dinámico firmado por esa CA
3. Squid desencripta el tráfico, aplica las reglas (ACLs, delay pools), y lo vuelve a encriptar
4. El navegador del cliente debe confiar en la CA de Squid

Los dominios que no deben interceptarse (banca, sanidad, apps con *certificate pinning*) se pueden excluir del descifrado desde **Configuración → Seguridad → dominios excluidos**.

### Para habilitarlo en los clientes:
1. Abre el panel → **"Certificado"**
2. Descarga el archivo `squidmanager-ca.crt` (o el instalador para tu sistema)
3. Instálalo en el almacén de **"Entidades de certificación raíz de confianza"** del sistema/navegador
4. Reinicia el navegador

Para instrucciones detalladas por sistema operativo, ver [docs/ssl-bump.md](docs/ssl-bump.md).

---

## 🖥️ Panel web

El panel se organiza en tres grupos:

| Grupo | Sección | Función |
|-------|---------|---------|
| **Vigilancia** | Dashboard | Estado del proxy, tráfico en tiempo real, top usuarios y dominios |
| | Registros | Visor del access.log, con filtros y alertas de fuerza bruta |
| | Auditoría | Log de todos los cambios realizados |
| **Políticas** | Usuarios | CRUD de usuarios del proxy |
| | Grupos | Agrupa usuarios y aplica políticas al grupo completo |
| | ACLs | CRUD de listas de control de acceso |
| | Reglas de acceso | CRUD de reglas `http_access` con reordenamiento |
| | Ancho de banda | CRUD de delay pools (limitación de velocidad) |
| **Sistema** | LDAP | Configuración LDAP/Active Directory |
| | Certificado | Descarga CA + instaladores por sistema operativo |
| | Configuración | Parámetros generales de Squid |
| | Notificaciones | Avisos por email y Telegram |
| | Backup y migración | Exportar/restaurar configuración, importar squid.conf |
| | Administradores | Gestión de cuentas del panel (solo superadmin) |

---

## 🔌 API REST

**La documentación interactiva no es accesible desde fuera del servidor.** El
puerto 8000 no se publica al host, así que `http://TU_SERVIDOR:8000/docs` nunca
responde — y en una máquina con otros servicios podrías acabar viendo la API de
otro contenedor. Además solo se registra con `DEBUG=true`; con el valor por
defecto devuelve 404.

Si necesitas consultarla:

```bash
# 1. DEBUG=true en el .env, y recrear el backend
docker compose up -d --force-recreate backend
```

```bash
# 2. Desde el propio servidor, contra la IP del contenedor
curl http://$(docker inspect squidmgr-backend --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'):8000/openapi.json
```

Para abrir la interfaz de Swagger en tu navegador hace falta un túnel SSH hasta
esa IP del contenedor, ya que el servidor sí la alcanza pero tu equipo no.

> Vuelve a dejar `DEBUG=false` al terminar: esa ruta se sirve sin
> autenticación.

El panel usa la API a través de nginx, en `/api/`, y ese camino sí está
publicado — es el que responde en el puerto del panel.

### Endpoints principales:

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/auth/login` | Login admin (JWT) |
| GET | `/api/proxy-users/` | Listar usuarios del proxy |
| POST | `/api/proxy-users/` | Crear usuario |
| GET | `/api/groups/` | Listar grupos de usuarios |
| GET | `/api/acls/` | Listar ACLs |
| POST | `/api/acls/` | Crear ACL |
| GET | `/api/access-rules/` | Listar reglas |
| PUT | `/api/access-rules/reorder` | Reordenar reglas |
| GET | `/api/delay-pools/` | Listar delay pools |
| GET | `/api/squid/settings` | Ver configuración |
| POST | `/api/squid/apply` | Validar y aplicar cambios a Squid |
| GET | `/api/squid/status` | Estado de Squid |
| GET | `/api/squid/ca-cert` | Descargar certificado CA |
| GET | `/api/ldap/config` | Ver config LDAP |
| POST | `/api/ldap/test` | Probar conexión LDAP |
| GET | `/api/backup/export` | Exportar toda la configuración a JSON |
| GET | `/api/metrics/dashboard` | Métricas del dashboard |
| GET | `/api/logs/access` | Consultar el access.log |
| GET | `/api/audit/` | Listar log de auditoría |

Son 14 routers con 72 endpoints en total. Para la documentación completa, ver [docs/api-reference.md](docs/api-reference.md).

---

## 📁 Estructura del proyecto

```
squid-manager/
├── docker-compose.yml          # Orquestación de contenedores
├── .env.example                # Template de configuración
├── README.md                   # Este archivo
├── LICENSE                     # Apache-2.0
├── CHANGELOG.md                # Historial de versiones
├── CONTRIBUTING.md             # Guía para contribuidores
│
├── backend/                    # API REST (Python + FastAPI)
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── migrations/             # Migraciones del esquema (Alembic)
│   └── app/
│       ├── main.py             # Entry point de FastAPI + migraciones al arrancar
│       ├── config.py           # Configuración (env vars)
│       ├── database.py         # Conexión SQLAlchemy
│       ├── models/             # Modelos de datos (11 modelos)
│       ├── schemas/            # Schemas Pydantic (validación)
│       ├── routes/             # Endpoints REST (14 routers)
│       ├── services/           # Lógica de negocio
│       │   ├── auth_service.py     # JWT + bcrypt, roles
│       │   ├── config_generator.py # Jinja2 → squid.conf
│       │   ├── squid_service.py    # Control de Squid via Docker SDK, validación real
│       │   ├── squid_names.py      # Validación anti-inyección de nombres y valores
│       │   └── log_service.py      # Lectura eficiente del access.log
│       └── templates/
│           └── squid.conf.j2   # Template Jinja2 del squid.conf
│
├── frontend/                   # Panel web (React + Vite + TailwindCSS)
│   ├── Dockerfile
│   ├── package.json
│   ├── nginx.conf              # Proxy reverso al backend
│   └── src/
│       ├── main.tsx            # Entry point + rutas
│       ├── pages/              # 16 páginas
│       ├── components/         # Layout, Icons, AuthShell, Toast
│       └── api/client.ts       # Cliente HTTP
│
├── squid/                      # Contenedor Squid (compilado desde fuente)
│   ├── Dockerfile              # Compila Squid 6.12 con OpenSSL + ssl-crtd
│   ├── entrypoint.sh           # CA, ssl_crtd, squid.conf inicial, arranque
│   ├── auth_helper.py          # Helper de autenticación local + LDAP
│   └── squid-logrotate         # Rotación diaria de los logs de Squid
│
├── docs/                       # Documentación
│   ├── installation.md         # Guía detallada de instalación
│   ├── configuration.md        # Todas las opciones de configuración
│   ├── architecture.md         # Arquitectura técnica
│   ├── authentication.md       # Cuentas, sesiones y roles
│   ├── ssl-bump.md             # Guía de SSL Bump + certificados
│   ├── backup-restore.md       # Backup, restore y migración
│   ├── production.md           # Guía de despliegue en producción
│   ├── api-reference.md        # Documentación de la API
│   └── project-log.md          # Bitácora del proyecto
│
└── examples/                   # Ejemplos y configs
    ├── docker-compose.override.yml  # Ejemplo de override para producción (HTTPS, backups)
    └── acl-examples.md              # Ejemplos de ACLs
```

---

## 📚 Documentación

- [Instalación nativa, sin Docker](docs/instalacion-nativa.md)
- [Idiomas del panel, de la API y del proxy](docs/idiomas.md)

| Documento | Descripción |
|-----------|-------------|
| [docs/installation.md](docs/installation.md) | Guía paso a paso de instalación |
| [docs/configuration.md](docs/configuration.md) | Todas las opciones de configuración |
| [docs/architecture.md](docs/architecture.md) | Arquitectura técnica detallada |
| [docs/authentication.md](docs/authentication.md) | Cuentas, sesiones, roles y grupos |
| [docs/ssl-bump.md](docs/ssl-bump.md) | Guía de SSL Bump + certificados CA |
| [docs/proxy-padre.md](docs/proxy-padre.md) | Salir a Internet por otro proxy (padre e hijo) |
| [docs/instalacion-tras-proxy.md](docs/instalacion-tras-proxy.md) | Instalar en un servidor que sale por un proxy |
| [docs/actualizacion.md](docs/actualizacion.md) | Cómo actualizar, verificar y volver atrás |
| [docs/backup-restore.md](docs/backup-restore.md) | Backup, restore y migración |
| [docs/production.md](docs/production.md) | Despliegue en producción |
| [docs/api-reference.md](docs/api-reference.md) | Documentación completa de la API |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Cómo contribuir al proyecto |
| [backups/](backups/README.md) | Backups de un despliegue completo, listos para restaurar en Proxmox |

---

## 🛠️ Solución de problemas

### El contenedor Squid no arranca
```bash
docker compose logs squid
```
La primera vez, Squid se compila desde el código fuente (~10-15 minutos). Espera a ver "Accepting HTTP Socket connections".

### El proxy no bloquea sitios HTTPS
Necesitas SSL Bump. Ver [docs/ssl-bump.md](docs/ssl-bump.md).

### El navegador muestra advertencia de certificado
Instala el certificado CA desde el panel → "Certificado".

### No puedo acceder al panel
```bash
docker compose ps    # Verificar que todos los contenedores están UP
docker compose logs backend    # Ver errores del backend
```

### Reinstalé y el backend no arranca: «password authentication failed»

Sobrevivió el volumen de datos de la instalación anterior. La contraseña de una
base de datos ya creada **no se cambia poniendo otra en el `.env`**:
`POSTGRES_PASSWORD` solo surte efecto la primera vez, cuando PostgreSQL crea la
base vacía. Si el volumen ya existía, conserva la contraseña original y el
backend, que usa la nueva, no puede entrar.

Ojo con esto al reinstalar en otra ruta: Compose nombra los volúmenes según el
**nombre del directorio** del proyecto, así que dos instalaciones en rutas
distintas pero con la misma carpeta (`squid-manager`) comparten volumen.

```bash
# Ver si existe el volumen de una instalación anterior
docker volume ls | grep pgdata
```

Dos salidas:

```bash
# 1) Empezar de cero. BORRA TODOS LOS DATOS (usuarios, reglas, historial)
docker compose down -v && docker compose up -d
```

```bash
# 2) Conservar los datos: recupera la DB_PASS con la que se creó la base,
#    ponla en el .env y levanta de nuevo
docker compose up -d
```

El instalador comprueba esto antes de generar un `.env` nuevo y se detiene si
encuentra un volumen huérfano, en lugar de dejar el sistema a medias.

### No recuerdo la contraseña inicial del admin
Cámbiala desde una sesión de base de datos, o revisa si sigue en el log:
```bash
docker compose logs backend | grep -A3 "Administrador inicial"
```

### Salir a Internet a través de otro proxy (padre e hijo)

En muchas empresas el cortafuegos cierra la salida directa y todo el tráfico
tiene que pasar por el proxy corporativo. SquidManager puede colocarse detrás
de otro proxy, y la configuración se hace en **Panel → Proxy padre**.

El reparto de papeles es lo que hace que funcione:

| | Hijo (el de abajo) | Padre (el de arriba) |
|---|---|---|
| Autentica usuarios | **Sí** | No: confía en el hijo |
| Filtra por dominio | **Sí** | No |
| Intercepta HTTPS | **Sí** | **No**: solo tuneliza |
| Sale a Internet | No: por el padre | **Sí** |

Encadenar dos proxies necesita cuatro ajustes, y faltando cualquiera no
funciona:

1. **En el hijo**: servidor, puerto y —si las pide— credenciales del padre
2. **En el hijo**: el certificado CA del padre, si el padre también intercepta HTTPS
3. **En el padre**: `trusted_sources` con la IP del hijo, para que no le pida credenciales
4. **En el padre**: `ssl_bump_enabled = false`, porque solo uno puede interceptar HTTPS

Si ambos son SquidManager, además necesitan un `visible_hostname` distinto:
Squid rechaza como bucle lo que ya lleve su nombre en la cabecera `Via`.

Para comprobar que funciona, la última columna del registro de accesos del hijo
pasa de `HIER_DIRECT` a `FIRSTUP_PARENT`.

> **Guía completa en [docs/proxy-padre.md](docs/proxy-padre.md)**: el porqué de
> cada pieza, la configuración paso a paso, y una tabla para identificar por el
> síntoma cuál de los cuatro ajustes falta — todos dan errores que no mencionan
> la causa.

### Eximir a un grupo de la interceptación de HTTPS

En **Grupos**, cada grupo tiene la casilla **«No interceptar el HTTPS de este
grupo»**. Sus miembros navegan con el tráfico cifrado de extremo a extremo.

Sirve para dos casos habituales:

- **Equipos donde no se puede instalar el certificado**: móviles personales,
  BYOD, dispositivos de invitados
- **Herramientas que se rompen al interceptarlas**: git, npm, docker y
  cualquier aplicación con *certificate pinning*

> **Eximir del descifrado no es eximir del filtrado.** El bloqueo por dominio
> actúa sobre el SNI, antes de descifrar, así que a esos usuarios les sigue
> afectando. También siguen autenticándose y quedando registrados. Lo único que
> se pierde es la inspección de la URL completa y del contenido.

Para comprobar que está funcionando, en el registro de accesos sus conexiones
HTTPS aparecen como `TCP_TUNNEL/200 CONNECT`, sin la petición descifrada
(`GET https://…`) que sí se ve en los demás.

### Orígenes que no tienen que autenticarse

En **Configuración → Seguridad**, el ajuste `trusted_sources` acepta IPs o
redes que pueden navegar sin credenciales:

```
trusted_sources = 203.0.113.10 198.51.100.0/24
```

Pensado para un proxy hijo que ya autentica a sus propios usuarios. Vacío por
defecto: todo el mundo debe autenticarse.

> Es una exención de autenticación: indicá el origen concreto. Si esa IP es una
> salida NAT compartida, **cualquier equipo detrás de ella queda exento**.

### Usar tus propios servidores DNS (por ejemplo, un Pi-hole)

Squid resuelve los nombres por su cuenta, así que puedes indicarle a qué
servidores preguntar y hacer que la navegación del proxy herede el filtrado de
un Pi-hole, un AdGuard o el DNS interno de tu empresa.

1. Panel → Configuración → `dns_nameservers` → las IPs separadas por espacios
2. Pulsa **Probar** para comprobar que responden
3. Guardar → Aplicar cambios

```
dns_nameservers 172.27.0.1
```

Vacío = Squid usa la resolución del sistema (el comportamiento por defecto).

**Solo IPs, no nombres de host.** Squid tiene que poder preguntar sin resolver
nada primero, que es justo lo que aún no puede hacer.

> **Si pones más de uno, el filtrado deja de estar garantizado.** Squid reparte
> las consultas entre todos los servidores de la lista, no los usa como
> respaldo: añadir un DNS público junto al Pi-hole hace que la parte de
> consultas que le toquen al público se resuelva sin filtrar. Para que **todo**
> pase por el filtro, deja un único servidor.

Al aplicar, se comprueba que los servidores responden de verdad y el cambio se
rechaza si no lo hacen. Es a propósito: un DNS inalcanzable no rompe una web,
deja de resolver todas a la vez, y el síntoma no apunta a la causa.

Si el Pi-hole corre como contenedor en la misma máquina, usa la IP de la
pasarela de su red Docker (`docker network inspect`), no `127.0.0.1`: dentro
del contenedor de Squid, esa dirección es el propio Squid.

### Cambiar el puerto del proxy
1. Panel → Configuración → `http_port` → poner el puerto nuevo → Guardar
2. Panel → Aplicar cambios

No hay que editar ningún fichero a mano: el backend actualiza `PROXY_PORT` en el
`.env` y recrea el contenedor con Docker Compose, así que el cambio también
sobrevive a un `docker compose up -d` o a un reinicio de la máquina.

**Abre el puerto nuevo en el firewall del servidor** y cierra el anterior si ya
no se usa:

```bash
sudo ufw allow 8128/tcp && sudo ufw delete allow 3128/tcp
```

El panel no gestiona el firewall. Sin esa regla, Squid escucha correctamente
pero los clientes no llegan, y el síntoma es una conexión que se queda colgada
sin ningún mensaje de error.

> Squid escucha siempre en el **3128 dentro del contenedor**; el puerto que
> eliges es el que Docker publica hacia fuera. Por eso `squid.conf` muestra
> `http_port 3128` aunque los clientes se conecten a otro puerto: el puerto
> vive en un único sitio (`PROXY_PORT`), y así no puede desincronizarse.

---

## 📝 Licencia

Apache-2.0 — Ver [LICENSE](LICENSE) para más detalles.

---

## 🤝 Contribuir

Ver [CONTRIBUTING.md](CONTRIBUTING.md) para saber cómo contribuir al proyecto.
