# Salir a Internet a través de otro proxy (padre e hijo)

En muchas empresas el cortafuegos cierra la salida directa y todo el tráfico
tiene que pasar por el proxy corporativo. SquidManager puede colocarse detrás
de otro proxy —o delante de uno— para funcionar en esas redes.

Esta guía cubre el caso completo, incluido el de encadenar **dos SquidManager**,
que es el más exigente porque los dos son Squid y compiten por hacer lo mismo.

---

## Los papeles

```
   Clientes  ──►  SquidManager HIJO  ──►  Proxy PADRE  ──►  Internet
                  (filtra, autentica)     (da salida)
```

Cada proxy hace una cosa, y **no deben solaparse**:

| | Hijo (el de abajo) | Padre (el de arriba) |
|---|---|---|
| Autentica usuarios | **Sí** | No: confía en el hijo |
| Filtra por dominio | **Sí** | No |
| Intercepta HTTPS | **Sí** | **No**: solo tuneliza |
| Sale a Internet | No: por el padre | **Sí** |

El motivo de que no se solapen no es de estilo: cada solapamiento rompe la
navegación de una forma distinta y con un error que no explica la causa.

---

## Las cuatro piezas

Encadenar dos proxies necesita cuatro cosas. Faltando cualquiera, no funciona.

### 1. El hijo tiene que saber a qué padre salir

**Panel del hijo → Proxy padre.** Servidor, puerto y, si el padre las pide,
usuario y contraseña.

Squid **solo sabe presentar autenticación básica** a un padre. Si el proxy
corporativo exige NTLM o Kerberos —habitual cuando está integrado con Active
Directory— no hay usuario y contraseña que lo resuelvan: haría falta un
intermediario que traduzca la autenticación. El botón **Probar conexión** lo
dice explícitamente en lugar de dejarte adivinando.

### 2. El hijo tiene que confiar en el certificado del padre

Solo si el padre **también intercepta HTTPS** (otro SquidManager lo hace por
defecto, y muchos proxies corporativos también).

Al reenviarle el tráfico, el padre presenta su propio certificado. Sin
declararlo, Squid lo rechaza por autofirmado y **no carga ninguna web HTTPS**:

```
X509_V_ERR_SELF_SIGNED_CERT_IN_CHAIN
Self-signed SSL Certificate in chain: ... CN=SquidManager CA
```

**Panel del hijo → Proxy padre → Certificado CA del proxy padre.** Si el padre
es otro SquidManager, descargá su certificado desde **su** panel (Certificado
CA) y cargalo con el botón.

### 3. El padre no debe pedirle credenciales al hijo

**Panel del padre → Configuración → Seguridad → `trusted_sources`**: la IP
desde la que le llega el tráfico del hijo.

```
trusted_sources = 203.0.113.10
```

No es una comodidad, es una necesidad: cuando el tráfico viaja dentro de un
túnel TLS, **no hay forma de negociar un 407** —el hijo cree que habla con el
sitio de destino, no con un proxy—, así que la petición acaba denegada con un
`403` que no menciona la causa. La autenticación de los usuarios finales ya la
hizo el hijo, que es donde corresponde.

> **Cuidado con las salidas NAT compartidas.** Si esa IP es la salida de toda
> una oficina, cualquier equipo detrás de ella queda exento de autenticarse,
> no solo el proxy hijo.

### 4. Solo uno de los dos puede interceptar HTTPS

**Panel del padre → Configuración → Seguridad:**

```
ssl_bump_enabled = false
```

Squid solo puede interceptar HTTPS una vez en una cadena. Si los dos lo hacen,
el de arriba recibe la petición ya descifrada dentro de un túnel que él mismo
cifró, y la rechaza con un `403`. En el registro se ve el patrón: el `CONNECT`
sale con 200 y la petición de dentro con 403.

Se apaga en el que **no** vaya a filtrar, normalmente el padre. Con eso se
pierde el filtrado por dominio dentro de HTTPS en ese proxy —el bloqueo por SNI
sigue funcionando, porque actúa antes de descifrar— pero el tráfico pasa.

### Y una quinta, si ambos son SquidManager: nombres distintos

Squid añade su `visible_hostname` a la cabecera `Via` al reenviar, y **rechaza
como bucle** cualquier petición que ya lleve el suyo. Dos instalaciones con el
mismo nombre se cortan entre sí.

Las instalaciones nuevas reciben un nombre único automáticamente. Si alguna
viene de una versión anterior, cambialo en **Configuración → General**:

```
visible_hostname = squidmanager-oficina
```

---

## Configuración paso a paso

### En el padre

1. **Configuración → Seguridad → `trusted_sources`** = IP pública desde la que
   sale el hijo
2. **Configuración → Seguridad → `ssl_bump_enabled`** = `false`
3. **Aplicar cambios**

Si el padre no es un SquidManager, el equivalente es: permitir la IP del hijo
sin autenticación, y no interceptar su tráfico HTTPS.

### En el hijo

1. **Proxy padre** → activar, servidor y puerto
2. Credenciales, solo si el padre las pide
3. **Certificado CA del proxy padre** → cargar el del padre, si intercepta HTTPS
4. **Probar conexión**
5. Guardar → **Aplicar cambios**

---

## Comprobar que funciona

La última columna del registro de accesos del hijo lo dice todo:

| Valor | Significado |
|---|---|
| `FIRSTUP_PARENT/…` | Salió por el padre ✓ |
| `HIER_DIRECT/…` | Salió directo, **sin pasar por el padre** |
| `HIER_NONE/-` | No salió: mirá el código de respuesta |

```bash
docker exec squidmgr-proxy tail -20 /var/log/squid/access.log
```

Un resultado sano mezcla HTTP y HTTPS, todos con `FIRSTUP_PARENT`:

```
TCP_MISS/200   GET http://example.com/       usuario  FIRSTUP_PARENT/203.0.113.1
NONE_NONE/200  CONNECT www.google.com:443    usuario  FIRSTUP_PARENT/203.0.113.1
TCP_MISS/200   GET https://www.google.com/   usuario  FIRSTUP_PARENT/203.0.113.1
```

---

## Problemas frecuentes

Todos dan errores que **no mencionan la causa**. La tabla los distingue por el
síntoma exacto:

| Síntoma | Causa | Solución |
|---|---|---|
| Ninguna web HTTPS carga; el error cita `X509_V_ERR_SELF_SIGNED_CERT_IN_CHAIN` | El hijo no confía en el certificado del padre | Pieza 2 |
| `403 Acceso Denegado`; el registro del padre muestra `CONNECT` con 200 y la petición de dentro con 403 | Los dos interceptan HTTPS | Pieza 4 |
| `403` y en el registro del padre la columna de usuario sale con un nombre | El padre le pide credenciales al hijo | Pieza 3 |
| **HTTP falla y HTTPS funciona** | Bucle de reenvío: los dos proxies se llaman igual | Pieza 5 |
| `407` desde el hijo | Normal: son tus usuarios autenticándose en el hijo | — |

Ese cuarto caso es el más desconcertante, porque el síntoma apunta al revés de
donde está el problema. El motivo real solo aparece en el `cache.log` del padre:

```bash
docker exec squidmgr-proxy grep -i 'forwarding loop' /var/log/squid/cache.log
```

```
WARNING: Forwarding loop detected for:
Via: 1.1 squidmanager (squid/6.12)
```

HTTPS funciona porque viaja dentro del túnel, donde esa cabecera no se
inspecciona.

---

## Limitaciones

- **La contraseña del padre se guarda en texto plano** en el `squid.conf`. Es
  una limitación de Squid: usá una cuenta de servicio con los permisos justos,
  nunca una cuenta personal.
- **El proxy que no intercepta pierde el filtrado por dominio dentro de HTTPS.**
  El bloqueo por SNI se mantiene, porque actúa antes de descifrar.
- **Squid no puede autenticarse contra un padre con NTLM ni Kerberos.** Solo
  autenticación básica.
- **Los clientes finales necesitan el certificado del hijo**, que es quien les
  presenta el suyo. El certificado del padre solo lo necesita el hijo.
