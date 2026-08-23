# API Reference — SquidManager

La API tiene 14 routers y 72 endpoints. La documentación interactiva (Swagger/OpenAPI) solo se sirve con `DEBUG=true` en `http://localhost:8000/docs`, accesible desde dentro de la red Docker; con `DEBUG=false` (el valor por defecto) esa ruta devuelve 404.

---

## Autenticación

Todas las rutas (excepto `/api/auth/login`) requieren un token JWT en el header:

```
Authorization: Bearer <token>
```

### Login

```http
POST /api/auth/login
Content-Type: application/x-www-form-urlencoded

username=admin&password=tu_contraseña
```

**Respuesta:**
```json
{
  "access_token": "eyJhbG...",
  "token_type": "bearer",
  "must_change_password": false,
  "role": "superadmin"
}
```

`must_change_password` en `true` indica que el panel debe forzar el cambio de contraseña antes de dejar continuar (ocurre en el primer acceso de cualquier cuenta nueva). El login está limitado a 10 intentos por minuto por IP y 5 por minuto por cuenta; al superarlo responde `429`.

### Info del admin actual

```http
GET /api/auth/me
Authorization: Bearer <token>
```

---

## Usuarios del Proxy

### Listar usuarios
```http
GET /api/proxy-users/
Authorization: Bearer <token>
```

**Respuesta:**
```json
[
  {
    "id": 1,
    "username": "jperez",
    "enabled": true,
    "active": true,
    "expires_at": null,
    "created_at": "2026-08-22T00:08:02",
    "updated_at": "2026-08-22T00:08:02"
  }
]
```

`active` distingue "habilitado" de "puede navegar ahora mismo": un usuario habilitado pero con `expires_at` en el pasado tiene `enabled: true` y `active: false`.

### Crear usuario
```http
POST /api/proxy-users/
Authorization: Bearer <token>
Content-Type: application/json

{
  "username": "nuevo_usuario",
  "password": "contraseña_de_8_caracteres_o_mas",
  "enabled": true,
  "expires_at": null
}
```

### Actualizar usuario
```http
PUT /api/proxy-users/{id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "password": "nueva_contraseña",
  "enabled": false
}
```

Deshabilitar un usuario, cambiarle la contraseña, o hacer que su `expires_at` quede en el pasado, purga automáticamente la caché de credenciales de Squid (afecta a todos los usuarios: es una limitación de Squid, no de la API).

### Eliminar usuario
```http
DELETE /api/proxy-users/{id}
Authorization: Bearer <token>
```

### Activar/Desactivar usuario
```http
PATCH /api/proxy-users/{id}/toggle
Authorization: Bearer <token>
```

### Resetear contraseña
```http
POST /api/proxy-users/{id}/reset-password
Authorization: Bearer <token>
```

Genera una contraseña aleatoria de 16 caracteres, la aplica y purga la caché de credenciales. La respuesta incluye la nueva contraseña en claro — es la única vez que se muestra.

```json
{
  "status": "ok",
  "message": "Contraseña de 'jperez' reseteada. El usuario deberá re-autenticarse.",
  "new_password": "aB3kL9mP2xQ7rT4v"
}
```

### Purgar credenciales manualmente
```http
POST /api/proxy-users/purge-credentials
Authorization: Bearer <token>
```

Fuerza la re-autenticación de **todos** los usuarios del proxy reiniciando Squid.

### Regenerar el fichero de contraseñas
```http
POST /api/proxy-users/sync
Authorization: Bearer <token>
```

Vuelve a escribir `squid_passwd` aplicando las caducidades vencidas desde la última escritura, sin esperar a que otro cambio lo dispare.

---

## Grupos de usuarios

Los grupos mapean a una ACL `proxy_auth` en `squid.conf` y sirven para aplicar políticas a varios usuarios (locales o LDAP) a la vez.

### Listar grupos
```http
GET /api/groups/
Authorization: Bearer <token>
```

**Respuesta:**
```json
[
  {"id": 1, "name": "Comerciales", "description": "Equipo comercial", "members": ["jperez", "mgarcia"]}
]
```

### Crear grupo
```http
POST /api/groups/
Authorization: Bearer <token>
Content-Type: application/json

{"name": "Comerciales", "description": "Equipo comercial"}
```

### Actualizar grupo
```http
PUT /api/groups/{id}
Authorization: Bearer <token>
Content-Type: application/json

{"name": "Comerciales-2027"}
```

Se rechaza con `409` si el nombre actual está referenciado por alguna regla de acceso o delay pool — el mensaje indica cuál.

### Eliminar grupo
```http
DELETE /api/groups/{id}
Authorization: Bearer <token>
```

Mismo bloqueo que renombrar: `409` si sigue en uso.

### Añadir miembro
```http
POST /api/groups/{id}/members
Authorization: Bearer <token>
Content-Type: application/json

{"username": "jperez"}
```

Aplica la configuración a Squid de inmediato (equivalente a pulsar "Aplicar cambios", pero solo con `reconfigure`, sin cortar conexiones).

### Quitar miembro
```http
DELETE /api/groups/{id}/members/{username}
Authorization: Bearer <token>
```

Aplica la configuración y purga la caché de credenciales, ya que quitar a alguien de un grupo puede revocarle acceso que ya tenía autenticado.

---

## ACLs

### Listar ACLs
```http
GET /api/acls/
Authorization: Bearer <token>
```

### ACLs sin usar
```http
GET /api/acls/unused
Authorization: Bearer <token>
```

Devuelve los nombres de las ACLs que no están referenciadas por ninguna regla ni delay pool — existen pero no bloquean ni permiten nada por sí solas.

### Crear ACL
```http
POST /api/acls/
Authorization: Bearer <token>
Content-Type: application/json

{
  "name": "redes_sociales",
  "type": "dstdomain",
  "value": ".facebook.com .twitter.com",
  "description": "Bloquear redes sociales",
  "enabled": true
}
```

**Tipos soportados (27):** `src`, `dst`, `srcdomain`, `dstdomain`, `srcdom_regex`, `dstdom_regex`, `url_regex`, `urlpath_regex`, `port`, `myport`, `localport`, `proto`, `method`, `browser`, `referer_regex`, `time`, `proxy_auth`, `proxy_auth_regex`, `maxconn`, `max_user_ip`, `ident`, `arp`, `req_mime_type`, `rep_mime_type`, `http_status`, `snmp_community`, `ssl::server_name`, `ssl::server_name_regex`, `at_step`. Ver [docs/configuration.md](configuration.md) para la lista completa con ejemplos.

El nombre debe empezar por una letra, usar solo letras/números/guion/guion bajo, y no coincidir con los nombres que usa internamente la plantilla (`all`, `localnet`, `authenticated`, etc.). El valor no puede contener saltos de línea.

### Actualizar ACL
```http
PUT /api/acls/{id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "value": ".facebook.com .twitter.com .instagram.com",
  "enabled": true
}
```

Renombrar se rechaza con `409` si alguna regla usa el nombre actual.

### Eliminar ACL
```http
DELETE /api/acls/{id}
Authorization: Bearer <token>
```

Se rechaza con `409` si alguna regla de acceso la está usando, indicando cuál.

---

## Reglas de Acceso

### Listar reglas
```http
GET /api/access-rules/
Authorization: Bearer <token>
```

### Crear regla
```http
POST /api/access-rules/
Authorization: Bearer <token>
Content-Type: application/json

{
  "action": "deny",
  "acl_names": "redes_sociales",
  "order": 0,
  "description": "Bloquear redes sociales",
  "enabled": true
}
```

`acl_names` se valida contra las ACLs y grupos que existen de verdad; una regla que cite un nombre inexistente se rechaza con `400` antes de guardarse.

### Reordenar reglas
```http
PUT /api/access-rules/reorder
Authorization: Bearer <token>
Content-Type: application/json

{
  "rule_ids": [3, 1, 2, 5, 4]
}
```

### Actualizar regla
```http
PUT /api/access-rules/{id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "action": "allow",
  "acl_names": "localnet authenticated"
}
```

### Eliminar regla
```http
DELETE /api/access-rules/{id}
Authorization: Bearer <token>
```

---

## Delay Pools

### Listar delay pools
```http
GET /api/delay-pools/
Authorization: Bearer <token>
```

### Crear delay pool
```http
POST /api/delay-pools/
Authorization: Bearer <token>
Content-Type: application/json

{
  "pool_class": 2,
  "parameters": "64000/64000 64000/32000",
  "acl_name": "",
  "description": "64KB/s global, 32KB/s por usuario",
  "enabled": true
}
```

### Actualizar delay pool
```http
PUT /api/delay-pools/{id}
Authorization: Bearer <token>
Content-Type: application/json

{
  "parameters": "128000/128000 128000/64000",
  "enabled": true
}
```

### Eliminar delay pool
```http
DELETE /api/delay-pools/{id}
Authorization: Bearer <token>
```

---

## Configuración de Squid

### Ver configuración
```http
GET /api/squid/settings
Authorization: Bearer <token>
```

### Actualizar un parámetro
```http
PUT /api/squid/settings
Authorization: Bearer <token>
Content-Type: application/json

{
  "key": "http_port",
  "value": "3129",
  "category": "network",
  "description": "Puerto de escucha del proxy"
}
```

### Aplicar cambios a Squid
```http
POST /api/squid/apply
Authorization: Bearer <token>
```

Genera la configuración, la **valida ejecutando `squid -k parse` dentro del contenedor de Squid** y solo si es válida la escribe y recarga. Si no es válida, no se toca nada y se devuelve el error exacto.

**Respuesta (éxito):**
```json
{
  "status": "ok",
  "message": "Squid reconfigurado: Squid reconfigurado correctamente",
  "needs_restart": false,
  "warnings": "",
  "config_preview": "# SquidManager ..."
}
```

**Respuesta (configuración inválida):**
```json
{
  "status": "error",
  "message": "Configuración inválida, no se ha aplicado nada:\nERROR: ACL not found: grupo_borrado"
}
```

### Estado de Squid
```http
GET /api/squid/status
Authorization: Bearer <token>
```

**Respuesta:**
```json
{
  "running": true,
  "state": "running",
  "pid": 1,
  "errors": []
}
```

### ¿Hay cambios sin aplicar?
```http
GET /api/squid/pending
Authorization: Bearer <token>
```

```json
{"dirty": true}
```

### Previsualizar squid.conf
```http
GET /api/squid/preview
Authorization: Bearer <token>
```

### Descargar certificado CA
```http
GET /api/squid/ca-cert
Authorization: Bearer <token>
```

Devuelve el certificado en formato `application/x-x509-ca-cert` (descargable).

### Instaladores del certificado

```http
GET /api/squid/ca-deploy/install-cert.bat
GET /api/squid/ca-deploy/deploy-gpo.ps1
GET /api/squid/ca-deploy/cert.mobileconfig
Authorization: Bearer <token>
```

Instalador para Windows (doble clic), script de despliegue por GPO, y perfil de configuración para iOS/macOS, todos con el certificado CA embebido.

---

## LDAP

### Ver configuración LDAP
```http
GET /api/ldap/config
Authorization: Bearer <token>
```

### Guardar configuración LDAP
```http
PUT /api/ldap/config
Authorization: Bearer <token>
Content-Type: application/json

{
  "server_url": "ldap://192.168.1.100:389",
  "bind_dn": "cn=admin,dc=empresa,dc=com",
  "bind_password": "mi_password",
  "search_base": "ou=users,dc=empresa,dc=com",
  "user_filter": "(uid=%s)",
  "enabled": false
}
```

### Test de conexión LDAP
```http
POST /api/ldap/test
Authorization: Bearer <token>
Content-Type: application/json

{
  "server_url": "ldap://192.168.1.100:389",
  "bind_dn": "cn=admin,dc=empresa,dc=com",
  "bind_password": "mi_password",
  "search_base": "ou=users,dc=empresa,dc=com",
  "username": "usuario.test",
  "password": "password_usuario"
}
```

**Respuesta:**
```json
{
  "results": [
    {"step": "Conexión LDAP", "status": "ok", "detail": "Bind exitoso"},
    {"step": "Búsqueda de usuario", "status": "ok", "detail": "Usuario encontrado"},
    {"step": "Autenticación", "status": "ok", "detail": "Usuario autenticado"}
  ],
  "success": true
}
```

### Sincronizar usuarios LDAP
```http
POST /api/ldap/sync
Authorization: Bearer <token>
```

Importa usuarios del directorio (búsqueda paginada, 500 por página) filtrando por `(&(objectCategory=person)(objectClass=user))`. Los nuevos se crean **deshabilitados** (allow-list estricto).

```json
{"status": "ok", "synced": 143}
```

### Listar usuarios LDAP sincronizados
```http
GET /api/ldap/users
Authorization: Bearer <token>
```

### Habilitar/deshabilitar un usuario LDAP
```http
PATCH /api/ldap/users/{id}/toggle
Authorization: Bearer <token>
```

Deshabilitar purga la caché de credenciales de Squid (afecta a todos los usuarios).

---

## Backup, Restore y Migración

### Exportar configuración a JSON
```http
GET /api/backup/export
Authorization: Bearer <token>
```

Descarga un `.json` con settings, ACLs, reglas, usuarios del proxy (sin contraseñas), delay pools, grupos y sus miembros, usuarios LDAP y la configuración LDAP (sin la contraseña de bind). Requiere rol de escritura (no lo pueden usar cuentas de solo lectura).

### Restaurar desde un backup
```http
POST /api/backup/restore
Authorization: Bearer <token>
Content-Type: multipart/form-data

file: squidmanager-backup-20260822-100000.json
```

Los usuarios del proxy se restauran deshabilitados y sin contraseña; hay que resetearles la contraseña tras restaurar. Grupos y usuarios LDAP se restauran antes que las reglas, para que ninguna quede apuntando a un nombre inexistente. Límite de subida: 8 MB.

### Descargar el squid.conf generado
```http
GET /api/backup/squid-conf
Authorization: Bearer <token>
```

### Importar un squid.conf tradicional
```http
POST /api/backup/import-squid-conf
Authorization: Bearer <token>
Content-Type: multipart/form-data

file: squid.conf
```

Parsea ACLs (acumulando las declaradas en varias líneas), reglas, delay pools y los parámetros básicos, incluidos los de `auth_param basic realm/children/credentialsttl`. Los usuarios (htpasswd) no se importan.

---

## Registros (logs)

### Consultar el access.log
```http
GET /api/logs/access?limit=100&offset=0&user=jperez&status=403&domain=facebook&denied=true
Authorization: Bearer <token>
```

Lee el fichero **desde el final**, sin cargarlo entero en memoria; con un tope de líneas examinadas por consulta.

| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| `limit` | 100 | Máximo de entradas a devolver (1-1000) |
| `offset` | 0 | Offset para paginación |
| `user` | (todos) | Filtrar por usuario |
| `status` | (todos) | Filtrar por código de estado HTTP |
| `domain` | (todos) | Filtrar por dominio (coincidencia parcial) |
| `ip` | (todos) | Filtrar por IP de origen |
| `denied` | false | Solo entradas denegadas (401/403/407 o acción `DENIED`) |

### Estadísticas para los filtros
```http
GET /api/logs/stats
Authorization: Bearer <token>
```

Lista de usuarios, dominios y códigos de estado vistos recientemente, para poblar los desplegables del visor.

### Alertas de fuerza bruta
```http
GET /api/logs/security-alerts?minutes=10&threshold=5
Authorization: Bearer <token>
```

IPs con `threshold` o más respuestas `407` (credenciales inválidas o ausentes) en los últimos `minutes` minutos.

```json
{
  "window_minutes": 10,
  "threshold": 5,
  "alerts": [{"ip": "203.0.113.7", "failed_attempts": 12}],
  "total_suspicious_ips": 1
}
```

### Exportar logs a CSV
```http
GET /api/logs/export?denied=true
Authorization: Bearer <token>
```

Mismos filtros que `/api/logs/access`, hasta 50.000 entradas.

---

## Métricas

### Dashboard completo
```http
GET /api/metrics/dashboard
Authorization: Bearer <token>
```

Todo lo que necesita la pantalla de inicio en una sola llamada: tráfico, top usuarios, top dominios, top bloqueados, estado del sistema, línea temporal y conexiones recientes.

### Tráfico en tiempo real
```http
GET /api/metrics/traffic
Authorization: Bearer <token>
```

Bytes/s de subida y bajada leídos directamente de `/proc/net/dev` dentro del contenedor de Squid (no del access.log, que llega con retraso).

### Top usuarios por tráfico
```http
GET /api/metrics/top-users?limit=10
Authorization: Bearer <token>
```

### Top dominios
```http
GET /api/metrics/top-domains?limit=10&denied=false
Authorization: Bearer <token>
```

### Métricas del sistema
```http
GET /api/metrics/system
Authorization: Bearer <token>
```

CPU, RAM y disco del contenedor de Squid.

### Línea temporal de tráfico
```http
GET /api/metrics/timeline
Authorization: Bearer <token>
```

Buffer de los últimos 5 minutos de tráfico, en puntos de 5 segundos.

### Conexiones recientes
```http
GET /api/metrics/connections?limit=20
Authorization: Bearer <token>
```

---

## Notificaciones

### Ver configuración
```http
GET /api/notifications/config
Authorization: Bearer <token>
```

Los secretos (contraseña SMTP, token de Telegram) se devuelven como `smtp_password_set: true/false`, nunca en claro.

### Guardar configuración
```http
PUT /api/notifications/config
Authorization: Bearer <token>
Content-Type: application/json

{
  "email_enabled": true,
  "smtp_host": "smtp.miempresa.com",
  "smtp_port": 587,
  "smtp_user": "alertas@miempresa.com",
  "smtp_password": "...",
  "smtp_encryption": "starttls",
  "email_recipients": "admin@miempresa.com",
  "telegram_enabled": false,
  "notify_on_apply": true,
  "notify_on_security_alert": true
}
```

### Probar email
```http
POST /api/notifications/test-email
Authorization: Bearer <token>
Content-Type: application/json

{"smtp_host": "smtp.miempresa.com", "smtp_port": 587, "email_recipients": "admin@miempresa.com"}
```

### Probar Telegram
```http
POST /api/notifications/test-telegram
Authorization: Bearer <token>
Content-Type: application/json

{"telegram_bot_token": "...", "telegram_chat_id": "..."}
```

---

## Administradores

Solo accesible para cuentas con rol `superadmin`, salvo el cambio de la propia contraseña.

### Listar administradores
```http
GET /api/admins/
Authorization: Bearer <token>
```

### Crear administrador
```http
POST /api/admins/
Authorization: Bearer <token>
Content-Type: application/json

{
  "username": "nuevo_admin",
  "password": "contraseña_de_10_caracteres_o_mas",
  "email": "admin2@miempresa.com",
  "role": "admin"
}
```

`role` es `superadmin`, `admin` o `viewer`. La cuenta se crea con el cambio de contraseña marcado como obligatorio.

### Cambiar la propia contraseña
```http
PUT /api/admins/change-password
Authorization: Bearer <token>
Content-Type: application/json

{"current_password": "actual", "new_password": "nueva_de_10_caracteres_o_mas"}
```

Invalida los tokens emitidos antes del cambio.

### Actualizar un administrador
```http
PUT /api/admins/{id}
Authorization: Bearer <token>
Content-Type: application/json

{"role": "viewer", "is_active": true}
```

El superadmin principal (`id=1`) no puede degradarse ni desactivarse. Nadie puede quitarse a sí mismo el rol de superadmin.

### Eliminar administrador
```http
DELETE /api/admins/{id}
Authorization: Bearer <token>
```

No se puede eliminar el superadmin principal ni la propia cuenta.

---

## Auditoría

### Listar log de auditoría
```http
GET /api/audit/?limit=100&offset=0&entity=proxy_user&action=create
Authorization: Bearer <token>
```

**Parámetros de query:**
| Parámetro | Default | Descripción |
|-----------|---------|-------------|
| `limit` | 100 | Número máximo de registros (1-500) |
| `offset` | 0 | Offset para paginación |
| `entity` | (todos) | Filtrar por entidad (proxy_user, acl, access_rule, admin, user_group, etc.) |
| `action` | (todos) | Filtrar por acción (create, update, delete, toggle, login, login_failed, reorder, restore, import, add_member, remove_member, reset_password, change_password) |

Además de los cambios de configuración, se registran los inicios de sesión (con éxito y fallidos) y la gestión de administradores, que antes no dejaba rastro.

### Estadísticas de auditoría
```http
GET /api/audit/stats
Authorization: Bearer <token>
```

**Respuesta:**
```json
{
  "total": 86,
  "by_entity": {
    "access_rule": 41,
    "acl": 25,
    "proxy_user": 12,
    "delay_pool": 8
  },
  "by_action": {
    "create": 30,
    "update": 15,
    "delete": 20,
    "toggle": 5
  }
}
```
