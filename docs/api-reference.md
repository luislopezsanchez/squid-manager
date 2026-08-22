# API Reference — SquidManager

La API REST está documentada con Swagger/OpenAPI en `http://localhost:8000/docs`

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

username=admin&password=admin123
```

**Respuesta:**
```json
{
  "access_token": "eyJhbG...",
  "token_type": "bearer"
}
```

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
    "username": "testuser",
    "enabled": true,
    "expires_at": null,
    "created_at": "2026-08-22T00:08:02",
    "updated_at": "2026-08-22T00:08:02"
  }
]
```

### Crear usuario
```http
POST /api/proxy-users/
Authorization: Bearer <token>
Content-Type: application/json

{
  "username": "nuevo_usuario",
  "password": "mi_contraseña",
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

---

## ACLs

### Listar ACLs
```http
GET /api/acls/
Authorization: Bearer <token>
```

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

**Tipos soportados:** `src`, `dst`, `dstdomain`, `dstdom_regex`, `url_regex`, `urlpath_regex`, `port`, `proto`, `method`, `time`, `proxy_auth`, `maxconn`, `browser`, `rep_mime_type`

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

### Eliminar ACL
```http
DELETE /api/acls/{id}
Authorization: Bearer <token>
```

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

**Respuesta:**
```json
{
  "status": "ok",
  "message": "Squid reconfigurado: Squid reconfigurado correctamente",
  "needs_restart": false,
  "config_preview": "# SquidManager ..."
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
| `entity` | (todos) | Filtrar por entidad (proxy_user, acl, access_rule, etc.) |
| `action` | (todos) | Filtrar por acción (create, update, delete, toggle) |

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