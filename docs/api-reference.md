# API Reference — SquidManager

La API tiene 19 routers y 101 endpoints.

## Idioma de las respuestas

Los mensajes de error se devuelven en **español, inglés o portugués** según la
cabecera `Accept-Language` de la petición. Sin cabecera, o con un idioma que no
se soporte, responde en español.

```bash
curl -H "Accept-Language: en" ...   # {"detail":"Rule not found"}
curl -H "Accept-Language: pt" ...   # {"detail":"Regra não encontrada"}
```

Se admite la lista completa que manda un navegador
(`en-US,en;q=0.9,es;q=0.8`): se usa la primera coincidencia. Detalles en
[idiomas.md](idiomas.md).

## Las métricas se sirven en dos rutas

`/api/metrics/*` y `/api/panel/*` son **el mismo conjunto de endpoints**. El
panel web usa `/api/panel`, y no es un capricho: los bloqueadores de anuncios y
los filtros de privacidad (uBlock, AdGuard, los escudos de Brave) cortan por
defecto cualquier URL que contenga «metrics» porque la asocian a telemetría. La
petición no llega a salir del navegador, así que en el servidor no queda ni
rastro y el dashboard se queda cargando para siempre sin nada que lo explique.

Si consumes la API desde un script o desde otro sistema, `/api/metrics` te sirve
igual: ahí no hay extensiones de navegador de por medio. Si la consumes **desde
un navegador**, usa `/api/panel`.

**La documentación interactiva (Swagger/OpenAPI) no se alcanza desde fuera del
servidor.** El puerto 8000 no se publica al host, así que
`http://TU_SERVIDOR:8000/docs` no responde; en una máquina con otros servicios
esa dirección puede llevarte incluso a la API de otro contenedor. Y solo se
registra con `DEBUG=true`: con el valor por defecto devuelve 404.

Para consultarla, con `DEBUG=true` y desde el propio servidor, hay que ir a la
IP del contenedor del backend:

```bash
curl http://$(docker inspect squidmgr-backend --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'):8000/openapi.json
```

Ver la interfaz de Swagger en el navegador requiere un túnel SSH hasta esa IP,
que el servidor alcanza pero tu equipo no. Deja `DEBUG=false` al terminar: la
ruta se sirve sin autenticación.

El panel consume la API por `/api/` a través de nginx, y ese camino sí está
publicado en el puerto del panel.

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
GET /api/proxy-users/?limit=1000&offset=0
Authorization: Bearer <token>
```

`limit` (1-5000, por defecto 1000) y `offset` (por defecto 0) son opcionales.

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
GET /api/acls/?limit=1000&offset=0
Authorization: Bearer <token>
```

`limit` (1-5000, por defecto 1000) y `offset` (por defecto 0) son opcionales.

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

**Tipos soportados (29):** `src`, `dst`, `srcdomain`, `dstdomain`, `srcdom_regex`, `dstdom_regex`, `url_regex`, `urlpath_regex`, `port`, `myport`, `localport`, `proto`, `method`, `browser`, `referer_regex`, `time`, `proxy_auth`, `proxy_auth_regex`, `maxconn`, `max_user_ip`, `ident`, `arp`, `req_mime_type`, `rep_mime_type`, `http_status`, `snmp_community`, `ssl::server_name`, `ssl::server_name_regex`, `at_step`. Ver [docs/configuration.md](configuration.md) para la lista completa con ejemplos.

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

### Carga masiva de dominios
```http
POST /api/acls/bulk-domains
Authorization: Bearer <token>
Content-Type: multipart/form-data

file: dominios.txt
acl_name: blocklist_grande
modo: reemplazar
acl_type: dstdomain
description: (opcional)
```

Para blocklists de miles de dominios, uno por línea (líneas vacías o que empiezan con `#` se ignoran). Solo para `dstdomain`/`dstdom_regex` — el resto de tipos de ACL no tiene sentido cargarlos así.

Por debajo del umbral configurado (200 dominios) la ACL queda **inline**, igual que una creada a mano; por encima pasa a **file**: un archivo aparte que Squid lee directo, no una línea de `squid.conf` con miles de entradas. El umbral se reevalúa en cada carga — una lista que creció puede pasar de inline a file, y una que se redujo puede volver.

`modo`:
- `reemplazar` (default): el archivo define la lista completa, pisa lo que hubiera.
- `agregar`: se suma a lo que ya había en la ACL, sin duplicar.

**Respuesta:**
```json
{
  "acl": { "id": 12, "name": "blocklist_grande", "type": "dstdomain", "source": "file", "...": "..." },
  "dominios_importados": 4500,
  "dominios_nuevos": 4500,
  "rechazados": ["linea-invalida-1", "linea-invalida-2"],
  "total_rechazados": 2
}
```

`rechazados` trae como mucho las primeras 20 líneas rechazadas (`total_rechazados` da el conteo real). Límite de la lista combinada: 200.000 dominios — pensado como cortafuegos ante un archivo descomunal por error, no como techo real de uso.

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

### Probar servidores DNS
```http
POST /api/squid/dns/test
Authorization: Bearer <token>
Content-Type: application/json

{
  "servers": "8.8.8.8, 1.1.1.1"
}
```

Comprueba que los servidores DNS respondan de verdad **sin llegar a guardarlos ni aplicarlos** — permite verificar antes, en vez de descubrir que no responden recién cuando ya nadie puede navegar. Una lista vacía es válida: significa que Squid usará la resolución del sistema.

**Respuesta:**
```json
{
  "ok": true,
  "message": "Los 2 servidores responden correctamente."
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
  "sync_filter": "(objectClass=inetOrgPerson)",
  "enabled": false
}
```

`user_filter` busca a un usuario por su nombre al iniciar sesión; `sync_filter` busca a
todos los usuarios al sincronizar. Son campos independientes — antes `sync_filter` no
existía y el filtro de sincronización estaba fijo en el código al de Active Directory.

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

Importa usuarios del directorio (búsqueda paginada, 500 por página) filtrando por `sync_filter` (configurable — por defecto el de Active Directory, pero sirve cualquier filtro LDAPv3). Los nuevos se crean **habilitados** (deny-list): navegan de inmediato, hasta que se deshabilitan a mano desde `PATCH /api/proxy-users/{id}/toggle` o el equivalente LDAP.

```json
{"status": "ok", "synced": 143}
```

### Listar usuarios LDAP sincronizados
```http
GET /api/ldap/users?limit=1000&offset=0
Authorization: Bearer <token>
```

`limit` (1-5000, por defecto 1000) y `offset` (por defecto 0) son opcionales.

### Habilitar/deshabilitar un usuario LDAP
```http
PATCH /api/ldap/users/{id}/toggle
Authorization: Bearer <token>
```

Deshabilitar purga la caché de credenciales de Squid (afecta a todos los usuarios).

---

## Kerberos

Autenticación Negotiate (SPNEGO/Kerberos) contra Active Directory: inicio de sesión único, sin que el navegador pida credenciales. Ver [docs/kerberos.md](kerberos.md) para el procedimiento completo.

### Ver configuración
```http
GET /api/kerberos/config
Authorization: Bearer <token>
```

El keytab nunca se devuelve, solo si hay uno subido (`keytab_uploaded`).

### Guardar realm y FQDN
```http
PUT /api/kerberos/config
Authorization: Bearer <token>
Content-Type: application/json

{
  "enabled": true,
  "realm": "EMPRESA.COM",
  "proxy_fqdn": "proxy.empresa.com"
}
```

El keytab se sube aparte (endpoint de abajo). No se comprueba aquí que el keytab funcione de verdad — eso solo se sabe cuando un cliente real presenta un ticket; al aplicar se valida al menos que el archivo tenga forma de keytab.

### Descargar el script de preparación del AD
```http
GET /api/kerberos/ad-setup-script
Authorization: Bearer <token>
```

Devuelve un `.zip` con un script de PowerShell (para correr en el Active Directory del cliente, no en el servidor de SquidManager) y un lanzador `.cmd` — Windows bloquea por defecto cualquier `.ps1` sin firma digital, el `.cmd` lo evita sin cambiar la política de ejecución del sistema. Requiere haber guardado antes realm y FQDN (`400` si faltan). No incluye ninguna contraseña ni credencial: la cuenta de servicio y el keytab se generan en el propio AD al correr el script.

### Subir el keytab
```http
POST /api/kerberos/keytab
Authorization: Bearer <token>
Content-Type: multipart/form-data

file: squidmanager.keytab
```

Límite 256 KB. SquidManager no genera este archivo ni pide credenciales de dominio — crear la cuenta de equipo en el AD es una operación que hace el propio cliente, fuera del panel.

### Quitar el keytab
```http
DELETE /api/kerberos/keytab
Authorization: Bearer <token>
```

Kerberos deja de ofrecerse al pulsar «Aplicar cambios».

---

## Proxy padre

Salida a Internet a través de otro proxy (encadenado), con credenciales fijas o reenviando las del cliente (`passthru`) hacia un padre que exige Digest, NTLM o Negotiate. Ver [docs/proxy-padre.md](proxy-padre.md).

### Ver configuración
```http
GET /api/parent-proxy/config
Authorization: Bearer <token>
```

La contraseña viaja enmascarada (`***`) si ya hay una guardada — igual que el bind de LDAP.

### Guardar configuración
```http
PUT /api/parent-proxy/config
Authorization: Bearer <token>
Content-Type: application/json

{
  "enabled": true,
  "host": "padre.empresa.com",
  "port": 3128,
  "username": "usuario",
  "password": "contraseña",
  "never_direct": true,
  "direct_domains": "",
  "ca_cert": "",
  "auth_method": "fixed"
}
```

`auth_method`: `fixed` (usuario/contraseña propios, solo Basic) o `passthru` (reenvía las credenciales del cliente tal cual — la única forma de llegar a un padre que exige Digest/NTLM/Negotiate). Enviar `password: "***"` conserva la que ya había guardada. No se comprueba aquí que el padre responda — eso se hace al aplicar. No se puede desactivar con el esquema de autenticación del proxy en `none` (dependencia real: ese esquema depende de que exista un padre habilitado, apagarlo dejaría el Squid abierto).

### Probar sin guardar
```http
POST /api/parent-proxy/test
Authorization: Bearer <token>
Content-Type: application/json

{"host": "padre.empresa.com", "port": 3128, "username": "usuario", "password": "contraseña"}
```

```json
{"ok": true, "message": "Conexión exitosa"}
```

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

### Importar un squid.conf tradicional (analizar → aplicar)

Dos pasos, no uno: un `squid.conf` administrado a mano varía demasiado entre instalaciones (`include` de ACLs en archivos aparte, NTLM/AD, squidGuard, proxy padres con opciones propias...) como para que un import de un solo paso sea seguro. Primero se analiza sin escribir nada, después se aplica explícitamente lo ya revisado.

**1. Analizar:**
```http
POST /api/backup/analyze-squid-conf
Authorization: Bearer <token>
Content-Type: multipart/form-data

files: squid.conf
files: acls-bloqueadas.conf   (opcional, uno o más, hasta 20 archivos)
principal: squid.conf
```

`principal` es el nombre del archivo que hace de punto de entrada; el resto solo se usan si algún `include` los referencia por nombre. No escribe nada en la base — solo devuelve un informe y un `token` de corta duración para confirmar con `/apply-squid-import` sin volver a subir los archivos.

**Respuesta:**
```json
{
  "status": "ok",
  "token": "a1b2c3...",
  "resumen": { "acls_nuevas": 12, "reglas_nuevas": 8, "...": "..." },
  "acls": [{"name": "...", "type": "dstdomain", "value": "...", "estado": "importable", "motivo": null}],
  "reglas": [{"action": "deny", "acl_names": ["..."], "estado": "importable", "motivo": null}],
  "settings": [{"key": "...", "value": "..."}],
  "delay_pools": [{"pool_class": 2, "parameters": "..."}],
  "parent_proxy": {"host": "...", "port": 3128, "username": "...", "estado": "importable", "motivo": null},
  "no_soportadas": [{"directiva": "acl_uses_indirect_client", "archivo": "squid.conf", "linea": 42, "motivo": "..."}],
  "desconocidas": [{"directiva": "...", "archivo": "...", "linea": 0, "motivo": "..."}],
  "includes_faltantes": ["archivo-que-no-se-subio.conf"]
}
```

Cada ACL, regla y el proxy padre traen su propio `estado` (`importable` / `existe` / `no_soportada` / etc.) y `motivo` cuando no es directo. `no_soportadas` son directivas reconocidas pero que SquidManager no puede representar; `desconocidas` son directivas que el parser no reconoce en absoluto. Los usuarios (htpasswd) nunca se importan.

**2. Aplicar el análisis ya revisado:**
```http
POST /api/backup/apply-squid-import
Authorization: Bearer <token>
Content-Type: multipart/form-data

token: a1b2c3...
```

El token vive en memoria unos minutos y se consume al usarlo: no se puede aplicar el mismo análisis dos veces ni reutilizarlo más tarde (expira con `400` y hay que volver a analizar).

```json
{"status": "ok", "message": "Importación aplicada", "details": {"acls": 12, "reglas": 8, "settings": 3, "avisos": ["Revisa la configuración importada y pulsa «Aplicar cambios» para activarla."]}}
```

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

### Exportar logs
```http
GET /api/logs/export?format=csv&denied=true
Authorization: Bearer <token>
```

Mismos filtros que `/api/logs/access`, hasta 50.000 entradas. El parametro `format` elige el contenido del archivo:

| `format` | Contenido | Uso tipico |
|---|---|---|
| `csv` (default) | Tabla, una fila por entrada | Abrir en una planilla |
| `ndjson` | Un objeto JSON por linea | Ingesta generica en un SIEM |
| `raw` | La linea del access.log de Squid sin modificar | AWStats, SARG, modulos Squid de Splunk/ELK |

### Histórico de logs

Meses ya cerrados y consolidados en frío (`archive/historical/AAAA/MM/`), separado a propósito del resto de este router: no forman parte del polling del panel, se consultan solo cuando alguien abre la pestaña de histórico.

```http
GET /api/logs/historical/months
Authorization: Bearer <token>
```

Lista los meses con log consolidado, más nuevo primero, leyendo solo los `index.json` (nunca abre los `.gz` para armar este listado).

```http
GET /api/logs/historical/{year}/{month}
Authorization: Bearer <token>
```

El `index.json` precalculado de un mes concreto (usuarios, dominios, denegados). `404` si ese mes no tiene log consolidado.

```http
GET /api/logs/historical/{year}/{month}/entries?limit=100&offset=0&user=jperez&status=403&domain=facebook&denied=true
Authorization: Bearer <token>
```

Mismos filtros que `/api/logs/access`, pero sobre el `.gz` de ese mes. No cachea nada (un mes cerrado no cambia, y cada consulta ya es bajo demanda).

```http
GET /api/logs/historical/{year}/{month}/export?format=csv&denied=true
Authorization: Bearer <token>
```

Igual que `/api/logs/export` pero para un mes histórico completo, en streaming. Sin `raw`: para el formato nativo de Squid alcanza con el `.gz` consolidado directamente.

---

## Syslog externo

Reenvio continuo del access.log a un SIEM u otra herramienta externa, en formato RFC 3164 o RFC 5424, por UDP o TCP. Apagado por defecto: mientras `enabled` sea `false` no se manda nada. Un hilo de fondo relee esta configuracion cada pocos segundos, asi que activarlo, apagarlo o cambiar el destino no requiere reiniciar el backend.

### Consultar y guardar la configuracion
```http
GET /api/syslog/config
PUT /api/syslog/config
Authorization: Bearer <token>
```

```json
{
  "enabled": true,
  "host": "siem.empresa.com",
  "port": 514,
  "protocol": "udp",
  "rfc_format": "rfc3164",
  "facility": "local0",
  "log_format": "raw"
}
```

`protocol` acepta `udp`/`tcp`, `rfc_format` acepta `rfc3164`/`rfc5424`, `log_format` acepta `raw`/`ndjson` (mismo significado que en la exportacion). Habilitarlo (`enabled: true`) exige tener `host` seteado.

### Probar el destino
```http
POST /api/syslog/test
Authorization: Bearer <token>
```

Manda un mensaje de prueba con los datos del cuerpo de la peticion, sin necesidad de guardar la configuracion antes -- permite probar un destino nuevo sin activar el reenvio real. Por UDP no hay confirmacion de entrega: un "enviado" no garantiza que algo este escuchando del otro lado.

---

## Métricas

> Todos los endpoints de esta sección existen tambien bajo `/api/panel/`,
> que es la ruta que usa el panel web porque los bloqueadores de anuncios
> cortan las URL que contienen «metrics». Ver la nota del principio.

### Dashboard completo
```http
GET /api/metrics/dashboard
Authorization: Bearer <token>
```

Todo lo que necesita la pantalla de inicio en una sola llamada: tráfico, top usuarios,
top dominios, top bloqueados, top usuarios bloqueados, estado del sistema, línea temporal
y conexiones recientes.

Las estadísticas del contenedor (red, CPU, RAM) se leen directamente de los ficheros de
cgroup dentro de un único `docker exec`, no con `container.stats()` del SDK de Docker:
ese método fuerza dos muestreos separados por un segundo para calcular el delta de CPU, y
el dashboard lo llamaba dos veces por carga (tráfico y sistema). El endpoint pasó de
tardar 4-8 segundos a 20-70 ms, con una caché de 2 segundos para no repetir el `exec` si
varias tarjetas piden datos casi al mismo tiempo.

### Tráfico en tiempo real
```http
GET /api/metrics/traffic
Authorization: Bearer <token>
```

Bytes/s de subida y bajada leídos directamente de `/proc/net/dev` dentro del contenedor de Squid (no del access.log, que llega con retraso).

También incluye, calculado sobre los últimos 60 segundos del access.log:
- `cache_hit_ratio` (0-100, o `null` si no hubo ninguna petición cacheable en la ventana —
  no es lo mismo que 0%), `cache_hits`, `cache_misses`, `cache_bytes_saved`.
- `latency_avg_ms`, `latency_p50_ms`, `latency_p95_ms` — excluyen los túneles CONNECT
  (HTTPS), donde ese campo del log mide la duración de la conexión completa, no el tiempo
  de respuesta.

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

### Top usuarios con más peticiones denegadas
```http
GET /api/metrics/top-blocked-users?limit=10
Authorization: Bearer <token>
```

Cuenta peticiones denegadas (407/403) por usuario en las últimas 1.000 líneas del log —
**no** implica que la cuenta esté deshabilitada, solo que tuvo intentos denegados (pueden
ser por credenciales viejas cacheadas en el navegador, una política de grupo, o sí, una
cuenta deshabilitada). Cada fila se cruza contra el estado real de la cuenta:

```json
{
  "users": [
    {"user": "jperez", "blocked_requests": 12, "account_status": "enabled"},
    {"user": "mgomez", "blocked_requests": 3, "account_status": "disabled"}
  ],
  "anonymous_blocked": 340
}
```

`account_status` es `"enabled"`, `"disabled"` o `"unknown"` (la cuenta no existe ni local
ni en LDAP, por ejemplo si se borró después). `anonymous_blocked` cuenta las denegadas sin
usuario asociado — la mayoría es ruido de fondo del navegador (telemetría, sondas de
conectividad) que nunca llega a mandar credenciales.

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

---

## Asistente de IA

Responde preguntas sobre el uso del panel usando **solo la documentación del proyecto** como fuente (README + `docs/*.md` en español, nunca la base de datos ni la configuración real). Apagado por defecto, igual que LDAP/Kerberos/Syslog. Necesita dos API keys separadas: una de un proveedor de chat (para generar la respuesta) y una de Jina AI (para la búsqueda semántica por embeddings — sin ella no puede encontrar los fragmentos relevantes).

### Ver configuración
```http
GET /api/ai/config
Authorization: Bearer <token>
```

Las API keys nunca se devuelven en claro (`"***"` si ya hay una guardada). Incluye `fragmentos_indexados`, para saber si hace falta (re)indexar.

### Guardar configuración
```http
PUT /api/ai/config
Authorization: Bearer <token>
Content-Type: application/json

{
  "enabled": true,
  "provider": "gemini",
  "api_key": "...",
  "embedding_api_key": "...",
  "chat_model": "gemini-2.0-flash",
  "embedding_model": "jina-embeddings-v3"
}
```

`provider`: `gemini`, `ollama_cloud`, `nvidia_nim` o `groq`. Enviar `api_key`/`embedding_api_key` como `"***"` conserva la que ya había guardada. Habilitar (`enabled: true`) exige tener las dos keys — sin la de Jina, `400`.

### Probar una API key de proveedor
```http
POST /api/ai/probar-proveedor
Authorization: Bearer <token>
Content-Type: application/json

{"provider": "gemini", "api_key": "..."}
```

No toca la configuración guardada: solo prueba la key y devuelve los modelos disponibles, para elegir de una lista real en vez de escribir un nombre a mano y enterarse recién al preguntar si existe.

```json
{"status": "ok", "modelos": ["gemini-2.0-flash", "gemini-2.0-pro"]}
```

### Probar la key de Jina AI (embeddings)
```http
POST /api/ai/probar-embeddings
Authorization: Bearer <token>
Content-Type: application/json

{"api_key": "..."}
```

Pide un embedding mínimo sin guardar nada.

```json
{"status": "ok", "dimensiones": 1024}
```

### Reindexar la documentación
```http
POST /api/ai/reindexar
Authorization: Bearer <token>
```

Vuelve a indexar toda la documentación desde cero (README + `docs/*.md`, sin las traducciones `.en.md`/`.pt.md`). Bloqueante — una llamada de red por fragmento a Jina AI — se corre en un threadpool para no congelar el panel mientras dura. Hay que correrlo a mano después de cualquier cambio en la documentación: no hay reindexado automático.

```json
{"status": "ok", "fragmentos": 214, "archivos": 19, "saltados": 0}
```

### Preguntar
```http
POST /api/ai/preguntar
Authorization: Bearer <token>
Content-Type: application/json

{"pregunta": "¿Cómo habilito la carga masiva de dominios?"}
```

Cualquier admin puede preguntar, incluida una cuenta de solo lectura: es una consulta de lectura sobre documentación, no una acción sobre el proxy. `400` si el asistente no está activado.

```json
{
  "respuesta": "Subí un archivo con un dominio por línea desde...",
  "fuentes": [
    {"archivo": "README.md", "seccion": "Gestión de proxy"},
    {"archivo": "docs/api-reference.md", "seccion": "ACLs"}
  ]
}
```

`fuentes` son los fragmentos de documentación que se usaron para armar la respuesta — sirve para verificar de dónde salió, no es una alucinación sin base.

---

## Actualizaciones

Comprueba si hay una versión nueva de SquidManager en GitHub y permite aprobarla —de inmediato o programada— sin salir del panel. Solo instalación nativa. El panel nunca ejecuta la actualización en sí: solo puede aprobarla; quién la aplica de verdad y con qué permisos está explicado en [docs/actualizaciones-automaticas.md](actualizaciones-automaticas.md).

### Ver el estado

```http
GET /api/update/estado
Authorization: Bearer <token>
```

Cualquier admin puede consultarlo, incluida una cuenta de solo lectura.

```json
{
  "es_nativo": true,
  "version_actual": "0.23.0",
  "check_enabled": true,
  "check": {
    "last_checked_at": "2026-09-09T12:00:00Z",
    "local_commit": "abc1234",
    "remote_commit": "def5678",
    "update_available": true,
    "commits": [{"sha": "def5678", "message": "fix: ..."}],
    "last_check_error": null
  },
  "request": {"approved": false, "scheduled_at": null, "requested_by": null, "requested_at": null, "atrasada": false},
  "apply": {"status": null, "started_at": null, "finished_at": null, "commit": null, "log_tail": null}
}
```

`apply.status` es `null`, `"running"`, `"verificando"` (la unidad ya no está activa pero el temporizador todavía no confirmó el resultado), `"ok"` o `"error"`. `request.atrasada` en `true` significa que una aprobación lleva más de 3 minutos sin que el temporizador la haya tomado — señal de que algo no anda bien en el servidor.

### Forzar una comprobación contra GitHub

```http
POST /api/update/comprobar
Authorization: Bearer <token>
```

Solo superadmin. `400` si la instalación no es nativa.

### Activar/desactivar la comprobación automática (cada 6 h)

```http
PUT /api/update/config
Authorization: Bearer <token>
Content-Type: application/json

{"check_enabled": false}
```

Solo superadmin.

### Aprobar una actualización

```http
POST /api/update/aprobar
Authorization: Bearer <token>
Content-Type: application/json

{"scheduled_at": null}
```

Solo superadmin. `scheduled_at` en `null` (o ausente) equivale a "ahora": queda aprobada y además se dispara al instante el chequeo que la aplica, sin esperar al temporizador. Con una fecha/hora futura (ISO 8601), queda programada — se rechaza con `400` si esa fecha ya pasó (con 30 s de margen, para no rechazar la propia opción "ahora" por la latencia normal de la petición). `400` también si ya hay una actualización en curso.

### Cancelar una aprobación pendiente

```http
POST /api/update/cancelar
Authorization: Bearer <token>
```

Solo superadmin. `400` si la actualización ya está en curso (ya no se puede cancelar).
