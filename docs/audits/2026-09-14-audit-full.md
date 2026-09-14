# Auditoría de SquidManager — 2026-09-14

| | |
|---|---|
| **Modo** | full |
| **Alcance** | `main` @ `8c317ed` (v0.24.8) — todo el repositorio, con foco en los 14 commits posteriores a la auditoría anterior (`73fbc04..8c317ed`: actualizaciones automáticas, scripts de instalación/upgrade, reset de contraseña) |
| **Entorno de verificación** | Windows 11 (desarrollo), Python 3.12 en venv limpio (`C:\sqmv`), Node 24, `gh` CLI contra GitHub. VM de pruebas Ubuntu 24.04 (172.30.36.116, systemd 255) usada en solo lectura para confirmar 10-001 e investigar los comportamientos reportados |
| **Stack detectado** | Backend FastAPI 0.136 / Starlette 1.6 / SQLAlchemy 2 / Alembic sobre PostgreSQL+pgvector; frontend React 18 + Vite + TypeScript; despliegue nativo (systemd + nginx) o Docker Compose; Squid gestionado |
| **Auditoría previa** | 2026-09-13 (full, `NO APTO` → corregido el mismo día, pendiente de confirmación por CI) |

---

## 1. Resumen ejecutivo

SquidManager sigue siendo un panel funcional y cuidado: la suite pasa (420/423, 3 omitidos por ser solo-Linux), el CI de GitHub está en verde para los tres últimos commits de `main`, `pip-audit` y `npm audit` no reportan vulnerabilidades, no hay secretos ni CRLF, y las tres correcciones de ayer están efectivamente en `main` (`73fbc04`). Los 14 commits de esta semana son casi todos parches sobre el mecanismo de actualización nativa, y ahí está el riesgo principal hoy: el flujo `panel → sudoers → autoupdate-check.sh → systemd-run → upgrade-nativo.sh → install-nativo.sh` acumuló cuatro capas de re-ejecución y guardas de entorno, cada una explicada por un bug real, y la forma en que se lee el resultado final de la unidad transient (`--collect`) es incorrecta: siempre reporta éxito (confirmado en VM). Aparte, se encontró un defecto de configuración independiente y de más impacto: en despliegue Docker, `DATA_KEY` se genera con cuidado en `install.sh` pero `docker-compose.yml` nunca la pasa al backend, así que el cifrado en reposo de credenciales de terceros no está operando en ese modo.

## 2. Veredicto

> **APTO CON RESERVAS**

Cero Críticos. Tres Mayores, cada uno con reserva explícita abajo (05-005, 10-001, 08-001). Suite verificada pasando y CI en verde. El arranque real se verificó en la VM (`/health` → `0.24.7`/`c7745a8`, servicios activos); 10-001 se reprodujo ahí con una unidad transient de prueba.

| Severidad | Cantidad |
|---|---|
| Crítico | 0 |
| Mayor | 3 (10-001 confirmado en VM) |
| Menor | 3 nuevos (+3 abiertos previos) |
| Nota | 4 |
| Riesgo aceptado (previo) | 0 |
| Regresiones | 0 |

**Qué se verificó ejecutando** (y no solo leyendo):

- Suite backend: `C:\sqmv\Scripts\python -m pytest -q` (venv limpio desde `requirements.txt`) → **420 passed, 3 skipped, 9 warnings in 15.39s**.
- CI real: `gh api repos/luislopezsanchez/squid-manager/actions/runs?branch=main` → `8c317ed success`, `d0c75d6 success`, `914ea24 success`.
- `pip-audit -r backend/requirements.txt` → `No known vulnerabilities found`.
- `npm audit --omit=dev` (frontend) → `found 0 vulnerabilities`.
- `npx tsc --noEmit -p frontend` → **1 error** (ver 13-001).
- CRLF en `*.sh`/entrypoints versionados → ninguno; `.gitattributes` fuerza LF.
- Secretos (patrones de key/token/password con valor literal) en el árbol → ninguno. `git ls-files` sin `.env`, `.pem`, `.key`, dumps.
- Mapa ruta → dependencia de autorización sobre los 23 routers (script sobre `app/routes/*.py`) → el único endpoint sin `get_current_admin`/`require_writer`/`require_superadmin` es `POST /api/auth/login`.
- Coherencia de versión: `backend/app/config.py`, `frontend/package.json`, `CHANGELOG.md` → las tres en `0.24.8`.
- Migraciones: 23 archivos, 23 con `downgrade()`.

**Qué no se pudo verificar**: arranque real del backend y del proxy (sin Postgres/Squid locales); que `docker compose` efectivamente arranque con la `.env` de `install.sh` (05-005 se confirmó leyendo el compose, que es determinista, no ejecutándolo).

## 3. Lo bien resuelto

- **Las tres correcciones de ayer llegaron a `main` y el CI las confirma** (`73fbc04`): suite 420/420 útiles, `starlette 1.6.0` fijado explícitamente con el porqué en `requirements.txt:1-8`, nota en `.env.example:7-12`.
- **Autorización por endpoint sin huecos**: 22 de 23 routers exigen sesión; escritura → `require_writer` (`auth_service.py:102`), acciones de mayor alcance (admins, actualizaciones) → `require_superadmin`. Revocación de sesiones por `iat` < `password_changed_at` (`auth_service.py:85-95`).
- **Modelo de privilegios del actualizador**: el backend nunca ejecuta nada con privilegios salvo un script fijo sin argumentos permitido por sudoers (`install-nativo.sh:594`, `update_service.py:56`), y ese script re-verifica la condición por su cuenta antes de actuar. Es un diseño correcto, aunque su lectura del resultado tenga el problema de 10-001.
- **Timeouts en todas las llamadas salientes** (httpx 10–15 s, `smtplib` 15 s, `subprocess` 3–180 s): revisadas las 9 ocurrencias sin `timeout` en la misma línea; todas lo tienen en la línea siguiente.
- **Cada bug corregido esta semana lleva su explicación en el código**, con fecha y síntoma. Es raro y valioso; la contracara es 08-001 (esas notas incluyen la IP pública del servidor donde se encontró).

## 4. Hallazgos

---

### 05-005 · `DATA_KEY` nunca llega al backend en despliegue Docker — **Mayor** · Confirmado

**Dimensión**: 5 — Seguridad (cruza con 1, transparencia, y 11, configuración)

**Evidencia**
```
docker-compose.yml:57-72 (servicio backend, bloque environment):
      DATABASE_URL: ...
      SECRET_KEY: ${SECRET_KEY:?...}
      ACCESS_TOKEN_EXPIRE_MINUTES: ${TOKEN_EXPIRE:-480}
      ... BCRYPT_COST, ADMIN_INITIAL_PASSWORD, PROJECT_DIR, DOCKER_HOST ...
   → no existe ninguna línea DATA_KEY, ni env_file: en el servicio.

install.sh:187-193 y 209-220: genera DATA_KEY con openssl y la escribe en .env
   ("ok '.env creado con SECRET_KEY, DATA_KEY y DB_PASS aleatorias'").

backend/app/config.py: DATA_KEY: str = ""
backend/app/crypto_service.py:47-49 / :87:
   if not settings.DATA_KEY: return None ... "sin DATA_KEY configurada: se guarda en texto plano"
```
Compose solo inyecta las variables listadas en `environment`; `.env` en la raíz lo usa para interpolar el compose, no para poblar el contenedor. Resultado: dentro de `squidmgr-backend`, `DATA_KEY=""` siempre.

**Por qué importa**: en Docker (el modo por defecto, `DEPLOY_MODE=docker`), la contraseña de bind de LDAP, credenciales SMTP, token de Telegram, API keys del asistente de IA, credenciales del proxy padre y el keytab quedan **en texto plano en PostgreSQL**, y por tanto en cada volcado de `backup-database.sh` (`.gitignore:56-62` describe exactamente ese riesgo). El proyecto presenta el cifrado como configurado (`install.sh` lo anuncia) sin que esté operando. No es Crítico porque no hay exposición directa: la base solo escucha en la red interna de Compose y las credenciales de terceros ya vivían en claro antes de que existiera `DATA_KEY`; lo que falla es una promesa de defensa en profundidad, no un control de acceso.

**Recomendación**: agregar `DATA_KEY: ${DATA_KEY:-}` al bloque `environment` del servicio `backend` en `docker-compose.yml` (una línea, sin riesgo: vacío sigue significando "sin cifrar", que es el estado actual). Tras el `docker compose up`, volver a guardar cada credencial desde el panel para que se cifre (el propio `crypto_service.py:16-21` describe esa migración de doble lectura). Sumar un test en `backend/tests/test_install_docker.py` que lea `docker-compose.yml` y exija que toda variable que `install.sh` escribe en `.env` y `config.py` declara aparezca en `environment` — es exactamente lo que habría atrapado esto.

**Esfuerzo estimado**: bajo.

---

### 10-001 · El resultado de la actualización se lee de una unidad ya recolectada por `--collect` — **Mayor** · Confirmado

**Dimensión**: 10 — Resiliencia y modos de fallo (cruza con 12, operabilidad)

**Evidencia**
```
autoupdate-check.sh:206-209:
    systemd-run --unit="$UNIDAD" --collect --property=Type=oneshot ... bash upgrade-nativo.sh

autoupdate-check.sh:136-143 (siguiente tic del temporizador, apply.status == running):
    ACTIVA="$(systemctl is-active "$UNIDAD" ...)"
    if [ "$ACTIVA" = "active" ] || [ "$ACTIVA" = "activating" ]; then exit 0; fi
    CODIGO="$(systemctl show "$UNIDAD" -p ExecMainStatus --value 2>/dev/null || echo 1)"
    ...
    if [ "$CODIGO" = "0" ]; then escribir_apply "ok" ... else escribir_apply "error" ...
```
`--collect` (`systemd-run(1)`: *"unload the transient unit after it completed, even if it failed"*) descarga la unidad en cuanto termina. Cuando el temporizador vuelve a pasar (hasta 60 s después), `squidmanager-autoupdate-run` ya no existe: `systemctl show` sobre una unidad no cargada responde con un stub de valores por defecto (`LoadState=not-found`, `ExecMainStatus=0`) y sale con 0. En ese caso `CODIGO` es `"0"` **haya fallado o no** la actualización → `apply.status = "ok"` y `actualizar_check_tras_aplicar` marca "al día" con el commit que haya quedado en disco. La única situación en que el código real es visible es que el tic ocurra en la ventana entre `inactive` y la recolección, que es inmediata.

**Confirmado en la VM de pruebas 172.30.36.116 (Ubuntu 24.04, systemd 255) el 2026-09-14**:
```
$ systemd-run --unit=sqm-audit-test --collect --property=Type=oneshot --wait bash -c 'exit 3'
Job for sqm-audit-test.service failed because the control process exited with error code.
$ systemctl show sqm-audit-test -p LoadState,ActiveState,Result,ExecMainStatus
Result=success
ExecMainStatus=0
LoadState=not-found
ActiveState=inactive
```
Y el propio `.update_state.json` de esa VM ya lo muestra en producción: `apply.status="ok"`, `apply.commit="d5038ff"` (el commit de ANTES), `log_tail` con "Deactivated successfully" al instante y un `upgrade-nativo-20260914_110441.log` de 0 bytes — una actualización que nunca corrió, reportada como aplicada. El síntoma: una actualización que falla a mitad (por ejemplo `install-nativo.sh` abortando en el chequeo de puertos o en `npm run build`) aparece en el panel como "aplicada" con el `log_tail` mostrando el error.

**Recomendación** (reversible, dos opciones, la primera preferida):
1. **Que el resultado lo escriba quien lo conoce**: al final de `upgrade-nativo.sh` (ambas ramas del `if COMMIT_SERVIDO = COMMIT_ESPERADO`) escribir `$INSTALL_DIR/backend/.update_result` con `ok <commit>` o `error <commit>`; que `autoupdate-check.sh` lea ese archivo en vez de `ExecMainStatus`, y lo borre al consumirlo. Independiente de systemd y del momento del tic. Con `trap 'echo "error" > ...' ERR` cubre también un corte inesperado.
2. Alternativa mínima: quitar `--collect`, leer `ExecMainStatus` y `Result` y luego `systemctl reset-failed "$UNIDAD"` para limpiar. Deja unidades cargadas entre tics, pero el estado sí sobrevive.

En ambos casos, verificar en la VM con una actualización forzada a fallar (por ejemplo `BRANCH=inexistente`) que el panel muestre "error".

**Esfuerzo estimado**: bajo–medio (más la verificación en VM).

---

### 08-001 · IP pública de un servidor real del usuario en comentarios versionados — **Mayor** · Confirmado

**Dimensión**: 8 — Privacidad y datos (gate de publicación, ítem 2)

**Evidencia**
```
install-nativo.sh:250:  # (209.126.86.242, 2026-09-13)-, sin llegar siquiera a este chequeo de
install-nativo.sh:506:  # (209.126.86.242, 2026-09-13): con el puerto de Squid libre, la
install-nativo.sh:739:  # (209.126.86.242, 2026-09-13): el puerto 3000 ya lo ocupaba un contenedor de Grafana
upgrade-docker.sh:113:  # ... en vivo (172.126.86.242, 2026-09-13)
```
`209.126.86.0/24` no es un rango privado (RFC 1918) ni de documentación (RFC 5737). El repositorio es público. Los comentarios además describen qué corre en ese host (Grafana en el 3000, Node 22 de NodeSource, SquidManager). Las IPs `172.30.36.x` y `192.168.145.135` del CHANGELOG/código son privadas y no aplican.

**Por qué importa**: es información de reconocimiento sobre un servidor de producción publicada de forma permanente; aunque se corrija ahora, queda en el historial de git. Es Mayor y no Crítico porque no es una credencial: no da acceso, reduce el esfuerzo de quien lo busque.

**Recomendación**: reemplazar en los 4 comentarios por una descripción neutra ("un servidor compartido con Grafana en el 3000") o por una IP de documentación (`203.0.113.x`), y adoptar como regla que las notas de "visto en vivo" no llevan IP pública. Como el dato ya está en el historial, evaluar si conviene reescribirlo (`git filter-repo`, con fuerza en `main`; disruptivo para cualquier clon existente) o aceptar el riesgo residual — decisión del usuario, se deja anotada.

**Esfuerzo estimado**: bajo (el reemplazo); alto si se reescribe el historial.

---

### 13-001 · El frontend no compila con `tsc` y nadie lo comprueba — **Menor** · Confirmado

**Dimensión**: 13 — Automatización de calidad

**Evidencia**
```
$ npx tsc --noEmit -p frontend
src/pages/ACLs.tsx(86,47): error TS2322: Type 'string | null' is not assignable to type 'string'.

frontend/package.json:11:  "build": "vite build"          ← sin tsc
.github/workflows/ci.yml:80:  run: npm run build             ← idem
```
`acl.value` pasó a ser `string | null` con la externalización de ACLs de archivo (migración 0023); el `return` de `ACLs.tsx:78-85` evita que llegue `null` en la práctica, pero el tipo no lo garantiza y el error está ahí desde entonces sin que ningún paso lo vea.

**Recomendación**: (1) corregir la línea (`value: acl.value ?? ''`); (2) agregar `"typecheck": "tsc --noEmit -p ."` a `package.json` y correrlo en el CI antes de `npm run build`. Con solo 1 error hoy es el momento barato de hacerlo.

**Esfuerzo estimado**: bajo.

---

### 14-001 · Mensaje de error 413 hardcodeado en español — **Menor** · Confirmado

**Dimensión**: 14 — Interfaz e internacionalización

**Evidencia**
```
frontend/src/api/client.ts:101-103:
    if (res.status === 413) {
      throw new Error('El archivo supera el tamaño máximo permitido (250 MB).')
```
`client.ts` ya importa de `../i18n` (línea 1) y `traducir()` existe (`i18n/index.ts:72`). Ayer se cerró una auditoría de i18n con 0 claves pendientes; este commit (`21c83fa`/posterior) reabrió una.

**Recomendación**: `throw new Error(traducir('El archivo supera el tamaño máximo permitido (250 MB).'))` y sumar la clave a `en.json`/`pt.json`.

**Esfuerzo estimado**: bajo.

---

### 11-002 · nginx nativo sin CSP ni gzip: deriva entre los dos modos de despliegue — **Menor** · Confirmado

**Dimensión**: 11 — Configuración / 5 — Seguridad

**Evidencia**
```
frontend/nginx.conf:13-20   add_header Content-Security-Policy "default-src 'self'; ..." always;
frontend/nginx.conf:26-30   gzip on; gzip_types ...
install-nativo.sh:759-770   (server block nativo): X-Frame-Options, X-Content-Type-Options,
                            Referrer-Policy — sin Content-Security-Policy, sin gzip
```

**Por qué importa**: el mismo panel tiene distinta postura de seguridad según cómo se instaló, y la próxima cabecera que se agregue a uno se olvidará en el otro. La CSP no es decorativa: es la mitigación real de XSS en una SPA que renderiza contenido de logs.

**Recomendación**: copiar las líneas de CSP y gzip de `frontend/nginx.conf` al heredoc de `install-nativo.sh`. Mejor todavía: un único `nginx.conf.j2`/plantilla en el repo del que ambos modos deriven, para que no vuelva a pasar.

**Esfuerzo estimado**: bajo.

---

### Notas (no cuentan para el veredicto)

- **03-N02 · Comentarios y mensajes desactualizados en el actualizador**: `install-nativo.sh:607` y `:636` dicen "cada 5 min", el timer es `OnUnitActiveSec=1min` (`:626`); `install-nativo.sh:589` referencia `docs/actualizaciones.md`, el archivo es `docs/actualizaciones-automaticas.md`; `install-nativo.sh:370` hace `git config --system --add safe.directory` sin comprobar si ya está (`upgrade-nativo.sh:129-130` sí lo comprueba), así que `/etc/gitconfig` acumula una línea idéntica por cada upgrade.
- **10-N01 · `upgrade-nativo.sh` corre el backup dos veces**: el re-exec de `:157-162` vuelve a empezar desde el paso 1 (`backup-database.sh`), como el propio comentario admite. Inofensivo, pero en bases grandes duplica el tiempo y los archivos en `backups/`. Se resuelve saltando el paso 1 cuando `SQUIDMGR_UPGRADE_REEXEC=1`.
- **01-N01 · Dependencia externa de Google Fonts** (`frontend/index.html:15-19`, permitida por la CSP): en la red típica donde vive un proxy corporativo (salida filtrada, a veces sin internet directo desde el navegador del admin) el panel arranca con fuentes de fallback y una espera de conexión; además cada carga del panel informa a Google la IP del administrador. Empaquetar Figtree/JetBrains Mono en `public/` lo hace 100 % local.
- **06-N01 · `docker-socket-proxy` con `POST=1 EXEC=1 IMAGES=1 VOLUMES=1 NETWORKS=1 ALLOW_RESTARTS=1`** (`docker-compose.yml:24-33`): es prácticamente el socket completo. Ya reconocido en `update_service.py:7-10` como "riesgo ya activo y ya anotado"; se deja aquí para que figure en el ledger y no solo en un comentario.

### Reverificación de hallazgos previos

- **04-001** (suite rota) → sigue corregido: 420 passed / 0 failed hoy, CI verde. Commit `73fbc04`.
- **06-001** (CVEs starlette) → sigue corregido: `pip-audit` limpio con `starlette==1.6.0`. Commit `73fbc04`.
- **11-001** (`.env.example` sin nota Docker) → sigue corregido: nota en `.env.example:7-12`. Commit `73fbc04`.
- **04-002**, **03-001**, **09-001** → siguen abiertos, sin cambios (`frontend/package.json` sin `test`; 6 dobles `_FakeQuery`; `find_references` sin cambios en `squid_names.py:119`).

### Dimensiones sin hallazgos nuevos

- **Dimensión 2 — Arquitectura**: sin hallazgos; capas `routes → services → models` respetadas en los 3 servicios leídos (`update_service`, `auth_service`, `crypto_service`); las decisiones estructurales están documentadas en docstrings largos y en `docs/architecture.md`.
- **Dimensión 4 — Pruebas**: sin hallazgos nuevos; suite verde; 7 `TODO` en total en el código, ninguno relacionado con los cambios de la semana.
- **Dimensión 6 — Cadena de suministro**: sin hallazgos; `pip-audit` y `npm audit` limpios; `package-lock.json` versionado; versiones fijadas con `==`.
- **Dimensión 7 — Datos**: sin hallazgos nuevos; 23/23 migraciones con `downgrade()`; `backup-database.sh`/`restore-database.sh` presentes y documentados.
- **Dimensión 9 — Rendimiento**: sin hallazgos nuevos (09-001 sigue abierto).
- **Dimensión 12 — Operabilidad**: sin hallazgos nuevos; `/health` reporta commit; logs por `journalctl`/`logger -t squidmanager-autoupdate`; `log_tail` de la actualización visible en el panel.

## 5. Gate de publicación

*(No aplica: modo `full`. Si se corriera en modo `release`, el ítem 2 —datos privados— fallaría por 08-001 hasta corregirlo.)*

## 6. Plan de acción priorizado

| # | Acción | Hallazgo | Severidad | Esfuerzo |
|---|---|---|---|---|
| 1 | Agregar `DATA_KEY: ${DATA_KEY:-}` al `environment` del backend en `docker-compose.yml` + test que compare `.env`/`config.py` contra el compose | 05-005 | Mayor | bajo |
| 2 | Reemplazar las 4 IPs públicas en comentarios de `install-nativo.sh`/`upgrade-docker.sh` | 08-001 | Mayor | bajo |
| 3 | Que `upgrade-nativo.sh` escriba su resultado en un archivo y `autoupdate-check.sh` lo lea, en vez de `ExecMainStatus` de una unidad recolectada; verificar en VM con un fallo forzado | 10-001 | Mayor | medio |
| 4 | Corregir `ACLs.tsx:86` y sumar `tsc --noEmit` a `package.json` y al CI | 13-001 | Menor | bajo |
| 5 | `traducir()` en el mensaje 413 de `client.ts`; CSP + gzip en el nginx nativo | 14-001, 11-002 | Menor | bajo |

## 7. Notas para la próxima auditoría

- **Reproducir 10-001 en la VM** antes de darlo por confirmado o descartarlo: `systemctl show squidmanager-autoupdate-run -p ExecMainStatus --value; echo $?` después de que la unidad haya terminado y sido recolectada.
- Tras corregir 05-005, verificar en un despliegue Docker real que las credenciales LDAP/SMTP queden cifradas (`SELECT bind_password FROM ldap_config` debe empezar por `gAAAA`).
- El usuario iba a describir comportamientos inesperados que observa; cruzarlos contra 10-001 y contra el doble backup (10-N01) antes de buscar causas nuevas.
- Sigue pendiente decidir sobre 04-002 (tests de frontend): con `tsc` en el CI (13-001) al menos habrá una red de tipos.
