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
</p>

---

## 📋 Descripción

SquidManager es una plataforma completa de gestión de Squid Proxy que permite a los administradores de red configurar y administrar un proxy Squid desde una interfaz web amigable, sin necesidad de editar archivos de configuración manualmente.

### Características principales:

- 🐳 **Todo en Docker** — Un solo `docker compose up` levanta todo el sistema
- 🔐 **SSL Bump** — Intercepta y filtra tráfico HTTPS (no solo HTTP)
- 🏷️ **ACLs visuales** — Crea listas de control de acceso por dominio, IP, horario, regex, etc.
- 📋 **Reglas de acceso** — Ordena reglas `http_access` con drag-and-drop
- 🐌 **Delay Pools** — Control de ancho de banda por usuario con interfaz visual
- 👥 **Usuarios del proxy** — Gestión completa de usuarios con autenticación básica
- 🔗 **LDAP** — Integración con Active Directory / OpenLDAP
- 📊 **Dashboard** — Estado del proxy en tiempo real
- 📝 **Auditoría** — Log completo de todos los cambios realizados
- ⚡ **Aplicar cambios en caliente** — `squid -k reconfigure` desde el botón "Aplicar Cambios"
- 🔐 **Certificado CA** — Descarga e instrucciones de instalación para SSL Bump

### Arquitectura:

```
┌─────────────────────────────────────────────────┐
│                 Docker Network                   │
│                                                  │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐   │
│  │ Frontend  │    │ Backend  │    │ Squid    │   │
│  │ (React)  │───▶│ (FastAPI)│───▶│ Proxy    │   │
│  │ :3000    │    │ :8000    │    │ :3128    │   │
│  └──────────┘    └────┬─────┘    └──────────┘   │
│                       │                          │
│                  ┌────▼─────┐                   │
│                  │PostgreSQL │                   │
│                  │  :5432   │                   │
│                  └──────────┘                   │
└─────────────────────────────────────────────────┘
```

## 🚀 Instalación

### Requisitos:
- Docker + Docker Compose
- Linux (Ubuntu 24.04 recomendado)

### Despliegue:

```bash
git clone https://github.com/luislopezsanchez/squid-manager.git
cd squid-manager
cp .env.example .env
# Editar .env con tus configuraciones
docker compose up -d
```

### Acceso:
- **Panel web:** http://localhost:3000
- **API docs:** http://localhost:8000/docs
- **Proxy:** localhost:3128

### Credenciales por defecto:
- **Admin panel:** admin / admin123
- **Usuario proxy de prueba:** testuser / test123

## 🛠️ Stack tecnológico

| Componente | Tecnología |
|-----------|------------|
| Backend API | Python + FastAPI |
| Frontend | React + Vite + TailwindCSS |
| Base de datos | PostgreSQL 16 |
| Proxy | Squid 6.12 (compilado con OpenSSL + ssl-crtd) |
| Contenedores | Docker + Docker Compose |

## 📁 Estructura del proyecto

```
squid-manager/
├── docker-compose.yml
├── .env.example
├── backend/                     # FastAPI + Python
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py              # Entry point
│   │   ├── config.py            # Configuración
│   │   ├── database.py          # Conexión BD
│   │   ├── models/              # Modelos SQLAlchemy
│   │   ├── schemas/             # Schemas Pydantic
│   │   ├── routes/              # Endpoints API
│   │   ├── services/            # Lógica de negocio
│   │   └── templates/           # Template Jinja2 (squid.conf)
│   └── tests/
├── frontend/                    # React + Vite
│   ├── Dockerfile
│   ├── package.json
│   ├── src/
│   │   ├── pages/               # Páginas del panel
│   │   ├── components/          # Componentes reutilizables
│   │   └── api/                 # Cliente API
│   └── public/
├── squid/                       # Contenedor Squid
│   ├── Dockerfile               # Compila Squid con OpenSSL
│   └── entrypoint.sh            # Inicialización + CA + SSL Bump
└── docs/
    └── project-log.md           # Bitácora del proyecto
```

## 📝 Licencia

Apache-2.0 — Libre uso y modificación.