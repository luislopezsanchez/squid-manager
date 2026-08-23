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

> ℹ️ **Deny-list:** los usuarios LDAP **navegan apenas se sincronizan**. Si alguien no
> debe tener acceso, hay que deshabilitarlo a mano en el panel (ver "Gestión de usuarios LDAP").
> Antes era al revés (allow-list estricto, nadie navegaba hasta habilitarlo uno por uno);
> se invirtió a pedido explícito, con el trade-off documentado: si el directorio tiene
> cuentas de servicio o gente sin acceso previsto, van a poder navegar automáticamente
> tras la primera sincronización.

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

## Bloquear acceso: la única forma real de interrumpir a alguien

Hubo un botón "Forzar re-autenticación" que se quitó del panel. Se dejó documentado el
motivo porque es un límite real de HTTP Basic Auth, no un detalle interno: **ningún
servidor puede borrar la caché de credenciales que un navegador ya tiene guardada**.
Purgar la caché de Squid (lo que hacía ese botón) solo obliga a Squid a re-chequear
contra la fuente en la siguiente petición de cada quien — si la contraseña sigue siendo
válida, el navegador la reenvía solo y Squid la vuelve a aceptar sin que nadie vea un
cartel de login. Se comprobó en vivo antes de sacarlo: no lograba lo que el nombre
prometía, así que mantenerlo solo generaba confusión.

### Bloquear acceso (deshabilitar usuario)

- **Qué hace:** elimina al usuario del archivo `squid_passwd` (o de la allow-list LDAP) y
  purga la caché de credenciales de Squid.
- **Efecto:** es la única acción que corta el acceso de forma **visible**: al no encontrar
  la credencial, Squid devuelve 407 y el navegador **sí** vuelve a preguntar usuario y
  contraseña, sin importar si la sesión seguía dentro de su `credentialsttl`.
- **Es temporal:** se puede volver a habilitar en cualquier momento.
- **Alcance:** un solo usuario en la base de datos, pero la purga de credenciales que lo
  acompaña es global (ver más abajo) — así que bloquear a alguien también obliga a
  **todos** los demás a volver a autenticarse, aunque solo uno haya perdido el acceso.

### Purga de credenciales (interna, ya no es una acción manual)

Squid mantiene una caché única y global de credenciales validadas. Purgarla (reiniciando
el proceso) es necesario para que ciertos cambios surtan efecto sin esperar hasta dos
horas, y ocurre **automáticamente** al bloquear a alguien, cambiar su contraseña,
resetearla, o que le caduque la cuenta — no hace falta ni existe un botón separado para
dispararla a mano. Como se explicó arriba, purgarla por sí sola **no** fuerza un re-login
visible para quien conserve una contraseña válida.

### Cuándo usar bloquear acceso

| Situación | Acción |
|-----------|--------|
| Un empleado deja la empresa o se le suspende el acceso | Bloquear acceso |
| Sospechas que alguien usa credenciales ajenas | Bloquear acceso + resetear contraseña |
| Cambiaste la política de contraseñas | Resetear la contraseña de cada usuario afectado |

---

## Gestión de usuarios LDAP (deny-list)

Los usuarios LDAP **navegan apenas se sincronizan**. El flujo es:

1. **Sincronizar** (panel → LDAP) — importa los usuarios del directorio a SquidManager
   (solo metadatos: username, nombre, email; nunca contraseñas), con búsqueda paginada
   para no perder usuarios en directorios de más de 1.000 cuentas. El filtro de búsqueda
   es configurable (`sync_filter`) — no está atado a Active Directory: sirve para
   cualquier directorio LDAPv3 (OpenLDAP, FreeIPA, AD), con un selector de tipo de
   directorio en el panel que rellena un filtro de partida razonable para cada uno.
2. **Quedan habilitados por defecto.** Si alguien no debe navegar, hay que
   deshabilitarlo a mano desde **Usuarios** (no desde la página de LDAP: la gestión de
   quién puede navegar vive junto a los usuarios locales, en una sola tabla con
   buscador y filtro por origen/estado).
3. **Solo los habilitados** tienen una entrada en la allow-list que el helper de
   autenticación consulta — el nombre de la lista interna no cambió, pero su política
   de arranque sí: antes vacía por defecto, ahora llena.

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

> **Nota técnica:** el JWT trunca `iat` a segundos enteros al codificarlo, pero
> `password_changed_at` conserva microsegundos. Sin margen, iniciar sesión en el mismo
> segundo del cambio de contraseña comparaba `iat < changed_at` por el redondeo y cerraba
> la sesión recién creada con un 401 falso. Se corrigió con un margen de 2 segundos en la
> comparación — no debilita la revocación real, solo evita el falso positivo del mismo
> segundo.

---

## Notas de seguridad

- Las contraseñas de los usuarios LDAP **nunca se almacenan** en SquidManager.
- Solo se guarda el hash htpasswd de los usuarios **locales**, con permisos de fichero restringidos a `600`.
- La purga de credenciales afecta a todos los usuarios (limitación de Squid) y se dispara automáticamente al bloquear, cambiar o resetear una contraseña, o al caducar una cuenta — no hay un botón manual separado.
- Los intentos de login están limitados por IP y por cuenta (ver [docs/production.md](production.md)), para dificultar la fuerza bruta contra el panel.
