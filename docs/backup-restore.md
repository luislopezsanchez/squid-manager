# Backup, Restore y Migración — SquidManager

## Tipos de exportación

SquidManager ofrece tres opciones de exportación/importación:

| Opción | Formato | Para qué sirve |
|--------|---------|---------------|
| **Backup de plataforma** | JSON | Restaurar dentro de SquidManager |
| **Descargar squid.conf** | Texto plano | Migrar a Squid tradicional o auditoría |
| **Importar squid.conf** | Texto plano → BD | Migrar desde un Squid tradicional a SquidManager |

---

## Backup de plataforma (JSON)

### Qué incluye
- Configuración de Squid (12 parámetros: puerto, caché, logging, etc.)
- ACLs (todas, con tipo, valor y descripción)
- Reglas de acceso (con orden preservado)
- Usuarios del proxy (sin contraseñas — se resetean al restaurar)
- Delay pools (con clase y parámetros)
- Configuración LDAP (sin contraseña de bind)

### Cómo usarlo
1. Panel → **💾 Backup/Migrar** → **📥 Descargar Backup (JSON)**
2. Se descarga un archivo `squidmanager-backup-YYYYMMDD-HHMMSS.json`
3. Para restaurar: **🔄 Restaurar Backup** → seleccionar el archivo JSON

### Notas importantes
- Los usuarios se importan **sin contraseña**. Al restaurar, se les asigna `changeme123` temporal. Debes cambiar las contraseñas manualmente después.
- La contraseña de bind LDAP **no se exporta** por seguridad. Debes reconfigurarla después de restaurar.
- El backup es **cumulative** (añade/actualiza), no destructivo. Las ACLs existentes con el mismo nombre se actualizan.

---

## Descargar squid.conf

### Qué es
El archivo `squid.conf` que SquidManager genera dinámicamente desde la base de datos y que Squid está usando actualmente.

### Uso en un Squid tradicional (sin plataforma)

El archivo es un `squid.conf` estándar válido, pero para usarlo en un Squid sin SquidManager debes ajustar:

| Elemento | Qué ajustar |
|----------|-------------|
| **Rutas** | `/var/spool/squid`, `/var/log/squid` pueden variar según distribución |
| **Helpers de auth** | `basic_ncsa_auth`, `basic_ldap_auth` deben existir en el servidor destino |
| **squid_passwd** | El archivo de usuarios debe copiarse aparte a `/etc/squid/squid_passwd` |
| **Certificados SSL** | Si usas SSL Bump, copia la CA (`squid-ca.crt`, `squid-ca.key`) e inicializa `ssl_crtd` |
| **security_file_certgen** | Debe estar instalado en el servidor destino para SSL Bump |
| **Puerto** | Verifica que el `http_port` no esté en uso |

### Otros usos
- **Auditoría:** Ver exactamente qué configuración tiene Squid
- **Debugging:** Comparar el config generado con uno manual
- **Documentación:** Adjuntar en reportes

---

## Importar squid.conf tradicional

### Qué hace
Si tienes un Squid configurado a mano y quieres migrar a SquidManager, puedes subir tu `squid.conf` y la plataforma importará:

| Elemento | Se importa | Notas |
|----------|------------|-------|
| **ACLs** (`acl nombre tipo valor`) | ✅ | Todas las ACLs simples (dstdomain, src, url_regex, etc.) |
| **Reglas** (`http_access allow/deny`) | ✅ | Preservando el orden original |
| **Delay pools** (`delay_class`, `delay_parameters`) | ✅ | Si siguen el formato estándar |
| **Settings** (`http_port`, `cache_mem`, `visible_hostname`, etc.) | ✅ | 12 parámetros básicos |
| **Usuarios** (htpasswd) | ❌ | No se pueden importar del squid.conf — crear manualmente |
| **Configuraciones complejas** | ⚠️ | Pueden no importarse perfectamente — revisar antes de aplicar |

### Cómo usarlo
1. Panel → **💾 Backup/Migrar** → **📥 Subir squid.conf**
2. Selecciona tu archivo `squid.conf` actual
3. La plataforma parsea e importa las ACLs, reglas y settings
4. **Revisa** las ACLs y reglas importadas antes de pulsar "Aplicar Cambios"
5. Crea los usuarios del proxy manualmente (no se importan)

### Limitaciones honestas
- Las ACLs internas de Squid (`all`, `localhost`, `SSL_ports`, `Safe_ports`, `CONNECT`, `localnet`) se filtran y no se importan
- Las ACLs `sni_*` generadas por SSL Bump de SquidManager se filtran
- Si tienes ACLs con nombres duplicados, se omite la segunda
- Las configuraciones muy anidadas o con lógica condicional pueden no importarse
- **Siempre revisa antes de aplicar** — la importación es un punto de partida, no una garantía

---

## Multi-Admin y Roles

### Roles disponibles

| Rol | Permisos |
|-----|----------|
| 👑 **Super Admin** | Todo + gestionar otros admins + no puede ser eliminado ni degradado |
| 🛡️ **Admin** | Gestiona el proxy (ACLs, reglas, usuarios, settings, aplicar cambios) pero NO puede gestionar otros admins |
| 👁️ **Viewer** | Solo lectura: ver dashboard, ACLs, reglas, logs, pero no modificar nada |

### Reglas de seguridad
- El **superadmin principal** (ID=1, creado por defecto) no puede ser:
  - Eliminado por nadie
  - Degradado a admin o viewer
  - Desactivado
- Un **admin** no puede:
  - Ver la lista de administradores
  - Crear, editar o eliminar otros administradores
  - Eliminar su propia cuenta
- Un **viewer** no puede:
  - Hacer ningún cambio (crear, editar, eliminar)
  - Aplicar cambios a Squid
  - Restaurar backups o importar configs

### Cambio de contraseña
- Cualquier admin (de cualquier rol) puede cambiar su **propia** contraseña
- Debe conocer la contraseña actual para cambiarla
- La nueva contraseña debe tener al menos 6 caracteres
- Panel → **💾 Backup/Migrar** → **🔑 Cambiar contraseña**