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
- 🏷️ **ACLs visuales** — Crea listas de control de acceso por dominio, IP, horario, regex, puerto, método HTTP, etc. (14 tipos soportados)
- 📋 **Reglas de acceso** — Ordena reglas `http_access` con botones ▲▼ (drag-and-drop)
- 🐌 **Delay Pools** — Control de ancho de banda por usuario con interfaz visual (sin necesidad de entender el formato `64000/64000 64000/32000`)
- ⚙️ **Configuración general** — Puerto, caché, logging, realm, hostname visible, todo editable desde la web

### Autenticación
- 👥 **Usuarios locales** — Gestión completa de usuarios con autenticación básica (htpasswd)
- 🔗 **LDAP / Active Directory** — Integración con directorio externo, con test de conexión integrado
- 🔐 **Panel seguro** — Login con JWT para administradores

### Seguridad
- 🔐 **SSL Bump** — Intercepta y filtra tráfico HTTPS (no solo HTTP)
- 🚫 **Bloqueo HTTPS por SNI** — Bloquea dominios antes de desencriptar (ej: Facebook, YouTube por HTTPS)
- 📝 **Auditoría completa** — Log de todos los cambios: quién, qué, cuándo
- 🔐 **Certificado CA** — Generación automática + descarga desde el panel

### Operación
- ⚡ **Aplicar cambios en caliente** — `squid -k reconfigure` desde un botón
- 🔄 **Cambio de puerto automático** — Detecta cambios de puerto y recrea el contenedor
- 📊 **Dashboard** — Estado del proxy en tiempo real
- 🐳 **Todo en Docker** — Un solo comando levanta todo

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

**Principio clave:** La base de datos es la fuente de verdad. El `squid.conf` se genera dinámicamente con Jinja2 desde los datos en PostgreSQL. Al pulsar "Aplicar Cambios", el backend genera el archivo, lo escribe al volumen compartido, y recarga Squid.

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

# 3. Editar .env con tus valores (opcional, los defaults funcionan)
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
| **API docs (Swagger)** | http://localhost:8000/docs |
| **Proxy Squid** | localhost:3128 |

### Credenciales por defecto:
| Tipo | Usuario | Contraseña |
|------|---------|-----------|
| **Admin del panel** | `admin` | `admin123` |
| **Usuario proxy de prueba** | `testuser` | `test123` |

> ⚠️ **Importante:** Cambia las credenciales por defecto en producción. Ver [Configuración](#-configuración).

Para una guía detallada de instalación, ver [docs/installation.md](docs/installation.md).

---

## 🔧 Configuración

Todas las configuraciones se manejan через el archivo `.env`:

```env
# PostgreSQL
DB_NAME=squidmanager
DB_USER=squid
DB_PASS=squidpass123

# Seguridad del panel
SECRET_KEY=change-this-to-a-random-64-char-string
TOKEN_EXPIRE=480

# Puerto del proxy
SQUID_PORT=3128
PROXY_PORT=3128
```

Para ver todas las opciones, ver [docs/configuration.md](docs/configuration.md).

---

## 📚 Primeros pasos

Después de la instalación:

1. **Abre el panel** → http://localhost:3000
2. **Inicia sesión** → admin / admin123
3. **Crea un usuario del proxy** → Página "Usuarios" → "+ Nuevo Usuario"
4. **Configura tu navegador** con el proxy:
   - IP: `localhost` (o la IP del servidor)
   - Puerto: `3128`
   - Usuario: el que creaste
   - Contraseña: la que configuraste
5. **Navega** → Tu tráfico pasa por Squid
6. **Crea una ACL** → Página "ACLs" → "+ Nueva ACL" (ej: bloquear `.facebook.com`)
7. **Crea una regla** → Página "Reglas de Acceso" → "+ Nueva Regla" → `deny` + tu ACL
8. **Aplica cambios** → Botón "⚡ Aplicar Cambios" en el sidebar
9. **Prueba** → Intenta navegar a Facebook → debería bloquearse

---

## 🔐 SSL Bump (HTTPS)

SquidManager incluye **SSL Bump**, que permite interceptar y filtrar tráfico HTTPS.

### Cómo funciona:
1. Squid genera una **CA raíz** automáticamente al arrancar
2. Para cada conexión HTTPS, Squid genera un certificado dinámico firmado por esa CA
3. Squid desencripta el tráfico, aplica las reglas (ACLs, delay pools), y lo vuelve a encriptar
4. El navegador del cliente debe confiar en la CA de Squid

### Para habilitarlo en los clientes:
1. Abre el panel → **"🔐 Certificado SSL"**
2. Descarga el archivo `squidmanager-ca.crt`
3. Instálalo en el almacén de **"Entidades de certificación raíz de confianza"** del sistema/navegador
4. Reinicia el navegador

Para instrucciones detalladas por sistema operativo, ver [docs/ssl-bump.md](docs/ssl-bump.md).

---

## 🖥️ Panel web

El panel tiene 9 secciones:

| Sección | Icono | Función |
|---------|-------|---------|
| Dashboard | 📊 | Estado del proxy, accesos rápidos |
| Usuarios | 👥 | CRUD de usuarios del proxy |
| ACLs | 🏷️ | CRUD de listas de control de acceso |
| Reglas de Acceso | 📋 | CRUD de reglas http_access con reorder |
| Ancho de Banda | 🐌 | CRUD de delay pools (limitación de velocidad) |
| LDAP | 🔗 | Configuración LDAP/Active Directory |
| Configuración | ⚙️ | Parámetros generales de Squid |
| Certificado SSL | 🔐 | Descarga CA + instrucciones de instalación |
| Auditoría | 📝 | Log de todos los cambios realizados |

---

## 🔌 API REST

La API está documentada con Swagger/OpenAPI en http://localhost:8000/docs

### Endpoints principales:

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/auth/login` | Login admin (JWT) |
| GET | `/api/proxy-users/` | Listar usuarios del proxy |
| POST | `/api/proxy-users/` | Crear usuario |
| GET | `/api/acls/` | Listar ACLs |
| POST | `/api/acls/` | Crear ACL |
| GET | `/api/access-rules/` | Listar reglas |
| PUT | `/api/access-rules/reorder` | Reordenar reglas |
| GET | `/api/delay-pools/` | Listar delay pools |
| GET | `/api/squid/settings` | Ver configuración |
| POST | `/api/squid/apply` | Aplicar cambios a Squid |
| GET | `/api/squid/status` | Estado de Squid |
| GET | `/api/squid/ca-cert` | Descargar certificado CA |
| GET | `/api/ldap/config` | Ver config LDAP |
| POST | `/api/ldap/test` | Probar conexión LDAP |
| GET | `/api/audit/` | Listar log de auditoría |

Para documentación completa, ver [docs/api-reference.md](docs/api-reference.md).

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
│   └── app/
│       ├── main.py             # Entry point de FastAPI
│       ├── config.py           # Configuración (env vars)
│       ├── database.py         # Conexión SQLAlchemy
│       ├── models/             # Modelos de datos (8 modelos)
│       ├── schemas/            # Schemas Pydantic (validación)
│       ├── routes/             # Endpoints REST (8 routers)
│       ├── services/           # Lógica de negocio
│       │   ├── auth_service.py     # JWT + bcrypt
│       │   ├── config_generator.py # Jinja2 → squid.conf
│       │   └── squid_service.py    # Control de Squid via Docker SDK
│       └── templates/
│           └── squid.conf.j2   # Template Jinja2 del squid.conf
│
├── frontend/                   # Panel web (React + Vite + TailwindCSS)
│   ├── Dockerfile
│   ├── package.json
│   ├── nginx.conf              # Proxy reverso al backend
│   └── src/
│       ├── main.tsx            # Entry point + rutas
│       ├── pages/              # 9 páginas
│       ├── components/         # Layout, Toast, etc.
│       └── api/client.ts       # Cliente HTTP
│
├── squid/                      # Contenedor Squid (compilado desde fuente)
│   ├── Dockerfile              # Compila Squid 6.12 con OpenSSL + ssl-crtd
│   └── entrypoint.sh           # CA, ssl_crtd, squid.conf inicial, arranque
│
├── docs/                       # Documentación
│   ├── installation.md         # Guía detallada de instalación
│   ├── configuration.md        # Todas las opciones de configuración
│   ├── architecture.md         # Arquitectura técnica
│   ├── ssl-bump.md             # Guía de SSL Bump + certificados
│   ├── api-reference.md        # Documentación de la API
│   └── project-log.md          # Bitácora del proyecto
│
└── examples/                   # Ejemplos y configs
    ├── docker-compose.override.yml  # Override para producción
    └── acl-examples.md              # Ejemplos de ACLs
```

---

## 📚 Documentación

| Documento | Descripción |
|-----------|-------------|
| [docs/installation.md](docs/installation.md) | Guía paso a paso de instalación |
| [docs/configuration.md](docs/configuration.md) | Todas las opciones de configuración |
| [docs/architecture.md](docs/architecture.md) | Arquitectura técnica detallada |
| [docs/ssl-bump.md](docs/ssl-bump.md) | Guía de SSL Bump + certificados CA |
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
Instala el certificado CA desde el panel → "🔐 Certificado SSL".

### No puedo acceder al panel
```bash
docker compose ps    # Verificar que todos los contenedores están UP
docker compose logs backend    # Ver errores del backend
```

### Cambiar el puerto del proxy
1. Panel → ⚙️ Configuración → `http_port` → cambiar valor → Guardar
2. Editar `.env`: `SQUID_PORT=nuevo_puerto` y `PROXY_PORT=nuevo_puerto`
3. Panel → ⚡ Aplicar Cambios (el sistema recrea el contenedor automáticamente)

---

## 📝 Licencia

Apache-2.0 — Ver [LICENSE](LICENSE) para más detalles.

---

## 🤝 Contribuir

Ver [CONTRIBUTING.md](CONTRIBUTING.md) para saber cómo contribuir al proyecto.