# Changelog — SquidManager

Todos los cambios notables de este proyecto se documentan aquí.
El formato está basado en [Keep a Changelog](https://keepachangelog.com/).

---

## [0.5.0] - 2026-08-22

### Añadido
- **Autenticación combinada (local + LDAP)**: Helper personalizado (`squidmanager_auth_helper`)
  que consulta htpasswd local primero y luego LDAP. Resuelve la limitación de Squid de un
  único helper de auth básica.
- **Gestión de sesiones**: Botón "Forzar re-autenticación" (purga la caché de credenciales,
  global) y "Bloquear/Habilitar acceso" (bloqueo temporal por usuario).
- **Sincronización de usuarios LDAP**: Importa usuarios desde AD (`POST /api/ldap/sync`).
- **Allow-list estricto para LDAP**: Los usuarios LDAP no navegan por defecto; el admin los
  habilita individualmente en el panel.
- **Grupos de usuarios**: Crear grupos y asignar usuarios (locales o LDAP). Cada grupo genera
  una ACL `proxy_auth` en Squid para aplicar políticas por grupo.

### Corregido
- **Bug de auth dual**: Squid tenía dos líneas `auth_param basic program` (local + LDAP),
  lo que hacía que solo funcionara una. Resuelto con el helper combinado.
- **Test LDAP**: Reemplazado `ldapsearch`/`ldapwhoami` (no instalados) por la librería `ldap3`.
- **Atributo `dn` inválido** en la búsqueda LDAP.
- **Toast roto** en las páginas Notificaciones, Admins, Logs y Backup.

---

## [0.3.0] - 2026-08-22

### Añadido
- **SSL Bump completo**: Squid 6.12 compilado con OpenSSL + ssl-crtd
- **Bloqueo HTTPS por SNI**: Las ACLs `dstdomain` y `dstdom_regex` ahora bloquean tráfico HTTPS
- **Página de Certificado SSL**: Descarga de CA + instrucciones de instalación por SO
- **Delay Pools con interfaz visual**: Selector de clase, campos separados por nivel, unidades (KB/s, MB/s)
- **Página de LDAP**: Configuración + test de conexión con resultados paso a paso
- **Página de Auditoría**: Log de cambios con filtros y estadísticas
- **Notificaciones toast**: Feedback visual en todas las acciones (crear, editar, eliminar, aplicar)
- **Certificado CA descargable**: Endpoint `/api/squid/ca-cert`
- **Endpoint de estadísticas de auditoría**: `/api/audit/stats`
- **Detección automática de cambio de puerto**: Recrea el contenedor cuando `http_port` cambia
- **Regeneración de usuarios tras reinicio**: `squid_passwd` se regenera después de recrear el contenedor

### Corregido
- **passlib + bcrypt 5.x**: Fijada bcrypt==4.2.1 (incompatible con passlib)
- **Paquetes squid-ldap-auth**: No existen en Ubuntu 24.04, helpers incluidos en paquete squid
- **PID file stale**: Limpieza en entrypoint
- **Docker socket**: Montado en backend para controlar Squid via SDK
- **Formato htpasswd**: Squid basic_ncsa_auth requiere formato htpasswd, no bcrypt
- **Reorder de reglas**: Ruta `/reorder` movida antes de `/{rule_id}` en FastAPI
- **delay_access sin ACL**: Ahora usa `allow all` cuando no hay ACL específica
- **Entrypoint no pisa config del backend**: Solo escribe config temporal si no existe config generado

---

## [0.2.0] - 2026-08-22

### Añadido
- **Página de ACLs**: CRUD completo con 14 tipos soportados
- **Página de Reglas de Acceso**: CRUD con reorder ▲▼
- **Página de Configuración**: 12 parámetros editables por categoría
- **Botón "Aplicar Cambios" global**: En el sidebar con feedback visual
- **Dashboard mejorado**: Accesos directos a todas las páginas
- **13 ACLs de ejemplo**: Preconfiguradas (redes sociales, streaming, juegos, etc.)
- **8 reglas de ejemplo**: Preconfiguradas con orden correcto
- **Componente Toast reutilizable**: `useToast()` hook

### Corregido
- **Login no redirigía**: Fix en `main.tsx` para detectar token existente

---

## [0.1.0] - 2026-08-21

### Añadido
- **Panel web inicial**: React + Vite + TailwindCSS
- **Backend FastAPI**: 8 modelos, 5 routers, 3 servicios
- **Docker Compose**: 4 servicios (db, backend, squid, frontend)
- **Login con JWT**: Autenticación de admin
- **CRUD de usuarios del proxy**: Con autenticación básica (htpasswd)
- **Generador de squid.conf**: Template Jinja2 desde base de datos
- **Control de Squid via Docker SDK**: reconfigure, status
- **PostgreSQL 16**: Base de datos persistente
- **Squid en Docker**: Ubuntu 24.04 + Squid con delay pools
- **Instalación de Docker**: En servidor Ubuntu 24.04