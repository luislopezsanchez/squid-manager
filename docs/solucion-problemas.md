# Solución de problemas

## El contenedor Squid no arranca
```bash
docker compose logs squid
```
La primera vez, Squid se compila desde el código fuente (~10-15 minutos). Espera a ver "Accepting SSL bumped HTTP Socket connections".

## El proxy no bloquea sitios HTTPS
Necesitas SSL Bump. Ver [ssl-bump.md](ssl-bump.md).

## El navegador muestra advertencia de certificado
Instala el certificado CA desde el panel → "Certificado".

## No puedo acceder al panel
```bash
docker compose ps    # Verificar que todos los contenedores están UP
docker compose logs backend    # Ver errores del backend
```

## Reinstalé y el backend no arranca: «password authentication failed»

Sobrevivió el volumen de datos de la instalación anterior. La contraseña de una
base de datos ya creada **no se cambia poniendo otra en el `.env`**:
`POSTGRES_PASSWORD` solo surte efecto la primera vez, cuando PostgreSQL crea la
base vacía. Si el volumen ya existía, conserva la contraseña original y el
backend, que usa la nueva, no puede entrar.

Ojo con esto al reinstalar en otra ruta: Compose nombra los volúmenes según el
**nombre del directorio** del proyecto, así que dos instalaciones en rutas
distintas pero con la misma carpeta (`squid-manager`) comparten volumen.

```bash
# Ver si existe el volumen de una instalación anterior
docker volume ls | grep pgdata
```

Dos salidas:

```bash
# 1) Empezar de cero. BORRA TODOS LOS DATOS (usuarios, reglas, historial)
docker compose down -v && docker compose up -d
```

```bash
# 2) Conservar los datos: recupera la DB_PASS con la que se creó la base,
#    ponla en el .env y levanta de nuevo
docker compose up -d
```

El instalador comprueba esto antes de generar un `.env` nuevo y se detiene si
encuentra un volumen huérfano, en lugar de dejar el sistema a medias.

## No recuerdo la contraseña inicial del admin
Cámbiala desde una sesión de base de datos, o revisa si sigue en el log:
```bash
docker compose logs backend | grep -A3 "Administrador inicial"
```
En instalación nativa: `reset-admin-password.sh` (ver el propio script, en la
raíz del proyecto).

## Salir a Internet a través de otro proxy (padre e hijo)

En muchas empresas el cortafuegos cierra la salida directa y todo el tráfico
tiene que pasar por el proxy corporativo. SquidManager puede colocarse detrás
de otro proxy, y la configuración se hace en **Panel → Proxy padre**.

El reparto de papeles es lo que hace que funcione:

| | Hijo (el de abajo) | Padre (el de arriba) |
|---|---|---|
| Autentica usuarios | **Sí** | No: confía en el hijo |
| Filtra por dominio | **Sí** | No |
| Intercepta HTTPS | **Sí** | **No**: solo tuneliza |
| Sale a Internet | No: por el padre | **Sí** |

Encadenar dos proxies necesita cuatro ajustes, y faltando cualquiera no
funciona:

1. **En el hijo**: servidor, puerto y —si las pide— credenciales del padre
2. **En el hijo**: el certificado CA del padre, si el padre también intercepta HTTPS
3. **En el padre**: `trusted_sources` con la IP del hijo, para que no le pida credenciales
4. **En el padre**: `ssl_bump_enabled = false`, porque solo uno puede interceptar HTTPS

Si ambos son SquidManager, además necesitan un `visible_hostname` distinto:
Squid rechaza como bucle lo que ya lleve su nombre en la cabecera `Via`.

Para comprobar que funciona, la última columna del registro de accesos del hijo
pasa de `HIER_DIRECT` a `FIRSTUP_PARENT`.

> **Guía completa en [proxy-padre.md](proxy-padre.md)**: el porqué de
> cada pieza, la configuración paso a paso, y una tabla para identificar por el
> síntoma cuál de los cuatro ajustes falta — todos dan errores que no mencionan
> la causa.

## Eximir a un grupo de la interceptación de HTTPS

En **Grupos**, cada grupo tiene la casilla **«No interceptar el HTTPS de este
grupo»**. Sus miembros navegan con el tráfico cifrado de extremo a extremo.

Sirve para dos casos habituales:

- **Equipos donde no se puede instalar el certificado**: móviles personales,
  BYOD, dispositivos de invitados
- **Herramientas que se rompen al interceptarlas**: git, npm, docker y
  cualquier aplicación con *certificate pinning*

> **Eximir del descifrado no es eximir del filtrado.** El bloqueo por dominio
> actúa sobre el SNI, antes de descifrar, así que a esos usuarios les sigue
> afectando. También siguen autenticándose y quedando registrados. Lo único que
> se pierde es la inspección de la URL completa y del contenido.

Para comprobar que está funcionando, en el registro de accesos sus conexiones
HTTPS aparecen como `TCP_TUNNEL/200 CONNECT`, sin la petición descifrada
(`GET https://…`) que sí se ve en los demás.

## Orígenes que no tienen que autenticarse

En **Configuración → Seguridad**, el ajuste `trusted_sources` acepta IPs o
redes que pueden navegar sin credenciales:

```
trusted_sources = 203.0.113.10 198.51.100.0/24
```

Pensado para un proxy hijo que ya autentica a sus propios usuarios. Vacío por
defecto: todo el mundo debe autenticarse.

> Es una exención de autenticación: indicá el origen concreto. Si esa IP es una
> salida NAT compartida, **cualquier equipo detrás de ella queda exento**.

## Usar tus propios servidores DNS (por ejemplo, un Pi-hole)

Squid resuelve los nombres por su cuenta, así que puedes indicarle a qué
servidores preguntar y hacer que la navegación del proxy herede el filtrado de
un Pi-hole, un AdGuard o el DNS interno de tu empresa.

1. Panel → Configuración → `dns_nameservers` → las IPs separadas por espacios
2. Pulsa **Probar** para comprobar que responden
3. Guardar → Aplicar cambios

```
dns_nameservers 172.27.0.1
```

Vacío = Squid usa la resolución del sistema (el comportamiento por defecto).

**Solo IPs, no nombres de host.** Squid tiene que poder preguntar sin resolver
nada primero, que es justo lo que aún no puede hacer.

> **Si pones más de uno, el filtrado deja de estar garantizado.** Squid reparte
> las consultas entre todos los servidores de la lista, no los usa como
> respaldo: añadir un DNS público junto al Pi-hole hace que la parte de
> consultas que le toquen al público se resuelva sin filtrar. Para que **todo**
> pase por el filtro, deja un único servidor.

Al aplicar, se comprueba que los servidores responden de verdad y el cambio se
rechaza si no lo hacen. Es a propósito: un DNS inalcanzable no rompe una web,
deja de resolver todas a la vez, y el síntoma no apunta a la causa.

Si el Pi-hole corre como contenedor en la misma máquina, usa la IP de la
pasarela de su red Docker (`docker network inspect`), no `127.0.0.1`: dentro
del contenedor de Squid, esa dirección es el propio Squid.

## Cambiar el puerto del proxy
1. Panel → Configuración → `http_port` → poner el puerto nuevo → Guardar
2. Panel → Aplicar cambios

No hay que editar ningún fichero a mano: el backend actualiza `PROXY_PORT` en el
`.env` y recrea el contenedor con Docker Compose, así que el cambio también
sobrevive a un `docker compose up -d` o a un reinicio de la máquina.

**Abre el puerto nuevo en el firewall del servidor** y cierra el anterior si ya
no se usa:

```bash
sudo ufw allow 8128/tcp && sudo ufw delete allow 3128/tcp
```

El panel no gestiona el firewall. Sin esa regla, Squid escucha correctamente
pero los clientes no llegan, y el síntoma es una conexión que se queda colgada
sin ningún mensaje de error.

> Squid escucha siempre en el **3128 dentro del contenedor**; el puerto que
> eliges es el que Docker publica hacia fuera. Por eso `squid.conf` muestra
> `http_port 3128` aunque los clientes se conecten a otro puerto: el puerto
> vive en un único sitio (`PROXY_PORT`), y así no puede desincronizarse.

## Actualizar desde el panel falla con `fatal: $HOME not set`

Ver [actualizacion.md](actualizacion.md#la-actualización-desde-el-panel-falla-con-fatal-home-not-set)
— afecta a instalaciones nativas o Docker entre las versiones 0.24.2 y 0.24.7.

## Un "Aplicar cambios" corta el servicio con una ACL grande

Corregido — ver la entrada correspondiente en [CHANGELOG.md](../CHANGELOG.md).
Si seguís viendo cortes al aplicar una ACL de archivo grande, confirmá primero
la versión instalada (`/health`) antes de reportarlo como nuevo.

## Squid no arranca después de instalar o actualizar (instalación nativa)

Si tenés una ACL de archivo con muchos dominios cargados (probado en vivo:
5.87 millones), Squid puede tardar **más de 90 segundos** en levantar —
tanto en un arranque en frío como en un `systemctl restart` — porque
necesita reconstruir en memoria el árbol de búsqueda de esa lista antes de
poder aceptar conexiones. `systemd` corta el arranque a los 90s por
defecto (`TimeoutStartSec`), así que el servicio queda en `failed (Result:
timeout)` aunque Squid no tenga ningún error real: solo necesitaba más
tiempo.

Confirmá la causa:

```bash
systemctl status squid   # "Result: timeout"
journalctl -u squid -n 20 --no-pager   # "start-pre operation timed out"
ls -la /etc/squid/acl_lists/   # ¿algún archivo de varios MB/millones de líneas?
```

Reintentar sin más no alcanza — vuelve a fallar igual. Dale más tiempo al
arranque, una vez:

```bash
mkdir -p /etc/systemd/system/squid.service.d
printf '[Service]\nTimeoutStartSec=300\n' > /etc/systemd/system/squid.service.d/timeout-temporal.conf
systemctl daemon-reload
systemctl reset-failed squid
systemctl restart squid   # puede tardar varios minutos; es esperable
```

Confirmado en vivo: con una ACL de 5.87 millones de dominios, el arranque
puede tardar entre 1 y 4 minutos según la carga de la máquina — largo, pero
no infinito. Una vez que Squid queda `active`, si tu instalación va a
seguir teniendo esa ACL de forma permanente, dejá el aumento del timeout de
forma fija (en vez de borrar el archivo `.conf` de arriba); si fue algo
puntual, podés quitarlo después:

```bash
rm /etc/systemd/system/squid.service.d/timeout-temporal.conf
systemctl daemon-reload
```
