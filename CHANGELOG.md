# Changelog — SquidManager

Todos los cambios notables de este proyecto se documentan aquí.
El formato está basado en [Keep a Changelog](https://keepachangelog.com/).

---

## [0.14.0] - 2026-08-29

### Añadido

- **Despliegue sin Docker.** SquidManager puede instalarse con Squid, el panel,
  PostgreSQL y nginx corriendo como servicios del sistema, mediante
  `install-nativo.sh`. Para redes donde la política interna no permite Docker, o
  para un equipo que ya hace de proxy y donde una capa de contenedores sobra. El
  modo se elige con `DEPLOY_MODE` y **por defecto sigue siendo `docker`**: una
  instalación existente no cambia de comportamiento al actualizar. Guía completa
  en [docs/instalacion-nativa.md](docs/instalacion-nativa.md).
- **Adaptador de runtime.** El panel necesitaba seis cosas del proceso de Squid
  —recargarlo, reiniciarlo, validar una configuración, saber si está vivo, leer
  sus contadores y hacer efectivo un cambio de puerto— y las pedía hablando
  directamente con el daemon de Docker. Ahora viven detrás de una interfaz con
  dos implementaciones, y el resto del código no sabe dónde corre Squid.
- **El instalador nativo usa `squid-openssl`, no `squid`.** El paquete a secas
  es la variante GnuTLS: sin SSL bump y sin generador de certificados. Con
  `squid-openssl` (6.14, más nueva que la que se compila en la imagen) no hace
  falta compilar nada, y las actualizaciones de seguridad llegan por `apt`.
- **El panel corre sin root en modo nativo**, con usuario propio y un sudoers de
  tres órdenes literales, sin comodines. Es bastante menos de lo que concede
  montar el socket de Docker, que es lo que exige el otro modo.
- **Panel en español, inglés y portugués**, seleccionable desde el menú lateral.
  La clave de cada texto es el propio texto en español, al estilo de gettext:
  así lo que falte por traducir sale en español y no como un identificador
  interno. 453 cadenas del panel, 409 traducidas a los dos idiomas; las 44
  restantes son comandos, directivas de Squid y ejemplos de configuración, que
  son iguales en los tres idiomas.
- **Los mensajes de la API también se traducen**, guiándose por
  `Accept-Language`. Traducir solo el panel dejaba una aplicación que estaba en
  inglés hasta que algo fallaba y entonces contestaba en español, justo en el
  momento de más fricción. Se resuelve en un único manejador de excepciones y no
  en los 60 sitios donde se lanzan los mensajes.
- **Las páginas de error del proxy en 203 idiomas** en modo nativo, vía
  `squid-langpack`. Son las que ve el usuario final, y Squid ya elegía el idioma
  por el `Accept-Language` de cada navegador. Detalles en
  [docs/idiomas.md](docs/idiomas.md).
- **Las métricas se sirven también bajo `/api/panel`.** Ver más abajo.

### Cambiado

- **En modo nativo el puerto vive en el `squid.conf`.** No hay mapeo que
  traducir, así que Squid escucha directamente donde diga el panel y cambiar de
  puerto es reescribir el fichero y reiniciar el servicio: las ~250 líneas que
  recreaban el contenedor no hacen falta ahí.
- Los ficheros con secretos que el panel escribe para Squid pasan de modo 600
  con `chown` a **640 con grupo `proxy`**. El conjunto de quien puede leerlos es
  el mismo —root, el panel y Squid—, pero así funciona también cuando el panel
  no es root y no puede hacer `chown`.
- El uid del usuario `proxy` **se resuelve del sistema** en lugar de darlo por
  supuesto en 13. Es lo habitual, pero si el usuario no existe cuando se instala
  el paquete de Squid se crea con el primer id libre.
- Varios mensajes de error **dependen ahora del modo de despliegue**: mandaban a
  reconstruir la imagen o a reiniciar el contenedor, cosas que en una
  instalación nativa no existen.
- El texto del certificado CA en el panel deja de dar por hecho que el
  despliegue es Docker.

### Seguridad

- **El proxy ya no queda abierto a la red local recién instalado.** El
  `squid.conf` de arranque que escribían el instalador nativo y el entrypoint de
  Docker permitía `10.0.0.0/8`, `172.16.0.0/12` y `192.168.0.0/16` **sin una sola
  línea `auth_param`**. Comprobado en una instalación limpia: HTTP 200 a través
  del proxy sin credenciales, y también con un usuario inexistente. La
  configuración que sí autentica solo se escribía cuando alguien entraba al panel
  y pulsaba «Aplicar cambios», y nada en la instalación decía que hubiera que
  hacerlo: quien instalaba y se iba dejaba un proxy abierto sin saberlo.

  Ahora los dos arranques niegan todo salvo `localhost`, y el backend aplica él
  solo la configuración definitiva en cuanto levanta, reintentando en segundo
  plano (en Docker la primera vez Squid tarda, porque compila desde fuente). El
  instalador espera a que aparezca `auth_param` y avisa si no llega. Pruebas
  nuevas impiden que un fichero de arranque vuelva a permitir la LAN.

### Corregido

- **El instalador nativo moría en el paso 4 sin DNS.** Al terminar el `apt`,
  `needrestart` reinicia `systemd-resolved`, y el `git clone` que va justo
  después fallaba con «Could not resolve host: github.com», dejando la máquina a
  medias. Pasó a la primera en una instalación limpia sobre Ubuntu 24.04. Ahora
  `needrestart` queda suspendido durante la instalación y el clon se reintenta
  cinco veces.
- **`PROXY_PORT` desaparece del `.env` en modo nativo.** Lo lee únicamente
  `docker-compose.yml`, para publicar el puerto del contenedor; en una
  instalación del sistema el puerto vive en el `squid.conf` y nadie consultaba
  esa variable. Quedaba con el valor de la instalación en cuanto se cambiaba el
  puerto desde el panel: una segunda copia que solo podía mentir.
- **La comprobación final del instalador daba un falso aviso.** Al aplicarse
  sola la configuración definitiva —que lleva SSL Bump y exige reinicio— Squid
  pasa unos segundos arrancando, y el instalador lo veía ahí y anunciaba que no
  estaba activo.

- **El dashboard se quedaba en «Cargando métricas…» para siempre.** La petición
  salía del código pero nunca llegaba al servidor: cero líneas en el log de
  nginx mientras el endpoint respondía en 5 ms. Lo bloqueaba el propio
  navegador, porque la URL `/api/metrics/dashboard` contiene «metrics», una
  palabra que uBlock, AdGuard y los escudos de Brave cortan por defecto al
  asociarla a telemetría. Como la petición no llega a salir, en el servidor no
  queda ni rastro, y el `.catch(console.error)` del dashboard se tragaba el
  error: no había nada que explicara el fallo.

  Quien administra un proxy es justo quien suele llevar bloqueador, así que era
  un fallo del producto esperando a ocurrirle a cualquiera. Las métricas se
  sirven ahora también bajo `/api/panel`, que es la ruta que usa el panel web;
  `/api/metrics` se conserva intacta para quien consuma la API desde fuera, que
  no es un navegador con extensiones.
- **Crear usuarios fallaba en la instalación nativa.** El backend genera el hash
  de cada usuario del proxy invocando `htpasswd`, que viene en `apache2-utils`,
  y el instalador nativo no lo incluía. La instalación terminaba diciendo que
  todo había ido bien y el fallo aparecía mucho después, al crear el primer
  usuario. El instalador ahora **comprueba los binarios que el backend ejecuta**
  y se detiene si falta alguno, en lugar de dar por buena una instalación
  incompleta.
- La prueba del cambio de puerto afirmaba el comportamiento de Docker sin fijar
  `DEPLOY_MODE`, así que pasaba o fallaba según el entorno donde se ejecutara.
  Ahora fija el modo, y se añade la prueba contraria para el modo nativo.

### Documentación

- **El README no dejaba claro que hubiera dos modos de instalación.** La
  sección de instalación empieza ahora eligiendo modo, con una tabla que
  compara los dos, y cada camino es autocontenido: sus propios pasos, su propia
  URL de acceso y su propio primer inicio de sesión. Antes el apartado «Primer
  acceso» daba solo la orden de Docker (`docker compose logs backend`), que en
  una instalación nativa no existe. El subtítulo del proyecto y la descripción
  también daban a entender que Docker era obligatorio.
- Los tres README llevan un recuadro con la documentación disponible en
  español, inglés y portugués.

### Pruebas

- `frontend/package.json` declara `engines.node >= 18.18`. Ubuntu 24.04 trae
  Node 18.19 y nada fijaba la versión: el día que Vite subiera a una que
  exigiera Node 20, las instalaciones nativas romperían sin motivo aparente.

De 127 a **162**, y pasan en los dos modos de despliegue. Las nuevas cubren la
elección del runtime, el puerto que acaba en el `squid.conf` en cada modo, el
contrato de formato de las métricas entre ambos, la traducción de los mensajes,
que el panel no pida rutas que un bloqueador pueda cortar, y que el instalador
nativo traiga todos los binarios que el código invoca.

---

## [0.13.0] - 2026-08-25

### Añadido
- **Grupos exentos de la interceptación de HTTPS** (casilla «No interceptar el
  HTTPS de este grupo», migración `0012`). Hay equipos donde no se puede
  instalar el certificado —móviles personales, BYOD— y herramientas que se
  rompen al interceptarlas: git, npm, docker y cualquier aplicación con
  *certificate pinning*. Hasta ahora la única salida era desactivar la
  interceptación para todo el mundo.
- **La exención no libra del filtrado.** El bloqueo por dominio actúa sobre el
  SNI, antes de descifrar, así que sigue aplicándose a los miembros del grupo.
  Lo que se pierde en ellos es la inspección de la URL completa y del
  contenido. Siguen autenticándose y quedando registrados.
- Los grupos exentos se marcan con una insignia en el panel, para verlos de un
  vistazo.

### Cambiado
- **La plantilla del `squid.conf` se reordena**: el bloque de autenticación
  pasa por delante del de SSL Bump. Squid lee la configuración de arriba abajo
  y no admite una ACL de usuario mientras no exista un esquema de
  autenticación: declarada antes, aborta el arranque con `Invalid ACL` y el
  proxy se queda sin servicio. Verificado que el cambio de orden no altera nada
  del comportamiento anterior.

### Notas
- Probado en ejecución, no solo generando el fichero: con dos usuarios, el no
  exento aparece en el registro con su petición descifrada (`GET https://…`) y
  el exento solo como `TCP_TUNNEL/200 CONNECT`, que es la señal de que el
  tráfico pasó cifrado de extremo a extremo.

---

## [0.12.1] - 2026-08-25

### Corregido
- **Dos SquidManager encadenados se cortaban entre sí.** Todas las
  instalaciones se llamaban `squidmanager`, y Squid rechaza como bucle de
  reenvío cualquier petición cuya cabecera `Via` ya lleve su propio nombre. El
  proxy de arriba veía su nombre en el tráfico que le mandaba el de abajo y lo
  denegaba con un `403 Acceso Denegado` que no mencionaba la causa; solo
  aparecía en el `cache.log`, como `WARNING: Forwarding loop detected`.
  Las instalaciones nuevas reciben un `visible_hostname` con sufijo único.
- El síntoma despistaba: **HTTP fallaba y HTTPS funcionaba**, porque el tráfico
  HTTPS viaja dentro del túnel y esa cabecera no se inspecciona. Parecía un
  problema de HTTPS cuando era justo al revés.

> Si vienes de una instalación anterior, tu `visible_hostname` sigue siendo
> `squidmanager`. Cámbialo en Configuración → General si vas a encadenar
> proxies.

---

## [0.12.0] - 2026-08-25

### Añadido
- **Se puede desactivar la interceptación de HTTPS** (ajuste
  `ssl_bump_enabled`, migración `0011`). Squid solo puede interceptar HTTPS una
  vez en una cadena de proxies: si dos lo hacen, el de arriba recibe la
  petición descifrada dentro de un túnel que él mismo cifró y la rechaza con un
  `403` que no explica nada. Activado por defecto, que es el comportamiento de
  siempre; se apaga en el proxy que no vaya a filtrar.
- **Orígenes exentos de autenticación** (ajuste `trusted_sources`, migración
  `0010`). Un proxy de arriba no puede pedir credenciales al de abajo —dentro
  de un túnel TLS no hay forma de negociar un 407—, así que necesita confiar en
  él por su dirección. La exención se emite **antes** de exigir credenciales;
  puesta después no serviría, porque a esas peticiones no se les llegaría a
  preguntar. Rechaza `0.0.0.0/0`.
- **Certificado CA del proxy padre** (`ca_cert`, migración `0009`), con carga
  desde archivo. Necesario cuando el padre también intercepta HTTPS: sin él,
  Squid rechaza su certificado por autofirmado
  (`X509_V_ERR_SELF_SIGNED_CERT_IN_CHAIN`) y no carga ninguna web HTTPS.

### Notas
- Encadenar dos SquidManager funciona ahora de punta a punta. Verificado con
  dos instalaciones reales: el registro del de abajo muestra `FIRSTUP_PARENT`
  en HTTP y HTTPS, y responden tanto sitios normales como los que redirigen.
- El README documenta el reparto de papeles en una cascada: quién intercepta,
  quién autentica y qué se pierde al dejar de interceptar (el filtrado por
  dominio dentro de HTTPS; el bloqueo por SNI se mantiene, porque actúa antes
  de descifrar).

---

## [0.11.0] - 2026-08-25

### Añadido
- **Salida a Internet a través de otro proxy** (tabla `parent_proxy`, migración
  `0008`, página «Proxy padre»). En muchas empresas el cortafuegos cierra la
  salida directa y todo el tráfico tiene que pasar por el proxy corporativo;
  sin esta opción, SquidManager no se podía desplegar en esas redes. Apagado
  por defecto: la salida sigue siendo directa mientras no se active.
- **Autenticación opcional** contra el padre. Muchos proxies internos no piden
  credenciales, así que los campos se dejan vacíos; la contraseña se enmascara
  al devolverla al panel, igual que la de enlace de LDAP.
- **Comprobación real antes de aplicar**, que distingue las cuatro formas de
  fallar porque cada una se arregla distinto: no se llega al padre, pide
  credenciales que no se le han dado, las rechaza, o exige un método de
  autenticación que Squid no puede presentar. Un padre inalcanzable no degrada
  la navegación: la corta entera y para todos a la vez.
- **Aviso explícito ante NTLM o Kerberos.** Squid solo sabe presentar
  autenticación básica a un padre. Si el proxy corporativo exige otra cosa
  —habitual cuando está integrado con Active Directory— la prueba lo dice en
  lugar de dejar a alguien buscando la combinación correcta de usuario y
  contraseña durante una tarde.
- **Destinos que no pasan por el padre** (`always_direct`), para la intranet.
- **Opción «no intentar nunca la salida directa»** (`never_direct`), activada
  por defecto: si el cortafuegos la bloquea, intentarla solo añade una espera
  antes de fallar igual.
- 22 pruebas, incluidas las de cada forma de fallar y la de que las
  credenciales viajen realmente en la petición.

### Notas
- La contraseña del proxy padre acaba escrita en el `squid.conf` en texto
  plano. Es una limitación de Squid, no del diseño: conviene usar una cuenta de
  servicio con los permisos justos.
- Para comprobar que el tráfico sale por el padre, la última columna del
  registro de accesos pasa de `HIER_DIRECT` a `FIRSTUP_PARENT`.

---

## [0.10.1] - 2026-08-25

### Corregido (el backend se quedaba sin logs)
- **Las migraciones dejaban muda a la aplicación.** Alembic reconfigura el
  logging al arrancar sus migraciones, y `fileConfig()` desactiva por defecto
  todos los loggers que no aparezcan en el `alembic.ini` —donde solo están
  `root`, `sqlalchemy` y `alembic`—. Como las migraciones corren durante el
  arranque del backend, a partir de ese punto **no se registraba nada más**:
  ni «Migraciones aplicadas», ni la contraseña del administrador recién
  creado, ni el «Application startup complete» de uvicorn, ni las peticiones
  atendidas, ni ningún error posterior en producción. El síntoma engañaba: el
  log se cortaba siempre en medio de Alembic y parecía que el backend se
  hubiera colgado, cuando seguía funcionando con normalidad.
- **Y el nivel de log quedaba en WARN.** Aunque los loggers ya no se
  desactiven, `fileConfig()` aplica el nivel del `alembic.ini` al logger raíz.
  Como la aplicación registra sus avisos con `logger.info()`, seguían
  descartándose por nivel. Se restaura a INFO al terminar de migrar.
- Consecuencia práctica: **la contraseña inicial del administrador era
  inaccesible**. Se generaba, se guardaba, pero el mensaje que la mostraba
  nunca llegaba al log, así que el comando que documentábamos para leerla no
  devolvía nada. En una instalación nueva era imposible entrar al panel sin
  fijar `ADMIN_INITIAL_PASSWORD` a mano.

### Cambiado (resumen del instalador)
- **El instalador espera a que el backend arranque y muestra la contraseña del
  administrador** en el resumen final. Antes remitía a
  `docker compose logs backend | grep …`, que no devuelve nada si el backend
  todavía no ha terminado —o si ha fallado—, y no había forma de distinguir un
  caso del otro. Si el backend no llega a arrancar, el instalador ahora lo dice
  y termina con error, en lugar de dar un resumen optimista.
  > Esto revierte a propósito la decisión de no imprimir credenciales. El
  > equilibrio cambia porque la contraseña ya está en el log del contenedor,
  > al alcance de quien pueda usar Docker, y porque es de un solo uso: el panel
  > obliga a cambiarla al entrar. El resumen avisa de que queda en el historial
  > de la terminal.
- **El resumen mandaba a una URL que no existe.** Anunciaba
  `API docs: http://localhost:8000/docs`, pero el puerto 8000 no se publica al
  host y `/docs` solo se sirve con `DEBUG=true`. Línea eliminada.
- **Los puertos del resumen salen del `.env`**, en lugar de estar fijos a 3000
  y 3128: quien cambiara `WEB_PORT` o `PROXY_PORT` recibía direcciones
  equivocadas. La del proxy usa además la IP del servidor, no `localhost`.
- Se añade el siguiente paso para filtrar HTTPS: instalar el certificado CA en
  los equipos cliente, con la ruta del panel donde descargarlo.

### Corregido (reinstalación sobre datos anteriores)
- **Reinstalar dejaba el backend en un bucle de reinicios imposible de
  diagnosticar.** Si sobrevivía el volumen de PostgreSQL de una instalación
  previa, el instalador generaba una `DB_PASS` nueva que la base ya creada
  ignora —`POSTGRES_PASSWORD` solo se aplica al inicializarla vacía—, así que
  el backend no podía entrar. Lo que veía el usuario era un volcado de más de
  cien líneas de SQLAlchemy con la causa enterrada en la penúltima, y un
  contenedor que aparecía como pausado. Es fácil de provocar sin saberlo:
  Compose nombra los volúmenes por el directorio del proyecto, de modo que dos
  instalaciones en rutas distintas con la misma carpeta comparten los datos.
- `install.sh` ahora comprueba si existe ese volumen antes de generar un `.env`
  nuevo, y se detiene explicando las dos salidas (empezar de cero borrando los
  datos, o recuperar el `.env` anterior) en lugar de dejar el sistema a medias.
- El backend traduce los fallos de conexión con la base a un mensaje legible
  que apunta a la causa probable, en vez de morir con el volcado entero.

### Corregido (instalador)
- **`install.sh` instalaba siempre en `/opt/squid-manager`, ignorando desde
  dónde se ejecutara.** Quien clonaba el repositorio en otra ruta y lanzaba
  `./install.sh` acababa con dos copias: el instalador descargaba una segunda a
  `/opt` y trabajaba allí, dejando el clon original sin usar y sin avisar de
  nada. Si además ese clon tenía cambios propios, se ignoraban en silencio.
  Ahora, si el script se ejecuta desde dentro de un clon, se instala ahí mismo;
  si se ejecuta suelto, sigue usando `/opt/squid-manager`; y se puede imponer
  la ruta con `INSTALL_DIR=/donde/sea ./install.sh`.
- La copia de seguridad ante cambios locales sin confirmar se creaba siempre en
  `/opt/squid-manager-backup-…`, aunque la instalación estuviera en otro sitio.
  Ahora se deja junto al proyecto que respalda.

### Documentación
- **Las dos formas de instalar están ahora explicadas como tales.** El
  repositorio traía un `install.sh` que no se mencionaba en ninguna parte del
  README, mientras la sección de instalación describía el método manual sin
  decir que existía una alternativa. Ahora ambas aparecen comparadas, con lo
  único que las diferencia de verdad: el instalador fija la ruta
  (`/opt/squid-manager`) y rellena la configuración; la manual te deja elegir
  la ruta pero exige ajustarla a mano.
- **`PROJECT_DIR` se documenta donde hace falta**: en los pasos de instalación,
  no solo en el `.env.example`. Es el ajuste que más se olvida porque el
  sistema arranca igual sin él, y el único síntoma aparece mucho después
  —cambiar el puerto desde el panel deja de tener efecto tras el siguiente
  `docker compose up -d`—, cuando ya nadie lo relaciona con la instalación.
- Se recuerda abrir el puerto del proxy en el firewall al terminar de
  instalar. No lo hace ni el instalador ni el panel.

### Corregido
- **El ajuste `dns_v4_first` no hacía nada y se ha retirado** (migración
  `0007`). La directiva está obsoleta desde Squid 5 y la 6 la rechaza al
  arrancar: se guardaba, se escribía en el `squid.conf` y Squid la descartaba
  dejando un `ERROR` en su log. Se ofrecía en el panel una opción sin efecto.
  Quien necesite priorizar IPv4 tiene que hacerlo por otra vía (que el servidor
  DNS no devuelva registros AAAA, o desactivar IPv6 en el contenedor).
- **La validación daba por buena una configuración con directivas obsoletas.**
  `squid -k parse` avisa por `ERROR` de una directiva que no reconoce pero
  termina con éxito, y solo se miraba el código de salida. Ahora también se
  revisan las líneas de error de la salida, así que una directiva obsoleta o
  desconocida se detecta al aplicar en lugar de quedar escrita sin efecto. Es
  la comprobación que habría evitado el fallo anterior.

---

## [0.10.0] - 2026-08-24

### Añadido
- **Servidores DNS propios para las consultas de Squid** (ajuste
  `dns_nameservers`, migración `0006`). Squid resuelve los nombres por su
  cuenta, así que ahora se le puede indicar a qué servidores preguntar: sirve
  para que la navegación del proxy herede el filtrado de un Pi-hole, un AdGuard
  o el DNS interno de una empresa. Vacío por defecto, que es el comportamiento
  de siempre (la resolución del sistema).
- **Comprobación real del servidor antes de aplicar.** No se valida solo el
  formato: se le envía una consulta DNS y se espera respuesta. Si no contesta,
  rechaza la consulta o responde sin resultados, el cambio se rechaza y no se
  toca el `squid.conf`. Un servidor inalcanzable aquí no rompe una web: deja al
  proxy sin resolver ningún nombre, todas las webs caen a la vez y el síntoma
  no apunta a la causa.
- **Botón «Probar» junto al campo**, que consulta los servidores sin guardar
  nada, para verificarlos antes de comprometerse.
- ~~Ajuste `dns_v4_first`: consultar IPv4 antes que IPv6.~~ **Retirado en
  0.10.1**: la directiva está obsoleta en Squid 6 y el ajuste no surtía efecto.
- 21 pruebas nuevas, incluidas las de un servidor que rechaza la consulta
  (RCODE 5) y otro que responde sin resultados: dos formas de fallar que un
  simple "¿hay algo escuchando en el puerto 53?" daría por buenas.

### Notas
- `dns_nameservers` solo acepta direcciones IP, no nombres de host: Squid tiene
  que poder preguntar sin resolver nada primero. Se rechaza al guardar, para
  que el error salga junto al campo que lo provoca.
- Squid **reparte** las consultas entre todos los servidores de la lista, no
  los usa como respaldo. Añadir un DNS público junto a un Pi-hole deja pasar
  sin filtrar la fracción de consultas que le toquen al público. Para que todo
  pase por el filtro, hay que dejar un único servidor. Queda documentado en el
  README porque es contraintuitivo.

---

## [0.9.0] - 2026-08-24

El cambio de puerto del proxy desde el panel dejaba el sistema en un estado que
parecía correcto y se rompía más tarde, sin aviso. Esta versión rehace el
mecanismo para que el puerto viva en un solo sitio.

### Corregido
- **El cambio de puerto no sobrevivía a un `docker compose up -d` ni a un
  reinicio de la máquina.** El puerto vivía en dos sitios: el `http_port` del
  `squid.conf` (generado desde la base de datos) y el mapeo de puertos de
  Docker (que sale del `.env`). Al cambiarlo desde el panel se recreaba el
  contenedor con el puerto nuevo, pero **nadie actualizaba el `.env`**. El
  sistema funcionaba hasta la siguiente recreación, momento en el que Docker
  volvía a publicar el puerto viejo —donde Squid ya no escuchaba— y el proxy
  quedaba inalcanzable desde fuera. El `.env.example` documentaba el fallo como
  si fuera parte del uso normal ("si cambias el puerto en el panel, actualiza
  también `SQUID_PORT` aquí").
- **El healthcheck daba «sano» con el proxy caído.** `squid -k check` solo
  comprueba que el proceso vive, no que acepte conexiones, así que un
  contenedor publicando un puerto donde Squid no escuchaba figuraba como sano
  mientras nadie podía navegar. Ahora también se comprueba que el puerto
  responda.
- **La recreación del contenedor perdía en silencio la configuración del
  compose.** Se reconstruía a mano con el SDK de Docker copiando campo a campo
  (imagen, volúmenes, red, etiquetas), de modo que cualquier opción del
  `docker-compose.yml` que no estuviera en esa lista desaparecía al cambiar el
  puerto. Ahora se recrea con `docker compose up -d`, que aplica el fichero
  entero. El camino anterior se conserva solo como reserva.
- El docstring de `POST /api/squid/apply` afirmaba que la recreación se hacía
  con `docker compose up -d` cuando en realidad usaba el SDK.

### Cambiado
- **El puerto del proxy vive ahora en un único sitio: `PROXY_PORT` del `.env`.**
  Squid escucha siempre en el 3128 interno del contenedor y ese valor es el que
  Docker publica hacia fuera (`"${PROXY_PORT}:3128"`). Al no haber dos copias,
  no pueden desincronizarse. El `http_port` de la base de datos pasa a
  significar «puerto publicado» y ya no llega al `squid.conf`.
- Al cambiar el puerto, el backend escribe el `.env` (de forma atómica, para no
  corromper un fichero que contiene la contraseña de la base de datos y la
  clave de firma de los JWT) y recrea el contenedor con Compose. El `.env` se
  sincroniza además en cada «Aplicar cambios», de modo que una instalación
  antigua o una edición manual se corrigen solas.
- `SQUID_PORT` desaparece del `.env`: ya no hay un puerto interno configurable.
- La imagen del backend incluye el cliente de Docker y el plugin de Compose, y
  el proyecto se monta en la misma ruta absoluta que tiene en el host (variable
  `PROJECT_DIR`, que `install.sh` rellena) para que Compose calcule las mismas
  rutas que calcularía desde fuera.

### Añadido
- Verificación de que Docker publica de verdad el puerto esperado después de
  recrear el contenedor, en lugar de dar por buena la operación.
- 9 pruebas del cambio de puerto, incluida la que fija el diseño: con
  `http_port = 9999` en la base de datos, el `squid.conf` generado sigue
  diciendo `http_port 3128`. Si esa prueba falla, el puerto ha vuelto a vivir
  en dos sitios.
- El README documenta que **el firewall del servidor no se abre solo** al
  cambiar el puerto. Es la causa más habitual de "cambié el puerto y dejó de
  funcionar": Squid escucha bien, pero los clientes no llegan y la conexión se
  queda colgada sin mensaje de error.

---

## [0.8.0] - 2026-08-23

Continuación de la prueba funcional completa: exportación de logs en más formatos, reenvío opcional a syslog externo, y corrección de la página de Auditoría (que hasta ahora solo reconocía la mitad de las entidades y acciones reales que genera el backend).

### Corregido
- **Iconos de descarga sin tamaño en Registros, Backup y Certificado**: `<IconDownload />` usado fuera de las clases `.btn`/`.stat-icon` (que dan tamaño implícito) se renderizaba al tamaño por defecto del navegador, ~300x150px. Corregido con clases de tamaño explícitas en los 6 casos.
- **Etiquetas "Total entradas" / "Mostrando: N filtradas" en Registros**: implicaban que la segunda era un subconjunto de la primera, cuando en realidad son dos conteos independientes de un escaneo en vivo del log — renombradas a "Últimas líneas analizadas" / "Coinciden con el filtro".
- **Auditoría solo reconocía 5 de 10 entidades y 4 de 12 acciones reales del backend**: el resto se mostraba con su nombre técnico en crudo (`ldap_user`, `login`, etc.) y no se podía filtrar por ellas. Completado el mapeo de etiquetas y las opciones de los dos filtros.
- **Tarjetas de resumen de Auditoría poco precisas**: mostraban las 3 entidades con más filas sin distinguir eventos de sesión de cambios de configuración reales, lo que hacía subir "Delay Pool" o "Usuario LDAP" al top mientras "Administrador" (dominado por logins) quedaba afuera pese a ser la entidad más numerosa. Reemplazadas por cuatro métricas elegidas a propósito: total de eventos, inicios de sesión fallidos, cambios de configuración (excluyendo login/login_failed) y eliminaciones.

### Añadido
- **Exportación de logs en NDJSON y formato nativo de Squid**, además de CSV (`GET /api/logs/export?format=csv|ndjson|raw`). El formato nativo preserva la línea original del access.log sin modificar, para herramientas que la esperan tal cual (AWStats, SARG, módulos Squid de Splunk/ELK); NDJSON para ingesta genérica en un SIEM.
- **Reenvío opcional a syslog externo** (página nueva "Syslog externo", tabla `syslog_config`, migración `0005`): un hilo de fondo seguido al access.log en tiempo real, con host/puerto/protocolo (UDP o TCP) y formato (RFC 3164 o RFC 5424, contenido raw o NDJSON) configurables desde el panel. Apagado por defecto — no se manda nada hasta configurar un host y habilitarlo a propósito. Probado en vivo con receptores UDP y TCP reales y con tráfico real del proxy, extremo a extremo.
- `POST /api/syslog/test` prueba un destino sin necesidad de guardar ni activar el reenvío real antes.

---

## [0.7.0] - 2026-08-23

Prueba funcional completa de la plataforma contra el sistema en marcha (no solo revisión de código), corrección de los bugs reales que salieron a la luz, y primera ronda de mejoras visuales del Dashboard y de Usuarios.

### Corregido
- **Condición de carrera en la sesión (`iat`/`password_changed_at`)**: el JWT trunca `iat` a segundos enteros al codificarlo, pero `password_changed_at` conserva microsegundos. Un login en el mismo segundo que un cambio de contraseña podía comparar `iat < changed_at` por el redondeo y cerrar la sesión recién creada con un 401 falso. Corregido con un margen de 2 segundos en la comparación.
- **`[object Object]` al crear o editar un usuario**: los errores de validación de Pydantic (contraseña corta, campo faltante) llegan como una lista de objetos, no como texto; el cliente los pasaba directo a `new Error()`, que los convierte a esa cadena literal. Ahora se extrae un mensaje legible.
- **Botones de Usuarios sin ninguna señal de que estaban trabajando**: bloquear a alguien reinicia Squid para purgar credenciales (10-20s reales). Sin ningún indicador visual, invitaba a hacer clic de nuevo — lo que de hecho encadenó varias acciones reales sobre las mismas cuentas durante las pruebas. Cada botón ahora se deshabilita y cambia de texto mientras la acción está en curso, con un guardado síncrono (no `useState`) para que ni siquiera clics disparados en el mismo instante generen una segunda petición.
- **Usuarios LDAP sin fecha de creación**: el modelo la tenía, pero el schema de respuesta nunca la incluía — se mostraba como "Invalid Date".
- **`index.html` sin cabeceras de caché**: un despliegue nuevo podía quedar invisible detrás de una copia vieja en el navegador. Ahora `index.html` se revalida siempre y los archivos con hash de la build se cachean un año sin riesgo.

### Cambiado
- **"Forzar re-autenticación" se eliminó.** Verificado en vivo: purgar la caché de Squid no fuerza un re-login visible si la contraseña sigue siendo válida — el navegador la reenvía solo y Squid la vuelve a aceptar sin preguntar nada. El botón prometía algo que no podía cumplir, por un límite real de HTTP Basic Auth (ningún servidor puede borrar la caché de un navegador ajeno), no un bug de código. "Bloquear acceso" queda como la única acción que interrumpe a alguien de verdad.
- **Usuarios LDAP nuevos quedan habilitados por defecto** (antes: allow-list estricto, deshabilitados hasta que un admin los habilitaba uno por uno). Es un cambio de postura de seguridad deliberado, a pedido explícito: ahora es deny-list — hay que deshabilitar a mano a quien no deba navegar.
- **Filtro de sincronización LDAP, configurable** (`sync_filter`, migración `0004`): antes estaba fijo en el código al filtro de Active Directory (`objectCategory=person`, atributo exclusivo de AD); contra OpenLDAP o cualquier otro LDAPv3 no encontraba a nadie, sin ningún error. Selector de "Tipo de directorio" en el panel con valores de partida para Active Directory, OpenLDAP y LDAP genérico.

### Añadido
- **Sección Usuarios unificada**: usuarios locales y LDAP en una sola tabla, con buscador, filtro por origen y por estado, columna de grupos a los que pertenece cada uno, e insignia de origen (Local/LDAP).
- **Modal de contraseña**: generar una automática o establecer una propia, con botón de copiar (con reserva para cuando el panel se sirve por HTTP plano, donde la Clipboard API del navegador no funciona).
- **Dashboard**: sparklines de tendencia en las 4 tarjetas superiores, tarjeta "Sistema" con indicadores circulares, curva de tráfico con interpolación monótona (sin inventar picos ni caer por debajo de los datos reales), tarjeta de aciertos de caché, latencia de respuesta (excluyendo túneles CONNECT, donde ese campo del log mide la duración de la conexión, no la respuesta), usuarios con más peticiones denegadas (cruzado contra el estado real de la cuenta, para no confundirlo con "cuenta bloqueada"), aviso de cambios sin aplicar.
- Auditoría del habilitar/deshabilitar de un usuario LDAP (antes no dejaba rastro).

### Rendimiento
- **Dashboard, de 4-8 segundos a 20-70 ms.** `container.stats()` del SDK de Docker fuerza dos muestreos separados por un segundo para calcular el delta de CPU, y se llamaba dos veces por carga. Ahora se lee un único `docker exec` a los ficheros de cgroup, con una caché de 2 segundos.

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