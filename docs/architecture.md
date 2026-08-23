# Arquitectura Técnica — SquidManager

## Visión general

SquidManager está compuesto por 4 contenedores Docker que se comunican a través de una red interna:

```
┌──────────────────────────────────────────────────────────────┐
│                     Docker Network (squidnet)                  │
│                                                                │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐     │
│  │  Frontend    │     │  Backend     │     │  Squid      │     │
│  │  (React)     │────▶│  (FastAPI)   │────▶│  (Proxy)    │     │
│  │  Nginx:80    │     │  Uvicorn:8000│     │  Squid:3128 │     │
│  └─────────────┘     └──────┬──────┘     └─────────────┘     │
│                             │                                  │
│                      ┌──────▼──────┐                          │
│                      │ PostgreSQL  │                          │
│                      │  16:5432    │                          │
│                      └─────────────┘                          │
└──────────────────────────────────────────────────────────────┘

Puertos publicados al host:
  3000 → Frontend (panel web)
  3128 → Squid (proxy)

El backend (8000) y PostgreSQL (5432) NO se publican al host: solo se
alcanzan por la red interna de Docker. La API se accede siempre a través
del frontend, que hace de proxy reverso en /api/*.
```

---

## Componentes

### 1. Frontend (React + Vite + TailwindCSS)

- **Imagen:** Node 20 (build) → Nginx Alpine (runtime)
- **Puerto:** 3000 → 80 (Nginx)
- **Función:** Panel web de administración
- **Nginx:** Actúa como proxy reverso, enruta `/api/*` al backend por la red interna; añade cabeceras de seguridad (`X-Frame-Options`, `X-Content-Type-Options`) y un límite de tamaño de subida

**Páginas (16):**
- Login
- Cambio de contraseña (obligatorio en el primer acceso)
- Dashboard
- Usuarios del proxy
- Grupos de usuarios
- ACLs
- Reglas de acceso
- Delay Pools
- LDAP
- Certificado SSL
- Configuración general
- Notificaciones
- Backup y migración
- Registros (visor del access.log)
- Auditoría
- Administradores

### 2. Backend (Python + FastAPI)

- **Imagen:** Python 3.12-slim
- **Puerto:** 8000 (interno, no publicado al host)
- **Función:** API REST + generación y validación de squid.conf
- **ORM:** SQLAlchemy 2.0
- **Esquema:** gestionado con Alembic — las migraciones se aplican automáticamente al arrancar; una base preexistente sin historial de Alembic se marca con la revisión inicial antes de aplicar el resto
- **Auth:** JWT (python-jose) + bcrypt directo (sin passlib, retirado por incompatibilidad con bcrypt ≥ 4.1)

**Routers (14):**
| Router | Prefijo | Función |
|--------|---------|---------|
| auth | /api/auth | Login, info del admin |
| proxy_users | /api/proxy-users | CRUD usuarios del proxy, purga de credenciales, reset de contraseña |
| user_groups | /api/groups | CRUD de grupos y sus miembros |
| acls | /api/acls | CRUD de ACLs, listado de ACLs sin uso |
| access_rules | /api/access-rules | CRUD de reglas + reorder |
| delay_pools | /api/delay-pools | CRUD de delay pools |
| squid_config | /api/squid | Settings, apply (con validación), status, preview, CA y sus instaladores |
| ldap | /api/ldap | Config LDAP, test conexión, sincronización, allow-list de usuarios |
| backup | /api/backup | Exportar/restaurar JSON, descargar/importar squid.conf |
| logs | /api/logs | Consulta del access.log, alertas de fuerza bruta, export CSV |
| metrics | /api/metrics | Dashboard, tráfico en vivo, top usuarios/dominios, conexiones |
| notifications | /api/notifications | Configuración y prueba de email/Telegram |
| admins | /api/admins | CRUD de administradores, cambio de contraseña propia (solo superadmin gestiona otros) |
| audit | /api/audit | Log de auditoría + estadísticas |

72 endpoints en total. Ver [docs/api-reference.md](api-reference.md) para el detalle.

**Servicios:**
- `auth_service.py` — JWT, bcrypt, validación de credenciales, roles (`require_writer`, `require_superadmin`)
- `config_generator.py` — Genera squid.conf desde BD usando Jinja2; calcula las reglas SNI paralelas para HTTPS
- `squid_service.py` — Control del contenedor Squid vía Docker SDK (reconfigure, restart, recreación con rollback) y validación real de la configuración ejecutando `squid -k parse` dentro del contenedor de Squid
- `squid_names.py` — Valida nombres, tipos y valores de ACLs/grupos antes de interpolarlos en la plantilla, para evitar inyección de directivas
- `log_service.py` — Lee el access.log desde el final en bloques, sin cargarlo entero en memoria

### 3. Squid (Squid 6.12 compilado con OpenSSL)

- **Imagen:** Ubuntu 24.04 + Squid compilado desde fuente
- **Puerto:** 3128
- **Función:** Proxy con SSL Bump
- **Compilación:** `--with-openssl --enable-ssl-crtd` (no disponible en Squid de Ubuntu)

**Por qué se compila desde el código fuente:**
El Squid que viene en Ubuntu 24.04 está compilado con GnuTLS, no con OpenSSL. SSL Bump requiere OpenSSL + ssl-crtd. Por eso se compila Squid 6.12 desde el código fuente dentro del Docker.

**Entrypoint:**
1. Genera CA raíz (RSA 4096, válida 10 años) si no existe
2. Inicializa la base de certificados dinámicos en `/var/lib/ssl_crtd/db` (volumen persistente, propiedad del usuario `proxy`) si no existe, y corrige el propietario en cada arranque
3. Copia archivos de config de Squid (mime.conf, icons, errors) que el volumen oculta, incluidos los alias de idioma para páginas de error en español
4. Asegura permisos 600 en los ficheros con secretos (`squid_passwd`, `ldap_helper.conf`)
5. Escribe squid.conf inicial si no existe
6. Inicializa caché si no existe
7. Arranca `cron` para la rotación diaria de logs
8. Arranca Squid en foreground (`squid -N -d1`)

### 4. PostgreSQL 16

- **Imagen:** postgres:16-alpine
- **Puerto:** 5432 (interno, no publicado)
- **Función:** Almacenar toda la configuración

**Tablas (12):**
| Tabla | Descripción |
|-------|-------------|
| admins | Administradores del panel (con `password_changed_at` para revocar sesiones) |
| proxy_users | Usuarios del proxy (con hash htpasswd y fecha de caducidad opcional) |
| acls | Listas de control de acceso |
| access_rules | Reglas http_access (con orden) |
| squid_settings | Configuración key-value de Squid |
| delay_pools | Delay pools (ancho de banda) |
| ldap_config | Configuración LDAP |
| ldap_users | Usuarios LDAP sincronizados (allow-list estricto) |
| user_groups | Grupos de usuarios |
| user_group_members | Miembros de cada grupo (con clave foránea en cascada) |
| notification_config | Configuración de notificaciones por email/Telegram |
| audit_log | Log de cambios |

---

## Flujo de configuración

```
1. Admin modifica algo en el panel web
2. Frontend envía cambio a la API REST
3. Backend valida (Pydantic + validación anti-inyección de nombres/valores)
4. Backend guarda en PostgreSQL
5. Backend registra en audit_log
6. Admin pulsa "Aplicar Cambios"
7. Backend genera squid.conf con Jinja2 desde la BD
8. Backend VALIDA el resultado ejecutando "squid -k parse" dentro del
   contenedor de Squid. Si no es válido, no se escribe nada y se informa
   del error exacto.
9. Backend escribe squid.conf al volumen compartido
10. Backend evalúa si necesita reconfigure o restart:
    - Si no hay cambio de puerto ni ssl-bump → squid -k reconfigure
    - Si hay ssl-bump → docker restart (necesita releer http_port)
    - Si hay cambio de puerto → recrea el contenedor (renombra el
      anterior primero; si la creación falla, lo restaura)
11. Backend regenera squid_passwd (solo usuarios habilitados y sin caducar)
12. Squid aplica la nueva configuración
```

---

## Volúmenes Docker

| Volumen | Montado en | Descripción |
|---------|-----------|-------------|
| pgdata | /var/lib/postgresql/data | Datos de PostgreSQL (persistente) |
| squid-config | /etc/squid | Config de Squid (compartido backend↔squid) |
| squid-spool | /var/spool/squid | Caché de Squid |
| squid-logs | /var/log/squid | Logs de Squid (con rotación diaria) |
| squid-crtd | /var/lib/ssl_crtd | Base de certificados dinámicos SSL, en el subdirectorio `db` |

> **Nota:** El volumen `squid-config` se comparte entre backend y squid. El backend escribe `squid.conf` y `squid_passwd` (con permisos 600), Squid los lee.

---

## Seguridad

### JWT
- Los tokens se firman con `SECRET_KEY` del `.env`. Si arranca en modo no depuración con la clave de ejemplo, el backend genera una temporal y avisa en el log en vez de arrancar con una clave conocida
- Expiran según `TOKEN_EXPIRE` (default: 8 horas)
- Incluyen la marca `iat` (momento de emisión); si es anterior a `password_changed_at` del admin, el token se rechaza — así cambiar la contraseña cierra las sesiones abiertas en otros navegadores
- Se envían en el header `Authorization: Bearer <token>`

### Roles
Tres roles por cuenta de administrador: `superadmin`, `admin` y `viewer` (solo lectura). Las rutas que modifican algo requieren `require_writer` (rechaza `viewer`); la gestión de otros administradores requiere `require_superadmin`.

### Contraseñas
- Admin: hash bcrypt directo, coste configurable (`BCRYPT_COST`, por defecto 12)
- Usuarios proxy: hash htpasswd (apache2-utils) generado con el mismo coste — Squid requiere este formato

### Rate limiting
Por IP y por cuenta (ver [docs/production.md](production.md)). Solo se confía en `X-Forwarded-For` si la petición llega de un host listado en `TRUSTED_PROXY_HOSTS`.

### Docker Socket
El backend tiene montado `/var/run/docker.sock` para controlar el contenedor Squid (reconfigure, restart, status). En producción, considera restringir los permisos del socket.

### CORS
Lista explícita de orígenes en `CORS_ORIGINS`, vacía por defecto — el panel y la API comparten origen a través de nginx, así que no hace falta ningún origen externo permitido.

### Documentación interactiva
`/docs` y `/openapi.json` solo se registran si `DEBUG=true`; con el valor por defecto (`false`) devuelven 404.
