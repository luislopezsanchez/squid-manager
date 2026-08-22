# Arquitectura Técnica — SquidManager

## Visión general

SquidManager está compuesto por 4 contenedores Docker que se comunican через una red interna:

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
  8000 → Backend (API REST, opcional)
  3128 → Squid (proxy)
```

---

## Componentes

### 1. Frontend (React + Vite + TailwindCSS)

- **Imagen:** Node 20 (build) → Nginx Alpine (runtime)
- **Puerto:** 3000 → 80 (Nginx)
- **Función:** Panel web de administración
- **Nginx:** Actúa como proxy reverso, enruta `/api/*` al backend

**Páginas:**
- Login
- Dashboard
- Usuarios del proxy
- ACLs
- Reglas de acceso
- Delay Pools
- LDAP
- Configuración general
- Certificado SSL
- Auditoría

### 2. Backend (Python + FastAPI)

- **Imagen:** Python 3.12-slim
- **Puerto:** 8000
- **Función:** API REST + generación de squid.conf
- **ORM:** SQLAlchemy 2.0
- **Auth:** JWT (python-jose) + bcrypt (passlib)

**Routers (8):**
| Router | Prefijo | Función |
|--------|---------|---------|
| auth | /api/auth | Login, info del admin |
| proxy_users | /api/proxy-users | CRUD usuarios del proxy |
| acls | /api/acls | CRUD de ACLs |
| access_rules | /api/access-rules | CRUD de reglas + reorder |
| delay_pools | /api/delay-pools | CRUD de delay pools |
| squid_config | /api/squid | Settings, apply, status, preview, CA |
| ldap | /api/ldap | Config LDAP + test conexión |
| audit | /api/audit | Log de auditoría + stats |

**Servicios:**
- `auth_service.py` — JWT, bcrypt, validación de credenciales
- `config_generator.py` — Genera squid.conf desde BD usando Jinja2
- `squid_service.py` — Control del contenedor Squid via Docker SDK (reconfigure, restart, status)

### 3. Squid (Squid 6.12 compilado con OpenSSL)

- **Imagen:** Ubuntu 24.04 + Squid compilado desde fuente
- **Puerto:** 3128
- **Función:** Proxy con SSL Bump
- **Compilación:** `--with-openssl --enable-ssl-crtd` (no disponible en Squid de Ubuntu)

**Por qué se compila desde el código fuente:**
El Squid que viene en Ubuntu 24.04 está compilado con GnuTLS, no con OpenSSL. SSL Bump requiere OpenSSL + ssl-crtd. Por eso se compila Squid 6.12 desde el código fuente dentro del Docker.

**Entrypoint:**
1. Genera CA raíz (RSA 4096, válida 10 años) si no existe
2. Inicializa `ssl_crtd` (certificados dinámicos)
3. Copia archivos de config de Squid (mime.conf, icons, errors) que el volumen oculta
4. Escribe squid.conf inicial si no existe
5. Inicializa caché si no existe
6. Arranca Squid en foreground (`squid -N -d1`)

### 4. PostgreSQL 16

- **Imagen:** postgres:16-alpine
- **Puerto:** 5432 (interno, no publicado)
- **Función:** Almacenar toda la configuración

**Tablas (8):**
| Tabla | Descripción |
|-------|-------------|
| admins | Administradores del panel |
| proxy_users | Usuarios del proxy (con hash htpasswd) |
| acls | Listas de control de acceso |
| access_rules | Reglas http_access (con orden) |
| squid_settings | Configuración key-value de Squid |
| delay_pools | Delay pools (ancho de banda) |
| ldap_config | Configuración LDAP |
| audit_log | Log de cambios |

---

## Flujo de configuración

```
1. Admin modifica algo en el panel web
2. Frontend envía cambio a la API REST
3. Backend valida (Pydantic)
4. Backend guarda en PostgreSQL
5. Backend registra en audit_log
6. Admin pulsa "Aplicar Cambios"
7. Backend genera squid.conf con Jinja2 desde la BD
8. Backend escribe squid.conf al volumen compartido
9. Backend evalúa si necesita reconfigure o restart:
   - Si no hay cambio de puerto ni ssl-bump → squid -k reconfigure
   - Si hay ssl-bump → docker restart (necesita releer http_port)
   - Si hay cambio de puerto → recrear contenedor (docker compose up)
10. Backend regenera squid_passwd (usuarios)
11. Squid aplica la nueva configuración
```

---

## Volúmenes Docker

| Volumen | Montado en | Descripción |
|---------|-----------|-------------|
| pgdata | /var/lib/postgresql/data | Datos de PostgreSQL (persistente) |
| squid-config | /etc/squid | Config de Squid (compartido backend↔squid) |
| squid-spool | /var/spool/squid | Caché de Squid |
| squid-logs | /var/log/squid | Logs de Squid |
| squid-crtd | /var/lib/ssl_crtd | Certificados dinámicos SSL |

> **Nota:** El volumen `squid-config` se comparte entre backend y squid. El backend escribe `squid.conf` y `squid_passwd`, Squid los lee.

---

## Seguridad

### JWT
- Los tokens se firman con `SECRET_KEY` del `.env`
- Expiran según `TOKEN_EXPIRE` (default: 8 horas)
- Se envían en el header `Authorization: Bearer <token>`

### Contraseñas
- Admin: hash bcrypt (passlib)
- Usuarios proxy: hash htpasswd (apache2-utils) — Squid requiere este formato

### Docker Socket
El backend tiene montado `/var/run/docker.sock` para controlar el contenedor Squid (reconfigure, restart, status). En producción, considera restringir los permisos del socket.

### CORS
Actualmente permite todos los orígenes (`*`). En producción, restringir al dominio del frontend.