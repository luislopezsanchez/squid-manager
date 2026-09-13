# Auditoría de SquidManager — 2026-09-13

| | |
|---|---|
| **Modo** | full |
| **Alcance** | `pruebas` @ `4d06a8d` (recién fusionada con `main`) — todo el repositorio, con muestreo dirigido por las 14 dimensiones |
| **Entorno de verificación** | VM Ubuntu 24.04 nativa (192.168.145.135), reinstalada desde cero en la sesión inmediatamente anterior; desarrollo en Windows |
| **Stack detectado** | Backend FastAPI/Python 3.12 + SQLAlchemy/Alembic sobre PostgreSQL+pgvector; frontend React 18/Vite/TypeScript; despliegue nativo (systemd) o Docker; Squid 6.14 como proxy gestionado |
| **Auditoría previa** | Ninguna — primera auditoría del proyecto |

---

## 1. Resumen ejecutivo

SquidManager es un panel de administración real y funcional para Squid: en esta misma sesión se verificó, con una VM limpia, que se instala desde cero (`main`) y se actualiza (`upgrade-nativo.sh` a `pruebas`) sin errores, sirviendo la configuración generada, aplicando cambios reales y externalizando correctamente listas de ACL de millones de dominios. El código está ordenado, con migraciones reversibles, sin secretos expuestos, sin CRLF rompiendo el despliegue en Linux, y con una auditoría de i18n completa a lo largo de tres idiomas. El riesgo principal hoy no es funcional sino de **proceso de verificación**: la suite de tests automatizados (211+ tests, con CI real en GitHub Actions) está **rota** — 60 de 434 tests fallan, y el propio CI de GitHub confirma `conclusion: "failure"` en el commit actual de `pruebas`. La causa es acotada y de bajo esfuerzo para corregir, pero el hecho de que nadie la haya visto (los cambios se probaron a mano contra la VM, nunca corriendo `pytest`) es la lección operativa de esta auditoría.

## 2. Veredicto

> **NO APTO**

Por regla explícita del criterio de veredicto: *"la suite no corre o falla"* implica `NO APTO` sin excepción, independientemente de que el sistema arranque correctamente (verificado) y de que la causa de la falla sea de bajo riesgo real. No se suaviza por el buen estado general del resto del proyecto.

| Severidad | Cantidad |
|---|---|
| Crítico | 0 |
| Mayor | 2 |
| Menor | 3 |
| Nota | 1 |
| Riesgo aceptado (previo) | 0 |
| Regresiones | 0 |

**Qué se verificó ejecutando** (y no solo leyendo):

- Suite de tests backend: `.venv/bin/python3 -m pytest -q` (VM, Python 3.12.3) → **374 pasados, 60 fallados**, 5.56s.
- CI real en GitHub: `GET /repos/.../actions/runs?branch=pruebas` → run #90, commit `4d06a8d`, `"conclusion":"failure"`.
- `npm audit --omit=dev` (frontend) → 0 vulnerabilidades.
- `pip-audit -r requirements.txt` (backend, VM) → 14 CVEs conocidos en `starlette 0.46.2` (transitiva de `fastapi==0.115.14`).
- Instalación limpia desde `main` (`install-nativo.sh`, sin `BRANCH`) → sin errores, panel y proxy operativos, login y cambio de contraseña obligatorio verificados.
- Upgrade real `main → pruebas` (`upgrade-nativo.sh`) → sin errores, migraciones a la cabeza (`0023`), commit servido confirmado por `/health`.
- Flujo funcional post-upgrade: carga de ACL de archivo (300 dominios) + "Aplicar cambios" → `200 OK`, Squid reconfigurado.
- Búsqueda de secretos en árbol de trabajo e historial de git → ninguno encontrado.
- CRLF en scripts `.sh` → ninguno; `.gitattributes` fuerza LF correctamente.
- Migraciones Alembic (23 archivos) → las 23 tienen `downgrade()` real, ninguna es un `pass` vacío.

**Qué no se pudo verificar**: cobertura de tests del frontend (no se detectó suite de tests de React/Vitest en el repositorio — ver hallazgo 04-002); explotabilidad real de los CVEs de `starlette` contra los endpoints propios de SquidManager (se reporta la vulnerabilidad conocida, no se intentó explotar, por política de esta auditoría).

## 3. Lo bien resuelto

- **El ciclo de vida real (instalar → actualizar) funciona de punta a punta**, verificado en una VM reinstalada desde cero en esta misma sesión, no solo leído en el script.
- **Sin secretos versionados**: `.gitignore` cubre `.env`/`.key`/`.pem`, verificado contra `git ls-files` y el historial completo.
- **Portabilidad Windows→Linux resuelta de raíz**: `.gitattributes` (`* text=auto eol=lf`, con comentario explicando el porqué) y cero archivos `.sh` con CRLF de los 12 revisados.
- **Migraciones reversibles de verdad**: 23/23 con `downgrade()` no trivial (la 0023, por ejemplo, relee archivos del disco para reconstruir el valor si hace falta revertir).
- **CI real en GitHub Actions**, matriz de dos versiones de Python, corriendo en cada push a cualquier rama — la infraestructura de calidad existe, el problema de esta auditoría es que su señal no se está mirando.
- **i18n frontend + backend auditados exhaustivamente esta sesión** (163 + 17 claves corregidas, verificadas cambiando el idioma real del panel), incluido un bug real de mensaje en inglés dentro de la clave en español.

## 4. Hallazgos

---

### 04-001 · La suite de tests está rota (60/434 fallando) — **Mayor** · Confirmado

**Dimensión**: 4 — Pruebas y verificación

**Evidencia**
```
$ .venv/bin/python3 -m pytest -q
...
60 failed, 374 passed, 9 warnings in 5.56s

tests/test_config_generator.py::test_generate_basic_config
AttributeError: '_FakeQuery' object has no attribute 'options'
  app/services/config_generator.py:51: db.query(Acl).options(defer(Acl.value))...

tests/test_acl_bulk_domains.py::test_build_acl_list_files_borra_sobrantes
AttributeError: '_FakeDBAcls' object has no attribute 'commit'
  app/services/squid_service.py:280: db.commit()
```
Confirmado también por GitHub Actions (no solo local): `GET /repos/luislopezsanchez/squid-manager/actions/runs?branch=pruebas` → run `34772664324` (#90), `head_sha: 4d06a8d...`, `"status":"completed","conclusion":"failure"`.

Desglose de las 60 fallas por causa raíz (conteo exacto de `AttributeError` agrupado):
- 57 fallas: `config_generator.generate_squid_config()` ahora usa `.options(defer(Acl.value))` (agregado en el commit `af5a234`, Fase 1 de externalización de ACLs) para no traer el contenido completo de una ACL de archivo en cada apply. Los dobles de prueba (`_FakeQuery` en `test_acl_bulk_domains.py:116`, `test_config_generator.py:84`, `test_proxy_auth_none.py:20`, `test_squid_import_service.py:211`; `_Consulta` en `test_grupos_sin_bump.py:59`; `_FakeQueryVacia` en `test_digest_auth.py:113`) simulan una consulta SQLAlchemy a mano y ninguno implementa `.options()`.
- 3 fallas: `build_acl_list_files()` (mismo commit) ahora llama `db.commit()` para persistir la migración perezosa de una ACL vieja; `_FakeDBAcls` (`test_acl_bulk_domains.py:127`) no implementa `commit()`.

**Por qué importa**: el CI existe y corre en cada push, pero lleva al menos un push (el de esta auditoría) sin que nadie mirara el resultado — la red de seguridad automatizada del proyecto está, en este momento, dando una señal roja que nadie atendió. Cualquiera que confíe en "los tests pasan" para juzgar si `pruebas` es segura de mergear a `main` está juzgando sobre información falsa.

**Recomendación**: no revertir la optimización de `config_generator.py`/`build_acl_list_files` (es correcta y ya está verificada funcionalmente en la VM real) — actualizar los dobles de prueba. Ambos cambios son mecánicos y de bajo riesgo:
1. Agregar un método `options(self, *a, **kw): return self` (no-op) a cada una de las 6 clases `_FakeQuery`/`_Consulta`/`_FakeQueryVacia` listadas arriba.
2. Agregar un método `commit(self): pass` a `_FakeDBAcls` (`test_acl_bulk_domains.py:127`).

**Esfuerzo estimado**: bajo (deberían ser ~10-15 líneas en total, sin tocar código de producción).

---

### 04-002 · Sin suite de tests para el frontend — **Menor** · Confirmado

**Dimensión**: 4 — Pruebas y verificación

**Evidencia**: `frontend/package.json` no declara `"test"` en `scripts`; no se encontró ningún archivo `*.test.tsx`/`*.spec.ts` en `frontend/src`. 39 archivos `.tsx` + 28 `.ts` sin ninguna prueba automatizada.

**Por qué importa**: toda la lógica de UI (formateo, validación de formularios, lógica de polling de progreso agregada esta sesión) depende hoy exclusivamente de verificación manual en el navegador. Es coherente con el tamaño del equipo (ver 13-001), pero es deuda real: un cambio futuro en, por ejemplo, `utils/format.ts` o `utils/chart.ts` no tiene ninguna red que lo atrape antes de llegar a un usuario.

**Recomendación**: no es urgente dado el tamaño del proyecto, pero si se agregan tests, empezar por las funciones puras sin DOM (`utils/format.ts`, `utils/chart.ts`) con Vitest, que ya es el motor de build (Vite) y no exige configuración adicional pesada.

**Esfuerzo estimado**: medio (para una primera base útil).

---

### 06-001 · Dependencia con 14 CVEs conocidos sin mitigar (`starlette` transitiva) — **Mayor** · Confirmado

**Dimensión**: 6 — Cadena de suministro y licencias

**Evidencia**
```
$ pip-audit -r requirements.txt
Found 14 known vulnerabilities in 1 package
Name      Version ID              Fix Versions
starlette 0.46.2  PYSEC-2026-161  1.0.1
...
```
`backend/requirements.txt:1` fija `fastapi==0.115.14`, que a su vez resuelve `starlette==0.46.2`. Una de las 14 (`PYSEC-2026-161` / `CVE-2026-48710`, según OSV): *"Missing Host header validation poisons request.url.path, bypassing path-based security checks... may lead to issues such as authentication bypass when authentication depends on the reconstructed URL's path."*

**Por qué importa**: no se verificó si SquidManager depende de `request.url.path` reconstruido para alguna decisión de autorización (esta auditoría no hace explotación activa), pero es una vulnerabilidad conocida y parcheada en versiones más nuevas de `starlette`, y el proyecto la sigue fijando sin actualizar.

**Recomendación**: subir el pin de `fastapi` en `backend/requirements.txt:1` a una versión que traiga una `starlette` parcheada (mínimo la línea que resuelve `PYSEC-2026-161`), correr la suite de tests después (una vez resuelto 04-001) y desplegar en la VM de pruebas antes de mergear.

**Esfuerzo estimado**: bajo a medio (depende de cuántos cambios de API rompa el salto de versión de FastAPI).

---

### 03-001 · Seis copias independientes del mismo doble de prueba — **Menor** · Confirmado

**Dimensión**: 3 — Calidad de código y mantenibilidad

**Evidencia**
```
backend/tests/test_acl_bulk_domains.py:116     class _FakeQuery:
backend/tests/test_config_generator.py:84          class _FakeQuery:
backend/tests/test_digest_auth.py:113          class _FakeQueryVacia:
backend/tests/test_grupos_sin_bump.py:59       class _Consulta:
backend/tests/test_proxy_auth_none.py:20       class _FakeQuery:
backend/tests/test_squid_import_service.py:211 class _FakeQuery:
```

**Por qué importa**: es la razón mecánica por la que un solo cambio de producción (agregar `.options()` a una consulta) rompió 7 archivos de test de forma independiente en vez de un solo punto de falla claro. Un fixture compartido en `conftest.py` habría hecho que este mismo cambio fallara en un solo lugar, más fácil de diagnosticar y corregir.

**Recomendación**: al corregir 04-001, aprovechar para extraer un `FakeQuery`/`FakeSession` común a `backend/tests/conftest.py`, con soporte de `.options()` y `.commit()` desde el origen. No es indispensable hacerlo ahora, pero cada archivo nuevo que copie el patrón actual sin este refactor perpetúa el mismo riesgo.

**Esfuerzo estimado**: medio (tocar 6 archivos de test para apuntar al fixture común).

---

### 11-001 · `.env.example` desincronizado de las variables reales — **Menor** · Confirmado

**Dimensión**: 11 — Reproducibilidad, configuración y portabilidad

**Evidencia**
```
.env real (instalación nativa):       ACCESS_TOKEN_EXPIRE_MINUTES, DATABASE_URL, SQUID_CONFIG_PATH
.env.example (raíz del repo):         TOKEN_EXPIRE, DB_NAME, DB_USER, DB_PASS, PROJECT_DIR, PROXY_PORT
```
`backend/app/config.py:35` declara `ACCESS_TOKEN_EXPIRE_MINUTES: int = 480` — la variable `TOKEN_EXPIRE` que ofrece `.env.example` no la lee ningún lado del código; quien la configure pensando que ajusta el tiempo de expiración del token no tendrá ningún efecto, sin ningún aviso.

**Por qué importa**: `.env.example` parece escrito pensando en el despliegue Docker (`DB_NAME`/`DB_USER`/`DB_PASS`/`PROJECT_DIR`/`PROXY_PORT` son variables de ese modo), mientras que la instalación nativa genera su propio `.env` con nombres distintos (`DATABASE_URL` ya armada). Es funcional porque `install-nativo.sh` no depende de `.env.example`, pero alguien que lo use como referencia para un despliegue Docker manual (sin `docker-compose.yml` de por medio) puede llevarse una sorpresa con `TOKEN_EXPIRE`.

**Recomendación**: renombrar `TOKEN_EXPIRE` a `ACCESS_TOKEN_EXPIRE_MINUTES` en `.env.example`, y agregar un comentario que aclare qué subconjunto de variables aplica a Docker y cuál a instalación nativa (o separar en dos ejemplos si diverge mucho más en el futuro).

**Esfuerzo estimado**: bajo.

---

### 09-001 · Recorrido N+1 al listar ACLs sin uso — **Menor** · Confirmado

**Dimensión**: 9 — Rendimiento y escalabilidad

**Evidencia**
```python
# backend/app/routes/acls.py — list_unused_acls
return [a.name for a in acls if not find_references(db, a.name)]

# backend/app/services/squid_names.py:119
def find_references(db, name: str) -> list[str]:
    ...
    for rule in db.query(AccessRule).all():   # línea 132: re-consulta TODAS las reglas
```

**Por qué importa**: por cada ACL, `find_references` vuelve a traer *todas* las reglas de acceso desde cero. Con la escala real de este proyecto (decenas de ACLs y reglas en un panel de administración, no miles) el costo es despreciable hoy, pero es un patrón que empeora linealmente si el catálogo de ACLs crece.

**Recomendación**: si en el futuro el catálogo de ACLs crece de forma significativa, traer `db.query(AccessRule).all()` una sola vez fuera del loop y pasarlo como parámetro a `find_references`. No es urgente a la escala actual.

**Esfuerzo estimado**: bajo.

---

### 13-N01 · Bus factor de facto 1 — **Nota**

**Dimensión**: 13 — Automatización de calidad y ciclo de vida

**Evidencia**: `git shortlog -sn --all` → `luislopezsanchez` (181) + `llopez` (44) + `Luis López Sánchez` (1) — casi con certeza la misma persona bajo distintas configuraciones de `git`, más 2 commits de `root` (probablemente automatizados). No es un hallazgo accionable, solo contexto de riesgo para quien planifique continuidad del proyecto.

---

### Dimensiones sin hallazgos

- **Dimensión 1 — Requisitos y transparencia**: sin hallazgos nuevos; auditado exhaustivamente durante esta misma sesión (i18n, documentación campo por campo) con hallazgos ya corregidos y verificados en vivo.
- **Dimensión 2 — Arquitectura**: sin hallazgos; capas backend (routes/services/models) y frontend (pages/components/api) consistentes, sin imports circulares detectados en el muestreo.
- **Dimensión 5 — Seguridad de aplicación**: sin hallazgos; bcrypt para contraseñas (`auth_service.py:28`, coste configurable), `DEBUG=False` por defecto con `/docs` deshabilitado, CORS sin comodín por defecto, sin secretos en árbol ni historial.
- **Dimensión 7 — Datos y estado**: sin hallazgos; 23/23 migraciones con `downgrade()` real, backup automático antes de cada upgrade (`upgrade-nativo.sh`, verificado en vivo esta sesión).
- **Dimensión 8 — Privacidad**: sin hallazgos de alcance para este proyecto (herramienta de administración interna, sin datos de usuarios finales más allá de IPs/dominios visitados, ya con retención acotada por rotación de logs).
- **Dimensión 10 — Resiliencia**: sin hallazgos nuevos; los timeouts de `squid -k parse`/`reconfigure` y del cliente Docker se revisaron y corrigieron en esta misma sesión (commit `1c5a8e3`), verificados con una carga real de 5.87M dominios.
- **Dimensión 12 — Operabilidad**: sin hallazgos; `journalctl -u squidmanager` da trazas legibles, `/health` expone versión y commit servido (permite saber exactamente qué corre), rotación de logs configurada por `install-nativo.sh`.
- **Dimensión 14 — Contrato e interfaz**: sin hallazgos de alcance; es un panel de administración interno, no una API pública versionada para terceros.

## 5. Gate de publicación

*(No aplica — modo `full`, no `release`.)*

## 6. Plan de acción priorizado

| # | Acción | Hallazgo | Severidad | Esfuerzo |
|---|---|---|---|---|
| 1 | Agregar `.options()`/`.commit()` no-op a los 6 dobles de prueba listados | 04-001 | Mayor | Bajo |
| 2 | Subir `fastapi` a una versión con `starlette` parcheada, re-correr la suite | 06-001 | Mayor | Bajo-Medio |
| 3 | Sincronizar `.env.example` con las variables reales | 11-001 | Menor | Bajo |
| 4 | Extraer un `FakeQuery`/`FakeSession` común a `conftest.py` | 03-001 | Menor | Medio |
| 5 | Evitar el re-query N+1 en `find_references` si el catálogo de ACLs crece | 09-001 | Menor | Bajo |

## 8. Adenda — correcciones aplicadas el mismo día (2026-09-13)

A pedido explícito del usuario, se corrigieron los dos hallazgos Mayores inmediatamente después de este informe (la auditoría diagnostica; esta corrección es una tarea aparte, ya aprobada):

- **04-001**: agregados `.options()` (no-op) a los 6 dobles de prueba y `.commit()` (no-op) a `_FakeDBAcls`. Un test (`test_acl_sni_file_tampoco_emite_el_valor_inline`) no era un doble roto sino una aserción desactualizada por el propio cambio de esta sesión (deduplicación de SNI, commit `1c5a8e3`): se corrigió para reflejar el comportamiento nuevo e intencional, y se agregó `test_acl_sin_regla_no_emite_sni` para no perder la cobertura del caso que cubría por accidente. **Resultado: 435/435 tests pasan.**
- **06-001**: `fastapi` subido a `0.136.0` y `starlette` fijado explícitamente en `1.6.0` (el rango de compatibilidad de `fastapi` por sí solo seguía permitiendo la `starlette` vulnerable). Verificado: instalación limpia de `requirements.txt`, suite completa, arranque real del servicio, login y "Aplicar cambios" reales contra la VM. `pip-audit` limpio.
- **11-001**: en vez del renombre propuesto originalmente (que habría sido incorrecto — ver nota abajo), se agregó una nota aclaratoria en `.env.example` explicando que es específico de Docker y que la instalación nativa genera su propio `.env` con nombres distintos.

**Corrección sobre el propio informe**: la recomendación original de 11-001 ("renombrar `TOKEN_EXPIRE`") estaba mal fundada — esa variable no es un cabo suelto: `docker-compose.yml:126` la traduce a `ACCESS_TOKEN_EXPIRE_MINUTES` para el contenedor del backend. Renombrarla habría roto el despliegue Docker. Se verificó esto antes de tocar el archivo y se corrigió con una aclaración, no un renombre. Queda como recordatorio de por qué esta skill exige evidencia ejecutada y no solo grep superficial antes de recomendar un cambio.

**Veredicto tras las correcciones**: sin Críticos ni Mayores abiertos. Quedan 2 Menores (04-002, 03-001) y 1 Nota — no bloquean. **Pendiente para que el veredicto sea `APTO` con la misma disciplina que exige esta auditoría**: subir estos cambios a `pruebas` y confirmar que el run de CI en GitHub Actions para ese commit muestre `conclusion: "success"` (no basta con el `pytest` local, como ya se aprendió con el hallazgo 04-001).

## 7. Notas para la próxima auditoría

- Revisar que 04-001 y 06-001 queden en estado `corregido` y que el run de CI en GitHub para el commit que los corrija muestre `conclusion: "success"` — no basta con correr `pytest` local, confirmar contra el CI real como se hizo aquí.
- No se auditó la suite de tests del backend en modo Docker (`test_install_docker.py`, `test_upgrade_docker.py` existen pero no se ejecutaron contra un despliegue Docker real en esta ronda, solo el modo nativo).
- Vale la pena, en la próxima auditoría, samplear con más profundidad la dimensión 14 (frontend) si el panel empieza a exponerse fuera de una red interna de confianza.
