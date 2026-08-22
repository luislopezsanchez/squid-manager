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

---

## Métodos de autenticación

Squid soporta **un único helper de autenticación básica** a la vez. SquidManager
implementa un helper personalizado que combina ambos orígenes:

1. **Usuarios locales** (`basic_ncsa_auth`): verificados contra el archivo `squid_passwd`
   (formato htpasswd), generado automáticamente desde la tabla `proxy_users`.
2. **Usuarios LDAP/AD** (`ldap3`): verificados contra el directorio configurado.

El helper consulta **primero local y luego LDAP**, de modo que ambas formas conviven.

> ⚠️ **Allow-list estricto:** los usuarios LDAP **no navegan por defecto**. Solo navegan
> los que el admin habilita explícitamente en el panel (ver "Gestión de usuarios LDAP").

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

Son conceptos diferentes y la plataforma las expone por separado:

### 🚫 Bloquear acceso (deshabilitar usuario)

- **Qué hace:** elimina al usuario del archivo `squid_passwd` y recarga Squid.
- **Efecto:** el usuario ya no puede autenticarse → pierde el acceso a internet.
- **Es temporal:** se puede volver a habilitar.
- **Alcance:** un solo usuario.

### 🛑 Forzar re-autenticación (purgar caché de credenciales)

- **Qué hace:** purga la caché de credenciales de Squid (`squid -k reconfigure`).
- **Efecto:** todos los usuarios deben volver a introducir su contraseña.
- **Alcance:** GLOBAL. Squid mantiene una caché única de credenciales, por lo que
  **no existe "purgar a un solo usuario"**. Esta es una limitación de Squid, no de
  SquidManager.

### Cuándo usar cada una

| Situación | Acción |
|-----------|--------|
| Un empleado deja la empresa o se le suspende el acceso | 🚫 Bloquear acceso |
| Sospechas de uso indebido y quieres que todos re-confirmen identidad | 🛑 Forzar re-autenticación |
| Cambiaste la política de contraseñas y quieres forzar el cambio | 🛑 Forzar re-autenticación |

---

## Gestión de usuarios LDAP (allow-list estricto)

Por seguridad, los usuarios LDAP **no navegan por defecto**. El flujo es:

1. **Sincronizar con AD** — el admin pulsa un botón que importa los usuarios del
   directorio a SquidManager (solo metadatos: username, nombre, email; nunca contraseñas).
2. **Habilitar usuarios** — el admin marca qué usuarios LDAP pueden navegar.
3. **Solo los habilitados** tienen una entrada en la allow-list que el helper de
   autenticación consulta.

### Grupos de usuarios

- Se pueden crear **grupos** de usuarios (locales o LDAP).
- Cada grupo se mapea a una ACL `proxy_auth` en el squid.conf.
- Se aplican **políticas** (reglas de acceso) a un grupo completo.

---

## Notas de seguridad

- Las contraseñas de los usuarios LDAP **nunca se almacenan** en SquidManager.
- Solo se guarda el hash htpasswd de los usuarios **locales**.
- La purga de credenciales afecta a todos los usuarios (limitación de Squid).
