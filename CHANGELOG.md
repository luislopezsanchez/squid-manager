# Changelog — SquidManager

Todos los cambios notables de este proyecto se documentan aquí.
El formato está basado en [Keep a Changelog](https://keepachangelog.com/).

---

## [0.6.0] - 2026-08-23

Auditoría de seguridad completa y rediseño visual. 93 ficheros modificados en 6 commits.

### Seguridad
- **Control de roles real**: el rol `viewer` no restringía ninguna operación de escritura — solo dos endpoints de backup lo comprobaban. Ahora todas las rutas que modifican algo requieren rol de escritura, y la gestión de administradores requiere superadmin.
- **Rate limiting robusto**: el límite de intentos de login se esquivaba rotando la cabecera `X-Forwarded-For`. Ahora esa cabecera solo se acepta desde un proxy de confianza, y hay un segundo límite por cuenta independiente de la IP de origen. El middleware devolvía 500 en vez de 429 al superar el límite; corregido.
- **CORS restringido**: de `allow_origins=["*"]` con credenciales a una lista explícita, vacía por defecto.
- **Puerto 8000 ya no se publica**: el frontend habla con el backend por la red interna de Docker. La documentación interactiva solo se expone con `DEBUG=true`.
- **Revocación de sesión al cambiar contraseña**: los tokens JWT emitidos antes de un cambio de contraseña dejan de aceptarse, aunque no hayan expirado.
- **Sin contraseña fija en el código**: el administrador inicial se genera con una contraseña aleatoria, visible una sola vez en el log, y se exige cambiarla en el primer acceso. Las cuentas nuevas creadas por un superadmin también.
- **passlib retirado** (sin mantenimiento desde 2020) en favor de bcrypt directo; el coste de los hashes del proxy sube de 5 a 12 (configurable).
- El instalador deja de recomendar `curl | bash` y de imprimir credenciales en la salida.

### Squid y generación de configuración
- **SSL Bump operativo**: la base de certificados dinámicos vivía en `/tmp`, propiedad de `root`, y el proceso de Squid (usuario `proxy`) no podía escribir su índice — 595 errores y el generador de certificados muerto 41 veces. Ahora vive en el volumen persistente `squid-crtd`, con el propietario correcto.
- **Validación real antes de aplicar**: `squid -k parse` se ejecutaba en el contenedor del backend, donde no existe el binario, así que cualquier configuración se daba por válida. Ahora se valida dentro del contenedor de Squid y solo se escribe si es correcta.
- **Bloqueo HTTPS por SNI corregido**: no se generaba nada cuando una regla combinaba más de una condición.
- **Orden de las reglas respetado**: las reglas de denegación por grupo se refundían al final del fichero generado, independientemente del orden mostrado en el panel.
- Nueva exclusión de dominios del descifrado de SSL Bump (`ssl_bump_exclude`), para banca, sanidad o apps con certificate pinning.
- Validación de nombres, tipos y valores de ACLs/grupos contra inyección de directivas.
- Páginas de error en español, rotación diaria de logs, `store.log` desactivado por defecto.
- El cambio de puerto ya no borra el contenedor antes de crear el nuevo: lo renombra y lo restaura si la creación falla.

### Integridad de datos
- **Migraciones con Alembic** en lugar de `create_all`, que nunca alteraba tablas existentes.
- Borrar o renombrar una ACL o un grupo en uso se bloquea, indicando qué regla lo referencia.
- Clave foránea con borrado en cascada para los miembros de un grupo.
- El backup ahora exporta e importa grupos y usuarios LDAP; antes se perdían al restaurar.
- La caducidad de los usuarios del proxy (`expires_at`) se aplica de verdad al generar el fichero de contraseñas.
- Deshabilitar un usuario purga la caché de credenciales de Squid de inmediato, en vez de esperar hasta dos horas.
- El importador de squid.conf reconoce los parámetros de `auth_param` y ya no descarta ACLs declaradas en varias líneas.
- Auditoría ampliada a la gestión de administradores y al reordenado de reglas.

### Rendimiento
- El access.log se lee desde el final en bloques, con un tope de líneas examinadas, en vez de cargarse entero en memoria en cada consulta del visor y del dashboard.

### Interfaz
- Tema visual nuevo con la identidad del logo: paleta derivada del calamar, tipografía Figtree + JetBrains Mono, 46 iconos de línea propios que sustituyen a los emojis del menú.
- Menú agrupado en Vigilancia, Políticas y Sistema.
- Pantalla de cambio de contraseña, obligatoria en el primer acceso.
- Aviso visible cuando la cuenta conectada es de solo lectura.

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