# Changelog — SquidManager

Todos los cambios notables de este proyecto se documentan aquí.
El formato está basado en [Keep a Changelog](https://keepachangelog.com/).

---

## [0.10.1] - 2026-08-25

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