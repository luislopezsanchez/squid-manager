# Configuración — SquidManager

Todas las configuraciones se manejan mediante el archivo `.env` y el panel web.

---

## Archivo .env

### Variables de entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| `DB_NAME` | `squidmanager` | Nombre de la base de datos PostgreSQL |
| `DB_USER` | `squid` | Usuario de la base de datos |
| `DB_PASS` | *(ninguno)* | Contraseña de la base de datos. **Obligatorio** — el `docker-compose.yml` no arranca sin ella |
| `SECRET_KEY` | *(ninguno)* | Clave para firmar los JWT. **Obligatorio**. Si se deja con un valor de ejemplo conocido y `DEBUG=false`, el backend genera una temporal y avisa en el log en vez de usarla |
| `TOKEN_EXPIRE` | `480` | Minutos de validez de la sesión del panel (480 = 8 horas) |
| `ADMIN_INITIAL_PASSWORD` | *(vacío)* | Contraseña de la cuenta `admin` al crearla. Vacío = se genera una aleatoria, visible una sola vez en `docker compose logs backend` |
| `BCRYPT_COST` | `12` | Coste de los hashes bcrypt de los usuarios del proxy. Más alto = más lento de romper y de verificar |
| `CORS_ORIGINS` | *(vacío)* | Orígenes permitidos por CORS, separados por comas. Vacío si accedes al panel por su propia URL |
| `TRUSTED_PROXY_HOSTS` | `frontend` | Hosts cuya cabecera `X-Forwarded-For` se acepta para el límite de intentos de login |
| `DEBUG` | `false` | En `true` expone `/docs` y `/openapi.json` sin autenticación — solo para desarrollo |
| `WEB_PORT` | `3000` | Puerto del panel publicado al host |
| `SQUID_PORT` | `3128` | Puerto que Squid escucha dentro del contenedor |
| `PROXY_PORT` | `3128` | Puerto publicado al host (normalmente igual a `SQUID_PORT`) |

### Generar valores seguros

```bash
openssl rand -hex 32   # SECRET_KEY
openssl rand -hex 16   # DB_PASS
```

---

## Configuración desde el panel web

### Configuración general (Configuración)

Estos parámetros se guardan en la base de datos y se aplican al `squid.conf`:

| Parámetro | Categoría | Default | Descripción |
|-----------|-----------|---------|-------------|
| `http_port` | network | `3128` | Puerto de escucha del proxy |
| `cache_mem` | cache | `128 MB` | Memoria RAM para caché en memoria |
| `cache_dir` | cache | `ufs /var/spool/squid 100 16 256` | Directorio de caché en disco (formato: tipo ruta tamaño L1 L2) |
| `maximum_object_size` | cache | `4 MB` | Tamaño máximo de objeto cacheable |
| `refresh_pattern` | cache | `. 0 20% 4320` | Patrón de refresco de caché |
| `auth_children` | security | `5` | Número de procesos helper de autenticación |
| `auth_realm` | security | `SquidManager Proxy` | Texto que ve el usuario al autenticarse |
| `credentialsttl` | security | `2 hours` | Tiempo de vida de las credenciales cacheadas |
| `ssl_bump_exclude` | security | *(vacío)* | Dominios que no se descifran con SSL Bump (banca, sanidad, apps con certificate pinning) |
| `access_log` | logging | `/var/log/squid/access.log` | Ruta del log de acceso |
| `cache_log` | logging | `/var/log/squid/cache.log` | Ruta del log de caché |
| `cache_store_log` | logging | `none` | Ruta del log de store; `none` lo desactiva (por defecto, ya que genera mucha escritura y no lo consume nadie) |
| `visible_hostname` | general | `squidmanager` | Nombre visible del proxy en páginas de error |
| `error_language` | general | `es` | Idioma de las páginas de error de Squid |

### Cómo cambiar un parámetro

1. Panel → Configuración
2. Modifica el valor en el campo de texto
3. Click en "Guardar"
4. Click en "Aplicar cambios" (sidebar)

> **Nota:** Cambiar `http_port` requiere recrear el contenedor. El sistema lo hace automáticamente al aplicar cambios, pero también debes actualizar `SQUID_PORT` y `PROXY_PORT` en el archivo `.env` para que el mapeo sobreviva a un `docker compose up -d` posterior.

Antes de aplicarse, la configuración generada se **valida** ejecutando `squid -k parse` dentro del contenedor de Squid. Si no es válida, no se escribe nada y el panel muestra el error exacto que reportó Squid.

---

## Configuración de ACLs

### Tipos de ACL soportados (27 tipos)

| Tipo | Descripción | Ejemplo | ¿Funciona con HTTPS? |
|------|-------------|---------|---------------------|
| `dstdomain` | Dominio de destino | `.facebook.com` | ✅ (SNI) |
| `dstdom_regex` | Regex de dominio de destino | `social` | ✅ (SNI) |
| `srcdomain` | Dominio del cliente (DNS inverso) | `.miempresa.com` | ✅ |
| `src` | IP de origen | `192.168.1.0/24` | ✅ |
| `dst` | IP de destino | `10.0.0.0/8` | ✅ |
| `url_regex` | Regex de URL completa | `\.mp4$` | ✅ (con bump) |
| `urlpath_regex` | Regex de path URL | `/admin/` | ✅ (con bump) |
| `port` | Puerto destino | `443 80` | ✅ |
| `myport` | Puerto local de Squid | `3128` | ✅ |
| `localport` | Puerto local de la conexión | `3128` | ✅ |
| `proto` | Protocolo | `HTTP FTP` | ✅ |
| `method` | Método HTTP | `GET POST` | ✅ (con bump) |
| `time` | Horario | `M-F 09:00-17:00` | ✅ |
| `proxy_auth` | Usuario autenticado | `REQUIRED` | ✅ |
| `proxy_auth_regex` | Regex sobre el usuario autenticado | `^admin` | ✅ |
| `maxconn` | Conexiones máximas por IP | `20` | ✅ |
| `max_user_ip` | IPs máximas por usuario autenticado | `3` | ✅ |
| `browser` | User-Agent | `Chrome` | ✅ (con bump) |
| `referer_regex` | Regex sobre la cabecera Referer | `google\.com` | ✅ (con bump) |
| `ident` | Usuario ident (RFC 1413) | `REQUIRED` | ✅ |
| `arp` | Dirección MAC del cliente | `01:23:45:67:89:AB` | ✅ |
| `req_mime_type` | MIME type de la petición | `application/` | ✅ (con bump) |
| `rep_mime_type` | MIME type de respuesta | `video/` | ✅ (con bump) |
| `http_status` | Código de respuesta HTTP | `403 404` | ✅ |
| `snmp_community` | Comunidad SNMP (para cachemgr) | `public` | — |
| `ssl::server_name` | Nombre del servidor por SNI | `.facebook.com` | ✅ (nativo) |
| `ssl::server_name_regex` | Regex sobre el SNI | `social` | ✅ (nativo) |
| `at_step` | Fase de SSL Bump | `SslBump1` | ✅ (uso interno) |

> Las ACLs `ssl::server_name` y `ssl::server_name_regex` las genera SquidManager automáticamente para las de tipo `dstdomain`/`dstdom_regex` (prefijo `sni_`); no suele hacer falta crearlas a mano. `at_step` la usa la plantilla internamente para las fases de SSL Bump.

Los nombres, tipos y valores se validan antes de guardarse: solo se admiten los 27 tipos de esta lista, los nombres no pueden coincidir con los que usa la plantilla internamente (`all`, `localnet`, `authenticated`, etc.) y los valores no pueden contener saltos de línea.

### Días de la semana (para ACL time)
- `S` = Domingo
- `M` = Lunes
- `T` = Martes
- `W` = Miércoles
- `H` = Jueves
- `F` = Viernes
- `A` = Sábado

### Ejemplos de ACLs

Ver [examples/acl-examples.md](../examples/acl-examples.md) para ejemplos completos.

---

## Grupos de usuarios

Los grupos permiten aplicar una política de acceso a varios usuarios (locales o LDAP) a la vez, en lugar de crear una regla por cada uno.

1. Panel → **Grupos** → crear un grupo con un nombre
2. Añade miembros: puede ser un usuario local del proxy o un usuario LDAP ya sincronizado
3. El grupo se comporta como una ACL `proxy_auth` en las reglas de acceso: puedes usar su nombre en el campo "ACLs" de una regla, igual que cualquier otra ACL
4. Los cambios de miembros de un grupo se aplican de inmediato (no hace falta pulsar "Aplicar cambios" aparte)

Borrar un grupo o quitarle el nombre que usa una regla existente se bloquea si hay alguna regla o delay pool que lo referencia — el panel indica cuál.

---

## Configuración de Delay Pools

### Clases de Delay Pool

| Clase | Descripción | Niveles |
|-------|-------------|---------|
| 1 | Límite global | 1: Global |
| 2 | Límite individual | 1: Global, 2: Por usuario |
| 3 | Límite por red | 1: Global, 2: Por red, 3: Por usuario |
| 4 | Límite por grupo | 1: Global, 2: Por grupo |
| 5 | Límite avanzado | 1: Global, 2: Red, 3: Usuario, 4: Tag |

### Valores de velocidad

Los valores se introducen en la unidad seleccionada (bytes/s, KB/s, MB/s) y el sistema los convierte automáticamente al formato de Squid:

- **Restauración:** velocidad a la que se recupera el bucket de tokens
- **Límite:** velocidad máxima permitida

Ejemplo: Clase 2 con 64 KB/s global y 32 KB/s por usuario → Squid recibe `65536/65536 65536/32768`

---

## Configuración de LDAP

### Campos necesarios

| Campo | Descripción | Ejemplo |
|-------|-------------|---------|
| `server_url` | URL del servidor LDAP | `ldap://192.168.1.100:389` |
| `bind_dn` | DN del usuario de bind | `cn=admin,dc=empresa,dc=com` |
| `bind_password` | Contraseña del bind | `••••••••` |
| `search_base` | Base de búsqueda de usuarios | `ou=users,dc=empresa,dc=com` |
| `user_filter` | Filtro para buscar y autenticar a UN usuario al iniciar sesión | `(uid=%s)` |
| `sync_filter` | Filtro para traer TODOS los usuarios al sincronizar | `(objectClass=person)` |
| `enabled` | Activar/desactivar LDAP | `true` / `false` |

`user_filter` y `sync_filter` son dos cosas distintas y ambas configurables — no hay
ningún filtro fijo en el código. Antes `sync_filter` estaba fijo al de Active Directory
(`objectCategory=person`, un atributo exclusivo de AD); contra OpenLDAP o cualquier otro
LDAPv3 no encontraba a nadie, sin ningún error visible. El panel ofrece un selector de
"Tipo de directorio" que rellena ambos filtros con un punto de partida razonable, pero
los campos son texto libre por si el esquema del directorio es distinto.

### Filtros comunes

| Directorio | `user_filter` (login) | `sync_filter` (importar todos) |
|-----------|------------------------|----------------------------------|
| Active Directory | `(sAMAccountName=%s)` | `(&(objectCategory=person)(objectClass=user))` |
| OpenLDAP (posixAccount) | `(uid=%s)` | `(objectClass=posixAccount)` |
| LDAP genérico (inetOrgPerson) | `(uid=%s)` | `(objectClass=inetOrgPerson)` |
| Apple Open Directory | `(uid=%s)` | `(objectClass=inetOrgPerson)` |

### Test de conexión

El panel incluye un test de conexión que usa la librería `ldap3` para:
1. Conectar y hacer bind con la cuenta de servicio
2. Buscar el usuario con el filtro configurado
3. Autenticar como ese usuario con la contraseña indicada

### Sincronización de usuarios

**Panel → LDAP → Sincronizar** importa los usuarios del directorio (solo metadatos: usuario, nombre, correo — nunca contraseñas), usando búsqueda paginada para no perder usuarios en directorios grandes, con el filtro `sync_filter` configurado. Los nuevos se crean **habilitados** (deny-list): navegan de inmediato, y hay que deshabilitar a mano desde **Usuarios** a quien no deba tener acceso. La lista de usuarios (locales y LDAP juntos, con buscador y filtro) vive en esa página, no en LDAP.

---

## Configuración de SSL Bump

### Cómo funciona

1. Squid genera una CA raíz al arrancar (RSA 4096 bits, válida 10 años)
2. Para cada conexión HTTPS, Squid genera un certificado dinámico firmado por la CA
3. Squid intercepta (bump), desencripta, aplica reglas, y vuelve a encriptar
4. El cliente debe confiar en la CA

### Fases del SSL Bump

| Fase | Acción | Qué hace |
|------|--------|----------|
| step1 (SslBump1) | `peek` | Ve el SNI del cliente sin desencriptar |
| step2 (SslBump2) | `terminate` | Bloquea si el SNI coincide con una ACL deny |
| step2 (SslBump2) | `splice` | Deja pasar sin descifrar si el dominio está en la lista de exclusión |
| step2 (SslBump2) | `stare` | Permite que el servidor envíe su certificado |
| step3 (SslBump3) | `bump` | Desencripta el tráfico para aplicar reglas |

### ACLs que bloquean HTTPS por SNI

Solo las ACLs tipo `dstdomain` y `dstdom_regex` generan reglas `ssl_bump terminate`. Las demás ACLs se aplican después del bump (tráfico desencriptado).

Para más detalles, ver [docs/ssl-bump.md](ssl-bump.md).
