# Auditoría de SquidManager — 2026-10-08 (completa, tras la 1.0.9)

| | |
|---|---|
| **Modo** | full (diagnóstico: no se corrigió nada) |
| **Alcance** | `main` @ `7246e06` (1.0.9): backend FastAPI (~26 000 líneas, 191 rutas), frontend React/TS, instaladores y scripts, CI, documentación. Muestreo, no exhaustivo |
| **Entorno de verificación** | Linux, Python 3.12 (venv limpio con `requirements-dev.txt`), Node 20, Docker (imagen del backend construida en limpio), CT 103 de pruebas |
| **Stack detectado** | Python 3.12 · FastAPI/SQLAlchemy/Alembic · PostgreSQL+pgvector · React 18/Vite/TS · Squid 6 · despliegue Docker Compose y nativo (systemd+nginx) |
| **Auditoría previa** | 2026-10-08 (modo release, sobre la 1.0.6) |

## 1. Resumen ejecutivo

SquidManager es un panel de administración para Squid maduro y bien defendido en lo que más importa: autenticación y autorización
por ruta, validación de todo lo que acaba en `squid.conf`, cifrado de credenciales en reposo, cabeceras de seguridad y cero
vulnerabilidades conocidas en dependencias. Esta auditoría **no encontró ningún hallazgo Crítico ni Mayor nuevo**. Lo que sí
aparece es una **familia de límites silenciosos** (listas truncadas sin avisar, como el de los 1000 usuarios ya corregido), huecos
de cobertura de pruebas justo en las rutas más delicadas (copias de seguridad, usuarios, LDAP, ACLs) y deuda de documentación tras
seis versiones seguidas. El riesgo principal sigue siendo el ya conocido **05-006** (imagen pública con claves reales).

## 2. Veredicto

> **APTO CON RESERVAS**

Cero Críticos; un Mayor abierto de antes (05-006) que sigue necesitando una decisión del propietario. La suite pasa y el sistema
arranca (verificado).

| Severidad | Cantidad |
|---|---|
| Crítico | 0 |
| Mayor | 1 (05-006, previo) |
| Menor | 16 (9 nuevos; 4 corregidos en 1.0.10) |
| Nota | 14 (3 nuevas) |
| Riesgo aceptado | 0 |
| Regresiones | 0 |

**Qué se verificó ejecutando**
- Suite: `pytest tests -q` → **1136 passed, 1 skipped** (≈15 s). Cobertura medida: **55 %** de `app/`.
- Arranque: imagen del backend construida en limpio, `alembic upgrade head` (47 migraciones, una sola cabeza), bajada y subida de la 0047 en PostgreSQL real; API y panel respondiendo en el CT 103.
- `pyflakes backend/app` (24 imports sin uso), `tsc --noEmit` (0 errores), `pip-audit` (0 vulnerabilidades), `npm audit --omit=dev` (0).
- Mapa de autorización construido importando la aplicación: 191 rutas; solo 3 sin autenticación (`POST /api/auth/login`, `GET /`, `GET /health`, las tres esperables). Los tokens del portal de autoservicio no abren rutas de administrador (`typ`).
- Búsqueda de secretos en el árbol y en 415 commits: ninguno (sí las IPs de 08-002).
- Reproducción en vivo del límite de 1000 usuarios con 11 000 usuarios LDAP sembrados (ya corregido en 1.0.9).

**No se pudo verificar**: comportamiento visual del panel (sin navegador; pedir capturas); sincronización real contra un LDAP/AD con miles de cuentas; rendimiento con cientos de miles de líneas de log; contenido de la imagen pública (05-006); actualización desde la web en un servidor Docker real con la 1.0.7–1.0.9.

## 3. Lo bien resuelto (no tocar)

1. **Autorización y sesiones.** Toda ruta de escritura exige `require_writer`/`require_superadmin` (las 3 excepciones son legítimas: cambiar la propia contraseña, preguntar al asistente, contacto). Los JWT se invalidan al cambiar la contraseña; los de usuarios del proxy llevan huella de la clave y tipo propio (`auth_service.py:80-260`). Tiempo de respuesta igualado para usuarios inexistentes.
2. **Inyección en la configuración de Squid.** Validación central (`squid_names.py`), defensa en profundidad en LDAP (`ldap.py:89`, `squid_service.py:538`), restauración de copias revalidando cada ajuste (`backup.py:222-260`). Sin `shell=True`, sin SQL con datos del usuario (los 2 `text(f…)` interpolan constantes internas).
3. **Cadena de suministro.** `pip-audit` y `npm audit` limpios; versiones fijadas con motivo; avisos de terceros cubren todo `requirements.txt` (hay un test que lo exige).
4. **Contenedores y red.** Backend sin root, base de datos sin puerto publicado, Squid en red propia, CSP/XFO/nosniff en nginx, subidas con tope de tamaño.
5. **Pruebas de lo difícil.** E2E de instalación limpia + 2 actualizaciones en Docker y nativo, con puerta en la publicación; 1136 pruebas que protegen regresiones concretas con su motivo escrito.

## 4. Hallazgos nuevos

### 01-002 · Lista de grupos LDAP truncada a 1000 sin avisar — **Menor** · Confirmado
**Dimensión**: 1 (requisitos y transparencia) · mismo patrón que el bug de los 1000 usuarios.
```
backend/app/routes/ldap.py:305-330   paged_search(...) lee TODOS los grupos
backend/app/routes/ldap.py:330       return {"groups": sorted(nombres)[:1000]}
```
**Por qué importa**: en un directorio con más de 1000 grupos, los últimos por orden alfabético no se pueden elegir en Grupos; no hay aviso. `docs/authentication.md:193` presenta la paginación como garantía de «no perder» cuentas.
**Recomendación**: devolver todos con un campo `truncado` o paginar/buscar en servidor; como mínimo avisar en pantalla. **Esfuerzo**: bajo.

### 01-003 · «Exportar logs» corta en 50 000 entradas sin decirlo en pantalla — **Menor** · Confirmado
```
backend/app/routes/logs.py:117   get_logs(limit=50000, …)      docs/api-reference.md:1132 (único sitio donde se dice)
```
**Por qué importa**: quien exporta para una investigación o una auditoría recibe un archivo incompleto creyendo que es completo.
**Recomendación**: cabecera `X-Truncado`/aviso en la UI o exportar en streaming sin tope. **Esfuerzo**: bajo-medio.

### 01-004 · Ayuda integrada desactualizada tras 1.0.3–1.0.9 — **Menor** · Confirmado
```
frontend/src/content/docsAcls.ts   sin menciones a filtros ni acciones en bloque (1.0.8)
frontend/src/content/*             sin ninguna página sobre el portal de autoservicio (módulo, 1.0.3)  [existe en docs/authentication.md]
```
**Recomendación**: añadir ambas secciones (es/en/pt). **Esfuerzo**: bajo.

### 04-003 · Cobertura 55 % con huecos en las rutas más delicadas — **Menor** · Confirmado
```
pytest --cov=app → TOTAL 55 %
routes/backup.py 13 %   routes/proxy_users.py 20 %   routes/ldap.py 27 %   services/runtime/docker_runtime.py 30 %
routes/acls.py 35 %     services/backup_v2_service.py 36 %   routes/logs.py 35 %   services/squid_service.py 42 %
```
**Por qué importa**: son restauración de copias, alta/edición de usuarios, sincronización LDAP y reinicio de Squid. Los dos bugs de «límite silencioso» de esta sesión estaban justo en este hueco. Se juzga Menor (y no Mayor) porque la restauración v2 y el generador de configuración sí tienen pruebas dedicadas.
**Recomendación**: pruebas de ruta (con la base simulada que ya usa la suite) para restore legado, importación de usuarios y sync LDAP; medir cobertura en CI como tendencia, sin umbral. **Esfuerzo**: medio.

### 05-008 · El límite de intentos por cuenta no bloquea nada — **Menor** · Confirmado (lectura de código)
```
backend/app/routes/auth.py:50-70     el 429 solo sustituye al 401 cuando la clave YA es incorrecta; una clave correcta entra siempre
backend/app/middleware/__init__.py:21-22   LOGIN_MAX_REQUESTS=10 por IP/min; LOGIN_MAX_PER_USER=5 (solo etiqueta)
```
**Por qué importa**: un atacante distribuido (varias IPs) puede adivinar contraseñas a ritmo ilimitado por cuenta; solo lo frena bcrypt y el límite por IP. Es una decisión de diseño razonada (evita bloquear al administrador real), pero el nombre y la documentación sugieren una protección que no existe. Mitigan: contraseña mínima de 10, bcrypt, sesiones de 8 h.
**Recomendación**: documentarlo; considerar retraso progresivo por cuenta (no bloqueo) y aviso en notificaciones tras N fallos. **Esfuerzo**: bajo.

### 05-009 · bcrypt trunca en 72 bytes pero se aceptan contraseñas de hasta 100–128 — **Menor** · Confirmado
```
auth_service.py:21-26   _prepare(password)[:72]     routes/admins.py:27 max_length=128    schemas/proxy_user.py:9 max_length=100
```
**Por qué importa**: dos contraseñas que coinciden en los primeros 72 bytes son equivalentes; quien elige una frase de 100 caracteres cree tener más seguridad de la real (y con acentos 72 bytes son menos de 72 caracteres).
**Recomendación**: limitar `max_length` a 72 bytes con mensaje claro, o pre-hashear con SHA-256 antes de bcrypt (cambio con migración de hashes). **Esfuerzo**: bajo (límite) / medio (pre-hash).

### 09-002 · Las pantallas descargan todos los usuarios para filtrar en el navegador — **Menor** · Probable
```
frontend/src/api/client.ts (listarTodo)   usada por ProxyUsers, Groups, Cuotas, DelayPools, LdapConfig
DelayPools/Groups/Cuotas solo necesitan nombres; LdapConfig solo el total
```
**Por qué importa**: con 11 000 usuarios son ~3 MB por pantalla y varias peticiones; con 100 000 deja de ser razonable. Es la contrapartida de la corrección 1.0.9 (la rápida y segura).
**Recomendación**: endpoints `?q=`/`/count` y selectores con búsqueda en servidor. **Esfuerzo**: medio.

### 10-005 · Envío de notificaciones sin tope de concurrencia ni reintento escalonado — **Menor** · Probable
```
notification_service.py: notify() → send_email/telegram/xmpp síncronos (15–45 s de espera máx. cada uno), uno por evento
```
**Por qué importa**: con un canal caído y eventos frecuentes (accesos bloqueados, cuotas) se acumulan tareas de fondo bloqueadas; el panel no se cae, pero consume hilos y los avisos del resto de canales se retrasan.
**Recomendación**: cola con un único consumidor por canal y «circuit breaker» (dejar de intentar unos minutos tras N fallos). **Esfuerzo**: medio.

### 13-003 · CI sin linter de Python — **Menor** · Confirmado
```
pyflakes backend/app → 24 «imported but unused» (routes/squid_config.py, notifications.py, main.py…)
.github/workflows/ci.yml: sin paso de pyflakes/ruff
```
**Recomendación**: añadir `ruff check` (o `pyflakes`) al CI tras limpiar los 24 avisos. **Esfuerzo**: bajo.

### 07-001 · La sincronización LDAP nunca retira cuentas ni compara mayúsculas — **Nota** · Probable
```
routes/ldap.py:~418-460  upsert por username exacto; nunca deshabilita/borra a quien ya no está en el directorio
```
Consecuencia: la lista permitida acumula cuentas obsoletas (no pueden autenticarse en el directorio, pero ensucian cuotas y listas); un cambio de mayúsculas del `sAMAccountName` crearía un duplicado. **Recomendación**: marcar «no encontrado en la última sincronización» y comparar sin distinguir mayúsculas.

### 02-001 · Hilos de fondo y límite de peticiones en memoria suponen un único worker de uvicorn — **Nota** · Confirmado
`Dockerfile:81` (un proceso); `main.py:321,354`, `update_service.py:474`, `middleware/__init__.py` (estado en memoria). Funciona; si alguien añade `--workers`, los trabajos periódicos se duplican y los límites se multiplican. Documentarlo.

### 02-002 · Dos sistemas de copia de seguridad conviven (heredado y v2) — **Nota** · Confirmado
`routes/backup.py:171-196` (export/restore JSON) y `:495-517` (v2). La ruta heredada accede por clave directa (`a["name"]`, `a["enabled"]`, `:249,:288`) y ante un archivo mal formado responde 500 en lugar de 400. Convendría fijar fecha de retirada de la ruta heredada.

## 5. Hallazgos previos: estado

| ID | Sev | Estado hoy |
|---|---|---|
| 05-006 | Mayor | **Abierto** — sin novedades; sigue pendiente verificar el CT 888 y rotar claves |
| 05-007 | Menor | Abierto (aceptación expresa del `updater` con socket de Docker completo) |
| 13-002 | Menor | **Se agrava**: ahora faltan etiquetas git de la 1.0.4 a la 1.0.9 (última `v1.0.3`) |
| 04-002 | Menor | Abierto — frontend sin pruebas; el bug de los 1000 usuarios y el de ACLs son de esa capa |
| 03-002 | Menor | Abierto — mismos 5 ficheros >1000 líneas (Dashboard 1602, metrics_service 1367…) |
| 09-001, 03-001, 08-002 | Menor | Abiertos sin cambios |

## 6. Dimensiones sin hallazgos nuevos

- **6 Cadena de suministro**: 0 CVE (pip-audit, npm audit); licencias al día (verificadas las de `slixmpp`, `aiodns`, `pycares`, `pyasn1-modules`).
- **7 Datos**: una sola cabeza de migraciones, bajada real en todas (la 0036 revierte columnas), índices en `audit_log.timestamp`, retención de 12 meses.
- **8 Privacidad**: documentada en `docs/privacidad.md` (incluye ahora XMPP); sin datos personales versionados salvo lo ya recogido en 08-002.
- **11 Portabilidad**: sin CRLF en el repositorio (`git ls-files --eol`), `.gitattributes` presente; scripts pasan `bash -n`.
- **12 Operabilidad**: `/health` con versión y commit, estado de actualización visible en el panel, copias antes de cada actualización.
- **14 API**: errores 4xx coherentes y traducidos; sin rutas de escritura que un lector pueda usar.

## 7. Plan de mejoras para analizar (priorizado)

| # | Mejora | Hallazgos | Valor | Esfuerzo | Riesgo |
|---|---|---|---|---|---|
| 1 | **Cerrar la decisión de 05-006** (verificar el CT 888, rotar `SECRET_KEY`/`DB_PASS`, retirar la imagen pública o sustituirla por una sin datos) | 05-006 | Muy alto | Bajo | Ninguno técnico |
| 2 | **Eliminar los límites silenciosos**: grupos LDAP, exportación de logs y límite de 5000 filas en la importación; todos con aviso visible o paginación real | 01-002, 01-003 | Alto | Bajo-medio | Bajo |
| 3 | **Pruebas en las rutas de más riesgo**: restore legado, importación de usuarios, sync LDAP, acciones masivas; y una prueba de humo del frontend (Vitest) para listas grandes | 04-003, 04-002 | Alto | Medio | Ninguno |
| 4 | **Endurecer contraseñas**: tope de 72 bytes (o pre-hash) y retraso progresivo por cuenta + aviso tras N fallos | 05-009, 05-008 | Medio | Bajo | Bajo (el pre-hash exige migración) |
| 5 | **Escala de usuarios**: búsqueda y conteo en servidor para selectores de Grupos/Cuotas/Delay pools | 09-002 | Medio | Medio | Medio |
| 6 | **Higiene de entrega**: etiquetar 1.0.4–1.0.9, pyflakes/ruff en CI, limpiar los 24 imports | 13-002, 13-003 | Medio | Bajo | Ninguno |
| 7 | **Ayuda integrada** al día (ACLs en bloque, autoservicio) y nota sobre un solo worker | 01-004, 02-001 | Bajo-medio | Bajo | Ninguno |
| 8 | **Notificaciones robustas**: cola por canal con «circuit breaker» | 10-005 | Medio | Medio | Bajo |
| 9 | **Sync LDAP que retire cuentas obsoletas** (marcar, no borrar) y compare sin mayúsculas | 07-001 | Bajo | Bajo | Medio (decisión de negocio) |
| 10 | **Retirar la copia heredada** o convertir su 500 en 400 | 02-002 | Bajo | Bajo | Bajo |
| 11 | Partir los 5 ficheros >1000 líneas cuando se toquen por otro motivo | 03-002 | Bajo | Alto | Medio |

Recomendación de orden: 1 → 2 → 3 → 6 en la próxima tanda (todo lo que sube confianza con poco riesgo); 4 y 5 cuando haya más
usuarios reales con volumen; el resto, al paso.

## 8. Estado tras las versiones 1.0.10 y 1.0.11

Plan de mejoras aplicado por decisión del propietario (2026-10-08):

| Hallazgo | Estado |
|---|---|
| 05-006 imagen LXC pública | **Corregido**: archivo borrado de `ftp.innovanet.uy` (HTTP 404); era un contenedor de pruebas |
| 05-007 `updater` con socket de Docker | **Riesgo aceptado** por el propietario |
| 01-002, 01-003, 05-008, 05-009 | **Corregidos** en 1.0.10 |
| 01-004, 09-002, 10-005, 13-003, 04-002 | **Corregidos** en 1.0.11 |
| 07-N01, 02-N01, 02-N02, 11-N01 | **Resueltas** en 1.0.11 |
| 04-003 cobertura | **Abierto**: 55 % → 57 % (`proxy_users` 42 %, `backup` 32 %, `ldap` 56 %, `acls` 50 %) |
| 13-002 etiquetas git | **Corregido**: `v1.0.4` a `v1.0.11` creadas y subidas |
| 03-002 ficheros de más de 1000 líneas | Sin cambios, por decisión (refactor solo al tocarlos por otro motivo) |

Además se añadió la importación masiva en segundo plano (hasta 20 000 filas), que elimina la causa del tope de 5000 filas.
