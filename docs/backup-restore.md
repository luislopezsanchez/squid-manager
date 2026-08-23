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
- Configuración de Squid (todos los parámetros: puerto, caché, logging, etc.)
- ACLs (todas, con tipo, valor y descripción)
- Reglas de acceso (con orden preservado)
- Usuarios del proxy (sin contraseñas — se resetean al restaurar)
- Delay pools (con clase y parámetros)
- **Grupos de usuarios y sus miembros**
- **Usuarios LDAP sincronizados y su estado (habilitado/deshabilitado)**
- Configuración LDAP (sin contraseña de bind)

### Cómo usarlo
1. Panel → **Backup y migración** → **Descargar backup (JSON)**
2. Se descarga un archivo `squidmanager-backup-YYYYMMDD-HHMMSS.json`
3. Para restaurar: **Restaurar backup** → seleccionar el archivo JSON

### Notas importantes
- Los usuarios se restauran **sin contraseña y deshabilitados**: no hay una contraseña temporal genérica. Debes usar "Resetear contraseña" en cada uno antes de que puedan volver a navegar.
- La contraseña de bind LDAP **no se exporta** por seguridad. Debes reconfigurarla después de restaurar.
- Los grupos y los usuarios LDAP se restauran **antes** que las reglas de acceso, precisamente para que una regla que los referencia no se quede apuntando a un nombre inexistente.
- El backup es **acumulativo** (añade/actualiza), no destructivo, salvo en reglas y delay pools, que se reemplazan por completo para preservar el orden.
- Las subidas tienen un límite de tamaño (8 MB), suficiente para cualquier backup de esta plataforma.

---

## Descargar squid.conf

### Qué es
El archivo `squid.conf` que SquidManager genera dinámicamente desde la base de datos y que Squid está usando actualmente.

### Uso en un Squid tradicional (sin plataforma)

El archivo es un `squid.conf` estándar válido, pero para usarlo en un Squid sin SquidManager debes ajustar:

| Elemento | Qué ajustar |
|----------|-------------|
| **Rutas** | `/var/spool/squid`, `/var/log/squid` pueden variar según distribución |
| **Helpers de auth** | El helper combinado (`squidmanager_auth_helper`) es específico de esta plataforma; en un Squid tradicional usa `basic_ncsa_auth` y/o `basic_ldap_auth` |
| **squid_passwd** | El archivo de usuarios debe copiarse aparte a `/etc/squid/squid_passwd`, con permisos `600` |
| **Certificados SSL** | Si usas SSL Bump, copia la CA (`squid-ca.crt`, `squid-ca.key`) e inicializa la base de `ssl_crtd` con el propietario correcto |
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
| **ACLs** (`acl nombre tipo valor`) | ✅ | Incluidas las declaradas en varias líneas: los valores se acumulan en lugar de quedarse solo con la primera |
| **Reglas** (`http_access allow/deny`) | ✅ | Preservando el orden original |
| **Delay pools** (`delay_class`, `delay_parameters`) | ✅ | Si siguen el formato estándar |
| **Settings** (`http_port`, `cache_mem`, `visible_hostname`, `auth_param basic realm/children/credentialsttl`, etc.) | ✅ | Incluye los parámetros de `auth_param`, que antes no se reconocían |
| **Usuarios** (htpasswd) | ❌ | No se pueden importar del squid.conf — crear manualmente |
| **Configuraciones complejas** | ⚠️ | Pueden no importarse perfectamente — revisar antes de aplicar |

### Cómo usarlo
1. Panel → **Backup y migración** → **Subir squid.conf**
2. Selecciona tu archivo `squid.conf` actual
3. La plataforma parsea e importa las ACLs, reglas y settings
4. **Revisa** las ACLs y reglas importadas antes de pulsar "Aplicar cambios"
5. Crea los usuarios del proxy manualmente (no se importan)

### Limitaciones honestas
- Las ACLs internas de Squid (`all`, `localhost`, `SSL_ports`, `Safe_ports`, `CONNECT`, `localnet`, `authenticated`, `manager`) se filtran y no se importan
- Las ACLs `sni_*` generadas por SSL Bump de SquidManager se filtran
- Si tienes ACLs con el mismo nombre y distinto tipo, se avisa y se conserva la primera
- Las configuraciones muy anidadas o con lógica condicional pueden no importarse
- **Siempre revisa antes de aplicar** — la importación es un punto de partida, no una garantía

---

## Multi-Admin y Roles

### Roles disponibles

| Rol | Permisos |
|-----|----------|
| **Superadmin** | Todo + gestionar otros admins + no puede ser eliminado ni degradado |
| **Admin** | Gestiona el proxy (ACLs, reglas, usuarios, settings, aplicar cambios) pero NO puede gestionar otros admins |
| **Viewer** (solo lectura) | Solo lectura: ver dashboard, ACLs, reglas, logs, pero no modificar nada |

### Reglas de seguridad
- El **superadmin principal** (ID=1, creado por defecto) no puede ser:
  - Eliminado por nadie
  - Degradado a admin o viewer
  - Desactivado
- Un **admin** no puede:
  - Ver la lista de administradores
  - Crear, editar o eliminar otros administradores
  - Eliminar su propia cuenta
- Un **viewer** no puede realizar ninguna operación de escritura: la API rechaza con un error 403 cualquier intento de crear, editar, eliminar, aplicar cambios, resetear contraseñas, sincronizar LDAP o restaurar backups. El panel oculta o deshabilita esos controles y muestra un aviso permanente de que la cuenta es de solo lectura.

### Cambio de contraseña
- Cualquier admin (de cualquier rol) puede cambiar su **propia** contraseña
- Debe conocer la contraseña actual para cambiarla
- La nueva contraseña debe tener al menos **10 caracteres**
- Cambiarla invalida cualquier token emitido antes del cambio, cerrando las sesiones abiertas en otros navegadores
- Panel → icono de llave en la barra lateral → **Cambiar contraseña**
- Las cuentas nuevas (creadas por un superadmin) deben cambiar su contraseña obligatoriamente en el primer inicio de sesión
