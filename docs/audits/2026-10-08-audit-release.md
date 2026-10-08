# Auditoría de SquidManager — 2026-10-08

| | |
|---|---|
| **Modo** | release |
| **Alcance** | rama `feat/updater-docker` @ `80b3cc4` (un commit sobre `main` @ `165d943`: 32 ficheros, +1334 / −169) y el proyecto completo con muestreo. Fuera del alcance: el VPS del responsable (no se tocó), el contenido de la imagen LXC publicada (no se descargó). |
| **Entorno de verificación** | Contenedor Ubuntu 24.04 nativo (Python 3.12, el mismo que fija `backend/Dockerfile`), seis contenedores Proxmox desechables (Docker y nativo, versiones base 1.0.1 / 1.0.2 / 1.0.5) y los runners limpios de GitHub Actions. Producción: no se tocó. |
| **Stack detectado** | Python 3.12 + FastAPI + SQLAlchemy/Alembic + PostgreSQL (pgvector); React 18 + Vite + TypeScript; Squid 6; despliegue Docker Compose y nativo (systemd + nginx). ~46 000 líneas de aplicación (272 `.py`, 97 `.ts/.tsx`), 100 ficheros de test. |
| **Auditoría previa** | 2026-09-14 (`2026-09-14-audit-full.md`) y auditoría externa 2026-09-30 |

---

## 1. Resumen ejecutivo

SquidManager es un panel web para administrar un proxy Squid (usuarios, ACL, cuotas, LDAP/Kerberos, estadísticas), que se despliega
con Docker o de forma nativa. Esta entrega cambia **cómo se actualiza desde el panel** en Docker: antes dependía de un temporizador
y de scripts instalados en el servidor que podían faltar sin que nada lo detectara (por eso «Actualizar ahora» dejaba la orden
pendiente para siempre en varias instalaciones); ahora lo hace un servicio del propio stack, y una prueba de extremo a extremo
instala desde cero y exige que la actualización se aplique. Además incluye el portal de autoservicio de usuarios del proxy.

El código entregado se comporta como dice: la suite pasa (1115), el frontend compila, no hay dependencias vulnerables y la
actualización desde la web se verificó en instalaciones limpias y en instalaciones reales 1.0.1/1.0.2, Docker y nativo. El riesgo
principal hoy **no está en esta entrega**: es una imagen completa de Proxmox, de descarga pública, que según su propia documentación
lleva claves reales de una instalación (05-006).

## 2. Veredicto

> **APTO CON RESERVAS**

No hay Críticos abiertos y la suite pasa y el sistema arranca desde cero (verificado, no supuesto). Hay un Mayor abierto (05-006,
anterior y ajeno a este cambio) con reserva explícita, y la entrega introduce un riesgo de diseño que el responsable debe aceptar
expresamente (05-007). Dos puntos del gate de publicación no pasan (2 y 8); ninguno lo introduce esta entrega (ver §5).

| Severidad | Cantidad |
|---|---|
| Crítico | 0 |
| Mayor | 1 (05-006) |
| Menor | 7 (05-007, 08-002, 13-002, 03-002 + los 3 previos: 04-002, 03-001, 09-001) |
| Nota | 7 (06-N02, 03-N03, 11-N01, 13-N01, 12-N01, 04-N01, 11-N02) |
| Riesgo aceptado (previo) | 0 |
| Regresiones | 0 |

**Reservas que el responsable debe aceptar para dar el veredicto por bueno**
1. **05-006** (Mayor, Probable): decidir qué hacer con la imagen LXC pública y rotar las claves de la instalación de origen si sigue
   activa. Si esa instalación sigue en marcha con esas claves, el hallazgo sube a **Crítico**.
2. **05-007** (Menor): aceptar que el servicio `updater` monte el socket de Docker completo (equivale a root en el servidor; es el
   mismo privilegio que ya tenía el temporizador del servidor, ahora dentro del stack).

**Qué se verificó ejecutando** (y no solo leyendo):

- Suite de tests: `pytest -q` (backend) → **1115 pasados, 1 omitido** (`pyflakes` no instalado en el entorno), 14,8 s.
- Frontend: `tsc --noEmit` → 0 errores · `npm run check-i18n` → 1990 claves en 96 ficheros, todas presentes en en/pt · `vite build` → correcto.
- `generar_compose_imagenes.py --check` → el compose de imágenes está al día.
- Dependencias: `pip-audit -r backend/requirements.txt --no-deps` → «No known vulnerabilities found»; `npm audit --omit=dev` → 0.
- CI de GitHub sobre el commit final: **CI en verde** (backend 3.11 y 3.12, frontend).
- **E2E de «Actualizar ahora» en máquinas limpias** (instalador oficial + 2 actualizaciones aprobadas por la API del panel):
  Docker en un contenedor limpio de Proxmox (31 s y 30 s; la segunda cambia la imagen del propio servicio) y en el runner de GitHub
  (17 min); nativo en un contenedor limpio (96 s y 55 s) y en el runner de GitHub (5,5 min).
- **Instalaciones reales por la web** (botón «Actualizar ahora» vía API): Docker 1.0.2 con su temporizador original → commit final
  en 56 s; nativo 1.0.1 → 126 s; nativo 1.0.2 → 136 s; nativo 1.0.5 → 60 s. Docker 1.0.1 sin temporizador: `sudo bash
  upgrade-docker.sh` lo deja en la versión nueva con el servicio activo. Docker 1.0.2 sin temporizador (el caso del VPS): se
  reproduce el síntoma original (orden pendiente para siempre) y se resuelve con `git pull && docker compose up -d --build`.
- Escenarios de fallo en Docker: el servicio se recrea a mitad de actualización (el auxiliar sobrevive y termina), el build del
  servicio roto a propósito (el panel y el proxy se actualizan igualmente y se recupera con el commit siguiente), el servicio
  parado (el temporizador del host toma el relevo y aplica la orden), orden vieja pendiente al arrancar (se aplica), y cambio de
  puerto del proxy desde el panel (solo se recrea Squid; el `updater` no se toca).
- Pruebas mutantes: se rompió a propósito la cesión del turno, la comprobación del auxiliar y el bloqueo en
  `docker-autoupdate-check.sh`; las pruebas nuevas fallaron las tres veces.
- Escaneos del gate: secretos (árbol e historial), datos privados, CRLF/BOM/bit de ejecución, licencias, lockfiles, versión.

**Qué no se pudo verificar**

- El **VPS del responsable** (estructura de carpetas de aaPanel): no se tocó, como se pidió. Se probó en instalaciones Docker
  limpias; el procedimiento esperado para él es `git pull && docker compose up -d --build`.
- **Imagen LXC publicada** (`backups/README.md`): se comprobó que la descarga es pública (HTTP 200, 2,99 GB) pero no se descargó,
  así que su contenido real no está verificado. Hace falta que el responsable lo confirme.
- Instalaciones Docker con **`install-imagenes.sh`** (sin carpeta de proyecto): su ruta de actualización no cambia y no se ejercitó.
- Docker detrás de un **proxy corporativo** para el servicio nuevo: queda documentado (`.env`) pero no se ejercitó.
- Docker rootless / Podman, límite de descargas de Docker Hub, licencias de las dependencias de Python (no hay `pip-licenses` en el
  entorno), rendimiento bajo carga y restauración real de backups.

## 3. Lo bien resuelto

1. **La cadena de actualización ahora se prueba entera, en limpio y en los dos modos**, y la publicación de imágenes depende de
   ello (`.github/workflows/update-e2e.yml`, `publicar-imagenes.yml`, `tests/e2e/`). Es la prueba que habría detectado los fallos
   repetidos de «Actualizar ahora» el primer día.
2. **Autorización por ruta**: el mapa completo (`app/routes/*.py`, AST) deja una sola ruta sin dependencia de autenticación
   (`POST /auth/login`) y solo 4 rutas de escritura accesibles a un administrador de solo lectura, las 4 legítimas por diseño
   (cambiar su propia contraseña, preguntar al asistente, iniciar sesión, enviar un mensaje de contacto).
3. **Resiliencia de llamadas externas**: todas las llamadas `httpx` llevan `timeout` y los 13 `subprocess.run` del backend también;
   no hay `shell=True`, ni `verify=False`, ni `except:` desnudo.
4. **Datos**: las 46 migraciones tienen `downgrade` real; `username` y `name` con `UNIQUE`/`NOT NULL` en la base; la consulta
   nueva del portal usa el índice `ix_ru_user_username_h` (`migrations/versions/0040_access_rollups.py:83`).
5. **Portal de autoservicio**: el token de un usuario del proxy lleva un tipo propio que la API de administración rechaza (también
   con nombres homónimos, que además ya no se pueden crear) y todo se filtra por el usuario del token; cubierto por tests.

## 4. Hallazgos

### 05-006 · Imagen de Proxmox de descarga pública con claves reales de una instalación — **Mayor** · Probable

**Dimensión**: 5 — Seguridad de la aplicación (secretos) · 11 — distribución

**Evidencia**
```
backups/README.md:3-9    «Esta imagen trae las claves reales de la instalación con la que se creó (SECRET_KEY y DB_PASS)…
                          cualquiera que haya descargado esta misma imagen —ahora o dentro de un año— tiene una puerta de entrada al panel»
backups/README.md:25     https://ftp.innovanet.uy/Proxmox_Container/vzdump-lxc-888-2026_08_28-16_27_41.tar.lzo   (2.99 GB, sha256 …)
$ curl -sI https://ftp.innovanet.uy/Proxmox_Container/vzdump-lxc-888-…tar.lzo
HTTP/2 200 · content-length: 2996418801 · last-modified: Fri, 28 Aug 2026
```

**Por qué importa**: el propio documento reconoce que `SECRET_KEY` permite fabricar una sesión de administrador sin autenticarse y que
`DB_PASS` abre la base. Cualquiera puede descargar la imagen; quien la restaure y olvide el paso de rotación (que el sistema no
fuerza) queda expuesto a todos los que la bajaron. Si la instalación de origen (contenedor 888) sigue activa con esas claves, es
acceso de administrador a ella para cualquiera: **Crítico**. No se subió de nivel porque no se pudo confirmar ni el contenido ni
que esa instalación siga viva.

**Recomendación**: (1) confirmar si el contenedor 888 sigue activo y, si es así, rotar ya su `SECRET_KEY` y `DB_PASS`; (2) retirar la
imagen o regenerarla sin `.env` con una rotación automática en el primer arranque (`install.sh` ya genera claves: reutilizarlo);
(3) mientras tanto, advertirlo al principio del `README.md` principal. Reversible: no toca el código del producto.

**Esfuerzo estimado**: bajo (rotar y retirar) a medio (regenerar la imagen)

---

### 05-007 · El servicio `updater` monta el socket de Docker completo — **Menor** · Confirmado · *pendiente de aceptación*

**Dimensión**: 5 — Seguridad (privilegios) · 2 — Arquitectura

**Evidencia**
```
docker-compose.yml  (servicio updater)   - /var/run/docker.sock:/var/run/docker.sock
backend/tests/test_updater_servicio.py   test_solo_el_updater_monta_el_socket_de_docker_completo
```

**Por qué importa**: quien comprometa ese contenedor controla el servidor (equivale a root). Es el mismo privilegio que ya tenía el
temporizador del host (un proceso root que ejecutaba los scripts del proyecto), pero ahora vive dentro del stack. Mitigaciones
comprobadas: el backend —la parte expuesta— **no** tiene el socket (un test lo impone), el servicio no publica puertos ni acepta
conexiones, sus scripts van horneados en su imagen y trata el JSON de estado como dato no confiable, y ningún servicio depende de él.
Sigue abierto el límite que ya recogía la auditoría externa (A-2): en Docker el directorio del proyecto pertenece al usuario del
backend, de modo que un backend comprometido podría sustituir `.git` y hacer que se actualice contra código ajeno. Esta entrega no
lo empeora ni lo cierra. No se subió de nivel porque la superficie de entrada no cambia.

**Recomendación**: aceptarlo expresamente (pasa a «riesgo aceptado») o, si no se acepta, desactivarlo quitando el servicio de
`docker-compose.yml` (queda el temporizador del host). Para reducirlo: fijar la imagen base por *digest* (06-N02) y, a más largo plazo,
separar el `.env` del árbol y firmar los commits (A-2).

**Esfuerzo estimado**: bajo (decidir) · alto (cerrar A-2)

---

### 08-002 · IPs reales dentro de informes y registro de cambios públicos — **Menor** · Confirmado

**Dimensión**: 8 — Privacidad · gate de publicación (punto 2)

**Evidencia**
```
docs/audits/2026-09-14-audit-full.md:135-137,140   209.126.86.242 (IP pública de un servidor real) y qué corre en él
CHANGELOG.md:700,711                                192.168.145.135 (IP privada de una VM de pruebas)
backups/README.md:25                                ftp.innovanet.uy (nombre de host de la infraestructura)
```

**Por qué importa**: 08-001 se dio por corregido al quitar la IP pública de los comentarios del código, pero el informe que lo
describía la sigue publicando, y también queda en el historial de git. Las privadas no son accesibles desde fuera, pero revelan
la red interna. Esta entrega no añade ninguna (`git diff origin/main..HEAD` sin coincidencias).

**Recomendación**: sustituir por `<IP pública del servidor>` / `192.168.x.x` en esos tres ficheros. Para la IP pública, el historial
conserva el valor: si importa, habría que reescribirlo o aceptarlo. Reversible.

**Esfuerzo estimado**: bajo

---

### 13-002 · Versiones 1.0.4, 1.0.5 y 1.0.6 sin etiqueta — **Menor** · Confirmado

**Dimensión**: 13 — Ciclo de vida

**Evidencia**
```
$ git tag --sort=-creatordate | head -2     →  v1.0.3, v1.0.2
docs/actualizacion.md:582-591               «el commit que las mueve se etiqueta en git — sin la etiqueta no hay forma de hacer git diff vX..vY»
backend/app/config.py:86 → "1.0.6" · frontend/package.json:7 → "1.0.6" · CHANGELOG.md [1.0.6]
```

**Por qué importa**: la versión de `config.py`, `package.json` y el CHANGELOG coinciden entre sí, pero faltan las etiquetas que el propio
proyecto exige. No se pusieron a propósito: cada etiqueta `v*` dispara la publicación de imágenes (≈40 min) y, desde esta entrega,
también el E2E.

**Recomendación**: etiquetar `v1.0.6` tras fusionar (cubre 1.0.4–1.0.6 en un solo hito) o decidir que esas versiones no se etiquetan y
anotarlo en la documentación.

**Esfuerzo estimado**: bajo

---

### 03-002 · Cinco ficheros superan las 1000 líneas — **Menor** · Confirmado

**Dimensión**: 3 — Calidad de código

**Evidencia**
```
frontend/src/pages/Dashboard.tsx 1602 · backend/app/services/metrics_service.py 1367 · frontend/src/pages/ProxyUsers.tsx 1221
frontend/src/pages/PanelCentral.tsx 1211 · backend/app/services/ai_service.py 1137
```

**Por qué importa**: concentran lógica difícil de cambiar sin miedo. Los tres de frontend mezclan estado, red y maquetación.

**Recomendación**: extraer por pestañas/secciones cuando se vuelva a tocar cada uno; no hace falta un esfuerzo aparte.

**Esfuerzo estimado**: alto (gradual)

---

### Notas (no cuentan para el veredicto)

- **06-N02** · La imagen base del servicio es `docker:27-cli` (etiqueta móvil) y `apk add` sin versiones (`updater/Dockerfile:10-13`); las acciones de CI
  van por etiqueta (`actions/checkout@v4`, etc.). Fijar por *digest* endurece la cadena de suministro.
- **03-N03** · 16 bloques `except Exception: pass` en `backend/app` (p. ej. `main.py:55`, `quota_service.py:95,103`, `syslog_service.py:51,59`): son
  de «mejor esfuerzo» y varios están comentados; conviene registrar al menos un `logger.debug`.
- **11-N01** · 6 scripts sin bit de ejecución en el índice (`autoupdate-check.sh`, `upgrade-nativo.sh`, `backend/entrypoint.sh`, `squid/*.sh`): se
  ejecutan siempre con `bash` o con `chmod` en el Dockerfile/instalador, pero un `./script` directo fallaría.
- **13-N01** (ya registrada) · Tres identidades de autor en el historial (`luislopezsanchez` 197, `root` 139, `llopez` 57 commits): factor de autobús efectivo 1.
- **12-N01** · Volver a una versión anterior a la 1.0.6 deja el contenedor `updater` huérfano (sigue funcionando, con su script antiguo);
  `docs/actualizacion.md:493-510` no menciona `--remove-orphans`.
- **04-N01** · El E2E de Docker tarda ≈17 min y desde esta entrega condiciona la publicación de versiones: un fallo del entorno (red, límite de
  Docker Hub) bloquearía un release sin que haya un fallo real. Está acotado a cambios en el mecanismo de actualización y a las etiquetas.
- **11-N02** · El contenedor auxiliar usa el CLI de Docker 27 / Compose 2.33 y el host puede tener versiones más nuevas (se probó con Compose 5.6 en el
  host): funcionó, pero conviene vigilarlo si Compose cambia el cálculo de recreación de contenedores.

### Corregidos durante esta auditoría (antes de congelar el alcance)

Encontrados al revisar y probar el propio cambio, y corregidos con test que falla sin la corrección:

| ID | Severidad | Qué era | Cómo se comprobó |
|---|---|---|---|
| 11-003 | Mayor | **Regresión de la 1.0.4 ya publicada**: los ficheros de latido (`.update_heartbeat`) no estaban en `.gitignore`; `git status` salía sucio y `install.sh` se negaba a re-ejecutarse en Docker. | `test_git_ignora_de_verdad_esos_ficheros`; tras actualizar un servidor real, `git status --short` → 0 líneas |
| 10-003 | Mayor | Dentro del contenedor, `git` se negaba a leer el proyecto montado («dubious ownership»), la rama salía vacía y se actualizaba contra `main` en vez de la rama del servidor. Lo encontró la prueba en un servidor real, no un test unitario. | `safe.directory` en la imagen + falla en vez de adivinar; test dedicado y E2E |
| 10-002 | Mayor | El contenedor auxiliar que aplica la actualización no tenía tiempo límite: una descarga colgada dejaba «en curso» para siempre. | `timeout 7200` verificado en un servidor real (`docker ps` del auxiliar) y en test |
| 01-001 | Menor | `docs/actualizaciones-automaticas.md` seguía describiendo el temporizador del host como único mecanismo en Docker. | Reescrito; revisión de enlaces |

Y, ya corregido antes en la misma jornada: `install.sh`/`upgrade-docker.sh` no creaban `/usr/local/lib/squidmanager` (1.0.5, `165d943`).

### Dimensiones sin hallazgos nuevos

- **Dimensión 1 — Requisitos y transparencia:** solo el desfase documental corregido (01-001); las afirmaciones de actualización y de privacidad se contrastaron con el código y las pruebas.
- **Dimensión 2 — Arquitectura:** las decisiones están registradas (`docs/project-log.md`, entrada de 2026-10-07, que recoge la «opción 2» evaluada en 2026-09-19).
- **Dimensión 7 — Datos:** 46 migraciones con `downgrade` real, constraints en base, scripts de backup/restauración con tests.
- **Dimensión 9 — Rendimiento:** la consulta nueva está indexada; sigue abierto 09-001 (previo).
- **Dimensión 10 — Resiliencia:** timeouts y límites verificados; ver los corregidos arriba.
- **Dimensión 12 — Operabilidad:** `/health` devuelve versión y commit desplegados; el servicio registra en `docker logs` con rotación (`max-size 5m`); rollback documentado (ver 12-N01).
- **Dimensión 14 — Interfaz:** las pantallas nuevas asocian etiquetas (`htmlFor`), usan `role`/`aria-*` y las cadenas están en los tres idiomas (CI las verifica); no se levantó navegador para juzgar maquetación.

## 5. Gate de publicación

| # | Verificación | Resultado | Evidencia |
|---|---|---|---|
| 1 | Sin secretos en árbol e historial | **PASA** (con 05-006 aparte) | Sin coincidencias de claves/tokens/cadenas de conexión; ningún `.env`/`.pem`/`.key` añadido en el historial. La imagen LXC con claves vive fuera del repositorio (05-006). |
| 2 | Sin datos privados (IPs, credenciales, clientes) | **NO PASA** (preexistente) | 08-002. **Esta entrega no añade ninguno** (diff contra `main` sin coincidencias); ya estaban publicados. |
| 3 | `.gitignore` correcto, verificado con `git ls-files` | **PASA** | Sin ficheros sensibles versionados; los ficheros de ejecución del actualizador ya se ignoran (11-003). |
| 4 | Finales de línea LF en scripts para Linux | **PASA** | Cero CRLF y cero BOM en `.sh`/`.py`/`.yml`; `.gitattributes` con `eol=lf`. (11-N01: bit de ejecución, Nota.) |
| 5 | Licencia presente y compatible | **PASA** | AGPL-3.0-or-later + `NOTICE` + `THIRD_PARTY_NOTICES.md`; dependencias de producción del frontend MIT/ISC/BSD. Python: no verificado a fondo. |
| 6 | Dependencias sin CVE crítico o alto | **PASA** | `pip-audit` y `npm audit --omit=dev` limpios; `package-lock.json` versionado y `requirements.txt` fijado. |
| 7 | La suite pasa y el proyecto arranca desde cero | **PASA** | 1115 pasados; E2E de instalación limpia Docker y nativo (local y GitHub). |
| 8 | Versión y changelog coherentes con la etiqueta | **NO PASA** | Coherentes entre sí (1.0.6) pero sin etiquetas 1.0.4–1.0.6 (13-002). |
| 9 | Rollback documentado | **PASA** | `docs/actualizacion.md` §«Volver a una versión anterior» + `restore-database.sh` (12-N01, Nota). |

**Lectura del gate**: los dos puntos que no pasan son preexistentes o de convención de publicación; fusionar esta entrega no los empeora.
Quien decida si eso basta para publicar es el responsable: la guía de auditoría dice que cualquier fallo del gate bloquea, y aquí
se recomienda **no** bloquear esta entrega por ellos (el dato privado ya es público y la etiqueta es una decisión de proceso), y
tratar 05-006 como prioritario aparte.

## 6. Plan de acción priorizado

| # | Acción | Hallazgo | Severidad | Esfuerzo |
|---|---|---|---|---|
| 1 | Confirmar si el contenedor 888 sigue activo y rotar `SECRET_KEY`/`DB_PASS`; retirar o regenerar la imagen LXC pública | 05-006 | Mayor (Crítico si sigue viva) | Bajo–medio |
| 2 | Aceptar (o descartar) el privilegio del servicio `updater`; fijar su imagen base por *digest* | 05-007, 06-N02 | Menor | Bajo |
| 3 | Sustituir las IPs/hostnames de informes y CHANGELOG por marcadores | 08-002 | Menor | Bajo |
| 4 | Decidir el etiquetado `v1.0.6` (cubre 1.0.4–1.0.6) | 13-002 | Menor | Bajo |
| 5 | Añadir `--remove-orphans` a la guía de «volver a una versión anterior» | 12-N01 | Nota | Bajo |

## 7. Notas para la próxima auditoría

- Reverificar 05-006 en cuanto el responsable actúe, y ver si el **VPS de producción** ya aplicó el procedimiento
  (`git pull && docker compose up -d --build`) y muestra «updater healthy».
- Vigilar que el E2E de GitHub se mantenga estable (04-N01) y revisar cuántas veces ha bloqueado un release sin motivo.
- Pendiente de verificar: ruta de actualización de `install-imagenes.sh`, Docker detrás de proxy corporativo con el servicio nuevo,
  licencias de Python con `pip-licenses`, y la imagen LXC real (descarga y revisión de contenido) si el responsable lo autoriza.
- Los tres Menores previos (04-002 sin tests de frontend, 03-001 dobles de prueba —**han pasado de 6 a 18 ficheros**—, 09-001 N+1) siguen abiertos.
