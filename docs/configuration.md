# Configuración — SquidManager

Todas las configuraciones se manejan mediante el archivo `.env` y el panel web.

---

## Archivo .env

### Variables de entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| `DB_NAME` | `squidmanager` | Nombre de la base de datos PostgreSQL |
| `DB_USER` | `squid` | Usuario de la base de datos |
| `DB_PASS` | `squidpass123` | Contraseña de la base de datos (**cambiar en producción**) |
| `SECRET_KEY` | `change-this...` | Clave secreta para firmar tokens JWT (**cambiar en producción**) |
| `TOKEN_EXPIRE` | `480` | Tiempo de expiración del token en minutos (480 = 8 horas) |
| `SQUID_PORT` | `3128` | Puerto que Squid escucha dentro del contenedor |
| `PROXY_PORT` | `3128` | Puerto publicado al host (normalmente igual a SQUID_PORT) |

### Generar SECRET_KEY segura

```bash
openssl rand -hex 32
```

---

## Configuración desde el panel web

### Configuración general (⚙️ Configuración)

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
| `access_log` | logging | `/var/log/squid/access.log` | Ruta del log de acceso |
| `cache_log` | logging | `/var/log/squid/cache.log` | Ruta del log de caché |
| `cache_store_log` | logging | `/var/log/squid/store.log` | Ruta del log de store |
| `visible_hostname` | general | `squidmanager` | Nombre visible del proxy en páginas de error |

### Cómo cambiar un parámetro

1. Panel → ⚙️ Configuración
2. Modifica el valor en el campo de texto
3. Click en "Guardar"
4. Click en "⚡ Aplicar Cambios" (sidebar)

> **Nota:** Cambiar `http_port` requiere recrear el contenedor. El sistema lo hace automáticamente, pero también debes actualizar `SQUID_PORT` y `PROXY_PORT` en el archivo `.env`.

---

## Configuración de ACLs

### Tipos de ACL soportados (14 tipos)

| Tipo | Descripción | Ejemplo | ¿Funciona con HTTPS? |
|------|-------------|---------|---------------------|
| `dstdomain` | Dominio de destino | `.facebook.com` | ✅ (SNI) |
| `dstdom_regex` | Regex de dominio | `social` | ✅ (SNI) |
| `src` | IP de origen | `192.168.1.0/24` | ✅ |
| `dst` | IP de destino | `10.0.0.0/8` | ✅ |
| `url_regex` | Regex de URL completa | `\.mp4$` | ✅ (con bump) |
| `urlpath_regex` | Regex de path URL | `/admin/` | ✅ (con bump) |
| `port` | Puerto destino | `443 80` | ✅ |
| `proto` | Protocolo | `HTTP FTP` | ✅ |
| `method` | Método HTTP | `GET POST` | ✅ (con bump) |
| `time` | Horario | `M-F 09:00-17:00` | ✅ |
| `proxy_auth` | Usuario autenticado | `REQUIRED` | ✅ |
| `maxconn` | Conexiones máximas por IP | `20` | ✅ |
| `browser` | User-Agent | `Chrome` | ✅ (con bump) |
| `rep_mime_type` | MIME type de respuesta | `video/` | ✅ (con bump) |

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
| `user_filter` | Filtro para buscar usuarios | `(uid=%s)` |
| `enabled` | Activar/desactivar LDAP | `true` / `false` |

### Filtros comunes

| Directorio | Filtro |
|-----------|--------|
| OpenLDAP | `(uid=%s)` |
| Active Directory | `(sAMAccountName=%s)` |
| Apple Open Directory | `(uid=%s)` |

### Test de conexión

El panel incluye un test de conexión que:
1. Hace `ldapsearch` para verificar conectividad
2. Busca el usuario en el directorio
3. Autentica con `ldapwhoami` para verificar la contraseña

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
| step2 (SslBump2) | `stare` | Permite que el servidor envíe su certificado |
| step2 (terminate) | `terminate` | Bloquea si el SNI coincide con una ACL deny |
| step3 (SslBump3) | `bump` | Desencripta el tráfico para aplicar reglas |
| resto | `splice` | Pasa sin tocar |

### ACLs que bloquean HTTPS por SNI

Solo las ACLs tipo `dstdomain` y `dstdom_regex` generan reglas `ssl_bump terminate`. Las demás ACLs se aplican después del bump (tráfico desencriptado).

Para más detalles, ver [docs/ssl-bump.md](ssl-bump.md).