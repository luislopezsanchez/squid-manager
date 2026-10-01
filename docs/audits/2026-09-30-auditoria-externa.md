# Auditoría externa de 0.25.0 — estado de cada hallazgo

Informe original: auditoría manual de solo lectura (rama `pruebas`, commit `41a5149`). Cada hallazgo se verificó
contra el código y, donde fue posible, en vivo (servidor de pruebas nativo y servidor Docker). Resultado: los
hallazgos eran correctos en lo esencial; se corrigió lo que se podía corregir sin romper instalaciones existentes.

## Corregido (con prueba automática en `backend/tests/test_auditoria_fixes.py`)

| Id | Qué se hizo | Cómo se comprobó |
|---|---|---|
| **C-1** SSRF por el proxy | La plantilla deniega `127.0.0.0/8`, `::1`, `169.254.0.0/16` y `fe80::/10` (ACL `destino_loopback` / `destino_linklocal`). En Docker, Squid pasa a su **propia red** (`proxynet`): ya no ve al backend, la base de datos ni el proxy del socket de Docker. | En vivo: `127.0.0.1:8000`, `localhost:5432` y `169.254.169.254` devuelven 403 a un usuario válido; `docker-socket-proxy:2375` ya no resuelve desde Squid. |
| **A-1** Inyección en el script de Kerberos | `realm` y FQDN solo admiten caracteres de un realm/host DNS (al guardar y al generar); la descarga exige rol de escritura. | Tests con cargas (`"; calc #`, `$(…)`). |
| **A-3** Clave de la CA en el backend (Docker) | El entrypoint ya no entrega `ssl_cert` al usuario del backend: la clave queda `proxy:proxy 600`. | En vivo: el usuario de la app no puede leerla; el certificado público sí. |
| **A-4** Secretos guardados enviados a otro destino | SMTP, LDAP y nodos centrales solo reutilizan la contraseña guardada contra el **mismo** servidor/usuario; si no, piden escribirla. | En vivo (SMTP): 400 al probar otro servidor. |
| **A-5** Vista previa con la contraseña del proxy padre | `login=usuario:clave` sale enmascarado. | Test. |
| **A-6** Inyección en `ldap_helper.conf` | Se rechazan saltos de línea al guardar y al escribir el fichero. | Test. |
| **A-7** Cabeceras de seguridad ausentes en la SPA | CSP, X-Frame-Options, nosniff y Referrer-Policy se repiten en cada `location` (nginx no hereda los del `server` si la location declara su propio `add_header`). Cuerpo máximo 2 MB; 250 MB solo en las rutas de subida. | En vivo con nginx: la CSP llega en `/`, `/index.html` y `/assets/`. |
| **A-8** Límite de login eludible con `X-Forwarded-For` | Se toma la IP más a la derecha que no sea un proxy de confianza. | En vivo, desde otra máquina con XFF falsificado: 429 al 11.º intento. |
| **M-1** Comillas en valores de ACL | Se rechazan `"` y `'` (en Squid significan «leer este archivo»). | Test. |
| **M-7** Fórmulas en CSV/XLSX | Se neutralizan celdas que empiezan por `= + - @`. | Test. |
| **M-8** Memoria en importaciones | El XLSX deja de leerse al superar el tope de filas; los gzip de un backup se descomprimen con tope. | Test. |
| **M-9** Backups legibles por todos | `umask 077`. | Test. |
| **M-10** `must_change_password` solo en la pantalla | La API responde 403 hasta cambiar la contraseña (salvo cambiarla y `/auth/me`). | En vivo y con el navegador. |
| **M-12** `squid.conf` no atómico | Escritura atómica; el panel solo marca «limpio» si Squid aceptó la configuración. | Test. |
| **M-16** (parcial) Espacios en usuario/clave del proxy padre | Se rechazan. | Test. |
| Bajos | Telegram escapa HTML; el helper de mensajes escapa comillas; el helper de grupos LDAP reintenta grupos no encontrados al minuto; el helper de dominios reintenta una vez; `install.sh` sigue la rama activa; el CI declara `permissions: contents: read`; **PyJWT 2.13.0 → 2.15.1** (13 CVE; `pip-audit` queda limpio). | `pip-audit`: sin vulnerabilidades conocidas. `npm audit --omit=dev`: 0. |

## Corregido en parte

- **A-2 (root ejecuta código del usuario de la app).** Hecho: `pip` del instalador nativo corre como el usuario de la app
  (antes, como root dentro de un venv de ese usuario); los scripts de root (`backup`, `restore`, `reset-admin-password`,
  `upgrade-docker`) **ya no ejecutan el `.env`** (lo leen como datos); el temporizador Docker ejecuta una **copia del script
  de actualización propiedad de root**; los `git` de root no ejecutan hooks ni fsmonitor del repositorio.
  **Pendiente:** en Docker el directorio del proyecto sigue perteneciendo al usuario del backend (hace falta para reescribir el
  `.env` al cambiar el puerto), así que un backend comprometido aún podría sustituir `.git` y hacer que el temporizador traiga
  código ajeno; y no se verifican firmas de commits (exige que el autor firme sus commits). Cerrarlo del todo requiere separar
  el `.env` del árbol y firmar los commits: queda para una decisión de diseño.

## Segunda ronda (decisiones del responsable)

| Id | Decisión | Qué se hizo |
|---|---|---|
| **M-2** | Aplicar lo mínimo que tiene efecto | Al restaurar un backup v2, las configuraciones de una sola fila que acaban en ficheros de configuración (LDAP, proxy padre, Kerberos, Syslog) rechazan saltos de línea y caracteres de control; Kerberos aplica los mismos validadores de realm/FQDN que la ruta y el proxy padre rechaza espacios en host/usuario/contraseña. Los textos libres (prompts, mensajes) y los certificados PEM no se tocan. |
| **M-3** | Aplicar | El restore heredado ya no hace `SquidSetting(**s)`; LDAP pasa por una lista cerrada de campos con `validate_value`. |
| **M-14** | No aplica en parte | `htpasswd` no se invoca desde el backend (el hash se calcula en Python con bcrypt), así que la contraseña nunca va por argv. El HA1 de Digest se guarda siempre a propósito (permite activar Digest sin pedir las contraseñas de nuevo). |
| **M-15** | Ya cubierto | `_escribir_estado` es atómica (temporal + rename); un `flock` adicional no cierra ninguna carrera real porque el único otro escritor es el temporizador, que también escribe atómicamente. |
| Bajos | Aplicados | Login con coste de bcrypt igual si el usuario no existe; `install-tras-proxy.sh` lee `proxy.conf` como datos (no lo ejecuta); los scripts de autoactualización ya no interpolan el log en `python -c`; la caducidad de un usuario del proxy se puede quitar enviando `null`; el formulario de Contacto valida el email de respuesta y limita a 5 mensajes cada 10 min; `pytest` sale de `requirements.txt` (nuevo `requirements-dev.txt` para CI); sudoers del borrado histórico solo admite `AAAA MM`. |
| **sudoers** | Analizado | `conntrack -D -s *` solo puede borrar entradas de seguimiento de conexiones (no ejecuta nada), y el script de borrado ya validaba año y mes; solo se apretó el patrón del segundo. `NoNewPrivileges=no` se mantiene: sudo lo necesita. |

## No corregido, con el motivo

- **A-2 (resto):** ver arriba. Solo importa si el contenedor del backend ya está comprometido y la instalación es Docker; cerrarlo exige separar el `.env` del árbol y firmar los commits.
- **M-4 / M-5** (TLS de LDAP y de SMTP sin verificar certificado): decisión del responsable, no aplicar. Verificar por defecto rompería los servidores internos con certificado propio.
- **M-6** (el helper de dominios deja pasar si falla su índice): decisión deliberada; ahora reintenta una vez y deja el error en el log.
- **M-11** (contraseña inicial en `.env`/logs): es la única forma de entregarla en una instalación sin terminal interactiva; el cambio es obligatorio en el primer acceso y la API lo exige.
- **M-13** (`/etc/squid` con grupo escritor), **JWT sin revocación individual**, **`/health` público**, **Squid como root en el contenedor**, **TLS por defecto del panel** (decisión del responsable: lo resuelve el proxy inverso del usuario): sin cambios; riesgo bajo o exigen un rediseño.

## Correcciones al propio informe

- El ledger `docs/audits/findings.md` marcaba **11-002 (cabeceras de seguridad)** como corregido: no lo estaba en las `location`
  de la SPA. Ahora sí, con prueba.
- Si pones **otro proxy inverso delante del panel**, añade su dirección a `TRUSTED_PROXY_HOSTS`; si no, el límite de intentos
  de login lo tratará como un único cliente.
