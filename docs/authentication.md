# Autenticación y Sesiones — SquidManager

Este documento explica los tipos de cuentas, cómo funciona la autenticación del proxy,
la vida de las sesiones y las acciones de gestión disponibles.

---

## Tipos de cuentas

SquidManager maneja **dos tipos de cuenta completamente separados**:

| Tipo | Tabla | Autenticación | ¿Puede navegar? |
|------|-------|---------------|-----------------|
| **Admin** (panel) | `admins` | JWT (token del panel) | ❌ No |
| **Usuario** (proxy) | `proxy_users` | `basic_ncsa_auth` / LDAP | ✅ Sí |

- Los **admins** gestionan la plataforma (ACLs, reglas, usuarios, config). No existen en
  el proxy, así que no pueden navegar.
- Los **usuarios** son las cuentas que navegan a través del proxy. Si un admin quiere
  navegar, debe crearse **además** una cuenta de usuario.

### Roles de administrador

| Rol | Puede leer | Puede modificar | Gestiona otros admins |
|-----|------------|------------------|------------------------|
| **Superadmin** | Todo | Todo | Sí |
| **Admin** | Todo | Todo excepto administradores | No |
| **Viewer** (solo lectura) | Todo | Nada | No |

El superadmin principal (`id=1`, creado al arrancar por primera vez) no puede ser eliminado, degradado ni desactivado por nadie, ni siquiera por sí mismo.

### Primer acceso

No hay contraseña por defecto. Al arrancar por primera vez se crea la cuenta `admin` con una contraseña aleatoria (o la que se defina en `ADMIN_INITIAL_PASSWORD`), visible una sola vez en el log del backend, y con el cambio de contraseña marcado como **obligatorio**: el panel no deja continuar hasta que se define una nueva. Lo mismo ocurre con cualquier cuenta que cree un superadmin — la contraseña inicial la conoce quien la crea, así que hay que sustituirla.

---

## Métodos de autenticación

Squid soporta **un único helper de autenticación básica** a la vez. SquidManager
implementa un helper personalizado que combina ambos orígenes:

1. **Usuarios locales** (`basic_ncsa_auth`): verificados contra el archivo `squid_passwd`
   (formato htpasswd, coste bcrypt configurable), generado automáticamente desde la tabla `proxy_users`.
2. **Usuarios LDAP/AD** (`ldap3`): verificados contra el directorio configurado.

El helper consulta **primero local y luego LDAP**, de modo que ambas formas conviven. Cualquier fallo inesperado se registra y deniega esa petición sin matar el proceso — si el helper muriera, Squid dejaría de autenticar a todo el mundo.

> ⚠️ **Allow-list estricto:** los usuarios LDAP **no navegan por defecto**. Solo navegan
> los que el admin habilita explícitamente en el panel (ver "Gestión de usuarios LDAP").

### Caducidad de usuarios locales

Un usuario del proxy puede tener una fecha de caducidad opcional. Al regenerar `squid_passwd` (en cada cambio o cada pocos minutos), los usuarios caducados quedan fuera del fichero automáticamente, aunque sigan marcados como "habilitados" en la base de datos.

---

## Vida de la sesión (credentialsttl)

Cuando un usuario se autentica, Squid **cachea sus credenciales** durante un tiempo
definido por el parámetro `credentialsttl` (por defecto: **2 horas**).

### Comportamiento

- Es un **TTL fijo desde el login**, no un timeout por inactividad.
- Durante ese periodo, el usuario **no vuelve a introducir su contraseña**, aunque esté
  inactivo.
- Al expirar, Squid pide la contraseña de nuevo.
- Configurable en **Configuración → credentialsttl** (acepta formatos como `2 hours`,
  `30 minutes`, `1 day`).

### Ejemplo

```
Login a las 09:00 con credentialsttl = 2 hours:
  - 09:00 → se pide contraseña (primer login)
  - 09:00–11:00 → no se pide (credenciales cacheadas)
  - 11:00 → se pide contraseña de nuevo
```

---

## Dos acciones distintas: bloquear vs forzar re-autenticación

Son conceptos diferentes, aunque desde la corrección de seguridad ambas cortan el acceso de inmediato:

### Bloquear acceso (deshabilitar usuario)

- **Qué hace:** elimina al usuario del archivo `squid_passwd` y **purga la caché de credenciales de Squid**.
- **Efecto:** el usuario deja de poder navegar de inmediato, incluso si tenía una sesión ya autenticada dentro de su `credentialsttl`.
- **Es temporal:** se puede volver a habilitar.
- **Alcance del bloqueo en sí:** un solo usuario. La purga de credenciales que lo acompaña es global (ver más abajo), así que bloquear a un usuario también obliga a **todos** los demás a volver a autenticarse.

### Forzar re-autenticación (purgar caché de credenciales)

- **Qué hace:** purga la caché de credenciales de Squid reiniciando el proceso.
- **Efecto:** todos los usuarios deben volver a introducir su contraseña.
- **Alcance:** GLOBAL. Squid mantiene una caché única de credenciales, por lo que
  **no existe "purgar a un solo usuario"** sin afectar a los demás. Esta es una limitación de Squid, no de
  SquidManager. Cambiar la contraseña de un usuario o que le caduque la cuenta también dispara esta purga automáticamente.

### Cuándo usar cada una

| Situación | Acción |
|-----------|--------|
| Un empleado deja la empresa o se le suspende el acceso | Bloquear acceso |
| Sospechas de uso indebido y quieres que todos re-confirmen identidad | Forzar re-autenticación |
| Cambiaste la política de contraseñas y quieres forzar el cambio | Forzar re-autenticación |

---

## Gestión de usuarios LDAP (allow-list estricto)

Por seguridad, los usuarios LDAP **no navegan por defecto**. El flujo es:

1. **Sincronizar con AD** — el admin pulsa un botón que importa los usuarios del
   directorio a SquidManager (solo metadatos: username, nombre, email; nunca contraseñas),
   con búsqueda paginada para no perder usuarios en directorios de más de 1.000 cuentas.
2. **Habilitar usuarios** — el admin marca qué usuarios LDAP pueden navegar.
3. **Solo los habilitados** tienen una entrada en la allow-list que el helper de
   autenticación consulta.

### Grupos de usuarios

- Se pueden crear **grupos** de usuarios (locales o LDAP).
- Cada grupo se mapea a una ACL `proxy_auth` en el squid.conf.
- Se aplican **políticas** (reglas de acceso) a un grupo completo, referenciando su nombre como si fuera una ACL.
- Añadir o quitar un miembro de un grupo aplica la política de inmediato, sin necesidad de pulsar "Aplicar cambios" por separado.
- Borrar un grupo o renombrarlo se bloquea si alguna regla de acceso lo está usando; el panel indica cuál.

---

## Cambio de contraseña y revocación de sesión

Cualquier admin puede cambiar su propia contraseña desde el panel (icono de llave en la barra lateral). Requiere conocer la contraseña actual y que la nueva tenga al menos **10 caracteres**.

Al cambiarla, el backend registra el momento exacto (`password_changed_at`). Los tokens JWT emitidos **antes** de ese momento dejan de aceptarse aunque no hayan expirado por tiempo — así, si un token se filtró, cambiar la contraseña lo invalida en el acto. Por eso cambiar la contraseña de un admin escribiendo directamente en la base de datos (sin pasar por este mecanismo) no revoca las sesiones existentes: hay que hacerlo siempre desde el panel.

---

## Notas de seguridad

- Las contraseñas de los usuarios LDAP **nunca se almacenan** en SquidManager.
- Solo se guarda el hash htpasswd de los usuarios **locales**, con permisos de fichero restringidos a `600`.
- La purga de credenciales afecta a todos los usuarios (limitación de Squid), y ahora se dispara automáticamente en varias acciones (bloquear, cambiar contraseña, caducar) además del botón manual.
- Los intentos de login están limitados por IP y por cuenta (ver [docs/production.md](production.md)), para dificultar la fuerza bruta contra el panel.
