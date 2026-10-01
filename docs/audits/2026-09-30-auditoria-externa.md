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

## No corregido, con el motivo

- **M-2 / M-3** (restore-v2 y restore heredado sin los validadores de cada ruta, asignación masiva): solo los usa un administrador
  que ya puede cambiar toda la configuración; endurecerlo exige revisar cada entidad. Pendiente.
- **M-4 / M-5** (TLS de LDAP y de SMTP sin verificar certificado): verificar por defecto rompería los servidores internos con
  certificado propio, muy habituales en esta base de usuarios. Pendiente: opción «verificar certificado» por integración.
- **M-6** (el helper de dominios deja pasar si falla su índice): decisión deliberada (no cortar toda la navegación por un fallo del
  helper); ahora reintenta una vez y deja el error en el log.
- **M-11, M-13, M-14, M-15** y el resto de los bajos (JWT sin revocación individual, `/health` público, Squid como root en el
  contenedor, sudoers con comodines, `install-tras-proxy.sh` con `source`, TLS por defecto del panel): riesgo bajo o que exige un
  rediseño; sin cambios.
- **TLS por defecto del panel (A-7):** el panel sigue sirviéndose por HTTP; poner TLS por delante (reverse proxy) está documentado en
  `docs/production.md`. Ofrecer un certificado automático queda como mejora.

## Correcciones al propio informe

- El ledger `docs/audits/findings.md` marcaba **11-002 (cabeceras de seguridad)** como corregido: no lo estaba en las `location`
  de la SPA. Ahora sí, con prueba.
- Si pones **otro proxy inverso delante del panel**, añade su dirección a `TRUSTED_PROXY_HOSTS`; si no, el límite de intentos
  de login lo tratará como un único cliente.
