# Arquitectura Técnica — SquidManager

## Visión general

SquidManager tiene **dos modos de despliegue**. Las cuatro piezas son las mismas
—panel, API, Squid y PostgreSQL— y lo que cambia es cómo se ejecutan y, sobre
todo, **cómo gobierna la API al proceso de Squid**. El modo se elige con la
variable `DEPLOY_MODE` y por defecto es `docker`.

| | `docker` (por defecto) | `native` |
|---|---|---|
| Las piezas corren como | Contenedores | Servicios de systemd |
| Squid viene de | Imagen propia, compilado desde fuente | Paquete `squid-openssl` |
| La API lo gobierna | Socket de Docker | `systemctl` y un sudoers de 3 órdenes |
| El puerto del proxy | Lo publica Docker, mapeado | Está en el `squid.conf` |
| Instalar | `install.sh` | `install-nativo.sh` |

El resto del sistema no sabe en cuál de los dos está: ver **Adaptador de
runtime** más abajo.

### Modo Docker

4 contenedores que se comunican a través de una red interna:

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

### Modo nativo

Las mismas piezas, sin capa de contenedores:

```
+--------------------------------------------------------------+
|                    Una sola maquina (systemd)                  |
|                                                                |
|  +-------------+     +-------------+     +-------------+      |
|  |  nginx      |     | squidmanager|     | squid       |      |
|  |  :3000      |---->| uvicorn     |---->| :3128       |      |
|  |  (estaticos)|     | 127.0.0.1:  | (1) | squid-      |      |
|  |             |     |        8000 |     |  openssl    |      |
|  +-------------+     +------+------+     +-------------+      |
|                             |                                  |
|                      +------v------+                          |
|                      | postgresql  |                          |
|                      |  :5432      |                          |
|                      +-------------+                          |
+--------------------------------------------------------------+

(1) No por red: escribiendo /etc/squid/squid.conf y ejecutando
    `squid -k reconfigure` o `systemctl restart squid` mediante sudo.
```

La API escucha solo en 127.0.0.1 y corre con el usuario `squidmgr`, no como
root. Los detalles están en [instalacion-nativa.md](instalacion-nativa.md).

---

## Adaptador de runtime

El panel necesita seis cosas del proceso de Squid, y solo seis:

| Operación | En Docker | En nativo |
|---|---|---|
| Recargar | `exec squid -k reconfigure` | `sudo squid -k reconfigure` |
| Reiniciar | `container.restart()` | `sudo systemctl restart squid` |
| Validar una configuración | `exec squid -k parse -f` | `sudo squid -k parse -f` |
| Saber si está vivo | Estado del contenedor | `systemctl show ActiveState` |
| Leer contadores | `exec` sobre cgroup y `/proc` | los mismos ficheros, en local |
| Aplicar un puerto nuevo | Recrear el contenedor | Reiniciar el servicio |

Viven detrás de una interfaz (`backend/app/services/runtime/`) con dos
implementaciones. El resto del código —generar el `squid.conf`, escribir los
ficheros de usuarios, hablar con la base de datos— es idéntico en los dos modos
y no sabe en cuál está.

Hay una séptima cosa que no es una acción sino una decisión: **en qué puerto
escribir la directiva `http_port`**. En Docker es un puerto interno fijo, porque
quien traduce al puerto elegido en el panel es el mapeo de Docker. En nativo no
hay traducción y Squid escucha directamente donde diga el panel. Esa diferencia
es la razón de que el modo nativo no necesite recrear nada al cambiar de puerto:
se reescribe el fichero y se reinicia el servicio.

### Métricas

Los contadores de red, memoria y CPU se leen de `/proc` y de los ficheros de
cgroup v2, y los dos modos producen **el mismo texto etiquetado**, de forma que
quien lo interpreta es idéntico. Solo cambia de dónde se leen: el cgroup del
contenedor, o el del servicio de systemd.

Una diferencia que conviene conocer: en modo nativo **el tráfico se mide de la
máquina entera**, no de una interfaz virtual dedicada al proxy. En un equipo que
hace de proxy y poco más la diferencia es despreciable; si la máquina hace otras
cosas, su tráfico también cuenta en la tarjeta de tráfico en tiempo real.

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

**Routers (15):**
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
| logs | /api/logs | Consulta del access.log, alertas de fuerza bruta, export CSV/NDJSON/nativo |
| metrics | /api/metrics | Dashboard, tráfico en vivo, top usuarios/dominios, conexiones |
| notifications | /api/notifications | Configuración y prueba de email/Telegram |
| admins | /api/admins | CRUD de administradores, cambio de contraseña propia (solo superadmin gestiona otros) |
| audit | /api/audit | Log de auditoría + estadísticas |
| syslog | /api/syslog | Configuración y prueba del reenvío del access.log a un SIEM externo (UDP/TCP, RFC 3164/5424) |

75 endpoints en total. Ver [docs/api-reference.md](api-reference.md) para el detalle.

**Servicios:**
- `auth_service.py` — JWT, bcrypt, validación de credenciales, roles (`require_writer`, `require_superadmin`)
- `config_generator.py` — Genera squid.conf desde BD usando Jinja2; calcula las reglas SNI paralelas para HTTPS
- `squid_service.py` — Control del contenedor Squid vía Docker SDK (reconfigure, restart, recreación con rollback) y validación real de la configuración ejecutando `squid -k parse` dentro del contenedor de Squid
- `squid_names.py` — Valida nombres, tipos y valores de ACLs/grupos antes de interpolarlos en la plantilla, para evitar inyección de directivas
- `log_service.py` — Lee el access.log desde el final en bloques, sin cargarlo entero en memoria

### 3. Squid (con OpenSSL y ssl-crtd)

- **Puerto:** 3128
- **Función:** Proxy con SSL Bump
- **Requisito innegociable:** compilado con `--with-openssl --enable-ssl-crtd`

**El paquete `squid` de Ubuntu NO sirve.** Está compilado con GnuTLS, y SSL Bump
necesita OpenSSL más el generador de certificados `security_file_certgen`. Sin
eso la interceptación de HTTPS no puede funcionar, y el fallo aparece mucho más
tarde y sin relación aparente con la causa.

De ahí salen los dos orígenes del binario, uno por modo:

- **Docker:** imagen propia, Ubuntu 24.04 con Squid 6.12 compilado desde fuente.
- **Nativo:** paquete **`squid-openssl`** de los repositorios oficiales, que es
  la variante OpenSSL del mismo Squid y trae ya todo lo necesario —incluida la
  versión 6.14, más nueva que la que se compila—. No hay que compilar nada, y
  las actualizaciones de seguridad llegan por `apt`.

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

**Tablas (13):**
| Tabla | Descripción |
|-------|-------------|
| admins | Administradores del panel (con `password_changed_at` para revocar sesiones) |
| proxy_users | Usuarios del proxy (con hash htpasswd y fecha de caducidad opcional) |
| acls | Listas de control de acceso |
| access_rules | Reglas http_access (con orden) |
| squid_settings | Configuración key-value de Squid |
| delay_pools | Delay pools (ancho de banda) |
| ldap_config | Configuración LDAP |
| ldap_users | Usuarios LDAP sincronizados (deny-list: habilitados por defecto) |
| user_groups | Grupos de usuarios |
| user_group_members | Miembros de cada grupo (con clave foránea en cascada) |
| notification_config | Configuración de notificaciones por email/Telegram |
| audit_log | Log de cambios |
| syslog_config | Configuración del reenvío a syslog externo (fila única, apagada por defecto) |

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

## Almacenamiento persistente

| Volumen | Montado en | Descripción |
|---------|-----------|-------------|
| pgdata | /var/lib/postgresql/data | Datos de PostgreSQL (persistente) |
| squid-config | /etc/squid | Config de Squid (compartido backend↔squid) |
| squid-spool | /var/spool/squid | Caché de Squid |
| squid-logs | /var/log/squid | Logs de Squid (con rotación diaria) |
| squid-crtd | /var/lib/ssl_crtd | Base de certificados dinámicos SSL, en el subdirectorio `db` |

> **Nota:** El volumen `squid-config` se comparte entre backend y squid. El backend escribe `squid.conf` y `squid_passwd` (permisos 640, grupo `proxy`), Squid los lee.

**En modo nativo no hay volúmenes:** son directorios normales del sistema, en
las mismas rutas. Lo que sustituye al volumen compartido es el grupo. El usuario
del panel tiene `proxy` como grupo primario, así que los ficheros que escribe
nacen ya legibles para Squid sin necesidad de `chown`, que exigiría privilegios
que el panel no tiene.

| Volumen (Docker) | Equivalente nativo |
|---|---|
| pgdata | `/var/lib/postgresql` (paquete del sistema) |
| squid-config | `/etc/squid`, grupo `proxy`, con setgid |
| squid-spool | `/var/spool/squid` |
| squid-logs | `/var/log/squid` |
| squid-crtd | `/var/lib/ssl_crtd` |

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

### Privilegios sobre Squid

Es la diferencia de seguridad más relevante entre los dos modos.

**En Docker**, el backend tiene montado `/var/run/docker.sock` para controlar el
contenedor (reconfigure, restart, status). Ese socket equivale a root en la
máquina anfitriona: con él se puede lanzar cualquier contenedor con cualquier
montaje. En producción conviene restringir sus permisos.

**En nativo**, el panel corre con el usuario `squidmgr` —no root— y un fichero
de sudoers con tres órdenes literales, sin comodines:

```
squidmgr ALL=(root) NOPASSWD: /usr/sbin/squid -f /etc/squid/squid.conf -k reconfigure
squidmgr ALL=(root) NOPASSWD: /usr/sbin/squid -k parse -f /etc/squid/squid.conf.candidate
squidmgr ALL=(root) NOPASSWD: /usr/bin/systemctl restart squid
```

Que las rutas sean literales no es un detalle de estilo: un comodín en un
fichero de sudoers suele ser una escalada de privilegios esperando a que alguien
la encuentre.

### CORS
Lista explícita de orígenes en `CORS_ORIGINS`, vacía por defecto — el panel y la API comparten origen a través de nginx, así que no hace falta ningún origen externo permitido.

### Documentación interactiva
`/docs` y `/openapi.json` solo se registran si `DEBUG=true`; con el valor por defecto (`false`) devuelven 404.
