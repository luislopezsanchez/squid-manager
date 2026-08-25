# SquidManager

<p align="center">
  <strong>Panel web de gestión para Squid Proxy con Docker, FastAPI, React y SSL Bump</strong>
</p>

<p align="center">
  <img alt="License" src="https://img.shields.io/badge/license-Apache--2.0-blue.svg">
  <img alt="Squid" src="https://img.shields.io/badge/Squid-6.12-green">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0.115-teal">
  <img alt="React" src="https://img.shields.io/badge/React-18-blue">
  <img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-16-blue">
  <img alt="Docker" src="https://img.shields.io/badge/Docker-Compose-blue">
</p>

---

## 📋 Tabla de contenidos

- [Descripción](#-descripción)
- [Características](#-características)
- [Arquitectura](#-arquitectura)
- [Requisitos](#-requisitos)
- [Instalación rápida](#-instalación-rápida)
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

El sistema está pensado para ser **escalable y modular**: la base de datos es la fuente de verdad, el archivo `squid.conf` se genera dinámicamente desde la web, y todo funciona dentro de contenedores Docker.

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
- **Todo en Docker** — Un solo comando levanta todo

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

### Sistema operativo
- Linux (Ubuntu 24.04 recomendado)
- También funciona en cualquier sistema con Docker

### Software
- **Docker** 20.10+ ([instalación](https://docs.docker.com/engine/install/))
- **Docker Compose** v2+ ([instalación](https://docs.docker.com/compose/install/))
- **Git** (para clonar el repo)

### Hardware mínimo
- **CPU:** 2 núcleos (4 recomendado para compilación de Squid)
- **RAM:** 2 GB (4 GB recomendado)
- **Disco:** 5 GB libres
- **Red:** Puerto 3128 accesible para los clientes del proxy

---

## 🚀 Instalación rápida

```bash
# 1. Clonar el repositorio
git clone https://github.com/luislopezsanchez/squid-manager.git
cd squid-manager

# 2. Copiar configuración
cp .env.example .env

# 3. Editar .env: DB_PASS y SECRET_KEY son OBLIGATORIOS
#    Genera valores aleatorios con: openssl rand -hex 32
nano .env

# 4. Levantar todo el sistema
docker compose up -d

# 5. Esperar a que Squid compile (primera vez: ~10-15 minutos)
#    Ver progreso:
docker compose logs -f squid

# 6. Cuando vea "Accepting HTTP Socket connections", está listo
```

### Acceso:
| Servicio | URL |
|----------|-----|
| **Panel web** | http://localhost:3000 |
| **Proxy Squid** | localhost:3128 |

> La API del backend (puerto 8000) no se publica al host: el panel habla con ella por la red interna de Docker. La documentación interactiva (`/docs`) solo está disponible si arrancas con `DEBUG=true` en el `.env`.

### Primer acceso:
No hay contraseña por defecto. El usuario `admin` se crea con una **contraseña aleatoria** que aparece **una sola vez** en el log del backend:

```bash
docker compose logs backend | grep -A3 "Administrador inicial"
```

Se te pedirá cambiarla antes de poder usar el panel. Si prefieres fijarla tú mismo, define `ADMIN_INITIAL_PASSWORD` en el `.env` antes del primer arranque.

Para una guía detallada de instalación, ver [docs/installation.md](docs/installation.md).

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

La documentación interactiva (Swagger/OpenAPI) solo está disponible con `DEBUG=true`, en `http://localhost:8000/docs` desde la red interna de Docker.

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

| Documento | Descripción |
|-----------|-------------|
| [docs/installation.md](docs/installation.md) | Guía paso a paso de instalación |
| [docs/configuration.md](docs/configuration.md) | Todas las opciones de configuración |
| [docs/architecture.md](docs/architecture.md) | Arquitectura técnica detallada |
| [docs/authentication.md](docs/authentication.md) | Cuentas, sesiones, roles y grupos |
| [docs/ssl-bump.md](docs/ssl-bump.md) | Guía de SSL Bump + certificados CA |
| [docs/backup-restore.md](docs/backup-restore.md) | Backup, restore y migración |
| [docs/production.md](docs/production.md) | Despliegue en producción |
| [docs/api-reference.md](docs/api-reference.md) | Documentación completa de la API |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Cómo contribuir al proyecto |

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

### No recuerdo la contraseña inicial del admin
Cámbiala desde una sesión de base de datos, o revisa si sigue en el log:
```bash
docker compose logs backend | grep -A3 "Administrador inicial"
```

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