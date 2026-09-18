# Estructura del proyecto

```
squid-manager/
├── docker-compose.yml          # Orquestación de contenedores
├── .env.example                # Template de configuración
├── README.md                   # Resumen y enlaces a toda la documentación
├── LICENSE                     # Freeware (uso permitido, sin modificar/redistribuir/comercializar)
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
│       ├── models/             # Modelos de datos
│       ├── schemas/             # Schemas Pydantic (validación)
│       ├── routes/             # Endpoints REST (20 routers)
│       ├── services/           # Lógica de negocio
│       │   ├── auth_service.py     # JWT + bcrypt, roles
│       │   ├── config_generator.py # Jinja2 → squid.conf
│       │   ├── squid_service.py    # Aplicar/recargar Squid, validación real
│       │   ├── runtime/             # Adaptador Docker/nativo (ver architecture.md)
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
│       ├── pages/              # Páginas del panel
│       ├── components/         # Layout, Icons, AuthShell, Toast
│       └── api/client.ts       # Cliente HTTP
│
├── squid/                      # Contenedor Squid (compilado desde fuente)
│   ├── Dockerfile              # Compila Squid con OpenSSL + ssl-crtd
│   ├── entrypoint.sh           # CA, ssl_crtd, squid.conf inicial, arranque
│   ├── auth_helper.py          # Helper de autenticación local + LDAP
│   └── squid-logrotate         # Rotación diaria de los logs de Squid
│
├── docs/                       # Documentación (ver README.md para el índice completo)
│
└── examples/                   # Ejemplos y configs
    ├── docker-compose.override.yml  # Ejemplo de override para producción (HTTPS, backups)
    └── acl-examples.md              # Ejemplos de ACLs
```
