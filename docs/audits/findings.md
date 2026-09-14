# Registro de hallazgos — SquidManager

Ledger acumulado entre auditorías. **Se actualiza, no se reescribe.** Es lo que evita re-reportar lo
mismo cada vez y lo que permite detectar regresiones.

**ID**: `<DIM>-<NNN>`, donde `DIM` es el número de dimensión y `NNN` un correlativo que nunca se
reutiliza (`05-003` = tercer hallazgo de seguridad de la historia del proyecto).

**Estados**
- `abierto` — vigente, cuenta para el veredicto.
- `corregido` — verificado como resuelto, con la fecha y el commit que lo corrigió. Se vuelve a
  comprobar en cada auditoría.
- `riesgo aceptado` — el usuario decidió convivir con él. No cuenta para el veredicto, pero sigue
  listado. Requiere motivo y fecha.
- `regresión` — estaba corregido y volvió a aparecer. Sube un nivel de severidad.
- `obsoleto` — dejó de aplicar porque el código o el alcance cambiaron. Con motivo.

---

## Abiertos

| ID | Sev | Dim | Título | Evidencia | Detectado | Última verificación |
|---|---|---|---|---|---|---|
| 04-002 | Menor | 4 | Sin suite de tests para el frontend | `frontend/package.json` sin script `test`; sin archivos `*.test.tsx` | 2026-09-13 | 2026-09-14 |
| 03-001 | Menor | 3 | 6 copias independientes del mismo doble de prueba (`_FakeQuery`/`_Consulta`) | Ver lista de archivos en el informe 2026-09-13-audit-full.md | 2026-09-13 | 2026-09-14 |
| 09-001 | Menor | 9 | N+1 en `find_references` al listar ACLs sin uso | `backend/app/services/squid_names.py:119`, `backend/app/routes/acls.py` (`list_unused_acls`) | 2026-09-13 | 2026-09-14 |

## Riesgos aceptados

| ID | Sev | Título | Motivo de la aceptación | Aceptado el | Revisar el |
|---|---|---|---|---|---|

(ninguno todavía)

## Corregidos

| ID | Sev | Título | Corregido el | Commit | Reverificado el |
|---|---|---|---|---|---|
| 05-005 | Mayor | `DATA_KEY` nunca llega al backend en Docker: cifrado en reposo inoperante en ese modo | 2026-09-14 | *(pendiente de push)* | 2026-09-14 — suite 421/421 + tests nuevos que fallan sin el fix |
| 10-001 | Mayor | `autoupdate-check.sh` lee `ExecMainStatus` de una unidad ya recolectada (`--collect`): fallo reportado como "ok" | 2026-09-14 | *(pendiente de push)* | 2026-09-14 — suite 421/421 + tests nuevos que fallan sin el fix |
| 08-001 | Mayor | IP pública de un servidor real en comentarios versionados (repo público) | 2026-09-14 | *(pendiente de push)* | 2026-09-14 — suite 421/421 + tests nuevos que fallan sin el fix |
| 13-001 | Menor | `tsc --noEmit` falla (1 error) y ni `build` ni CI hacen typecheck | 2026-09-14 | *(pendiente de push)* | 2026-09-14 — suite 421/421 + tests nuevos que fallan sin el fix |
| 14-001 | Menor | Mensaje 413 hardcodeado en español, fuera de i18n | 2026-09-14 | *(pendiente de push)* | 2026-09-14 — suite 421/421 + tests nuevos que fallan sin el fix |
| 11-002 | Menor | nginx nativo sin CSP ni gzip (deriva respecto de `frontend/nginx.conf`) | 2026-09-14 | *(pendiente de push)* | 2026-09-14 — suite 421/421 + tests nuevos que fallan sin el fix |
| 04-001 | Mayor | Suite de tests rota: 60/434 fallando | 2026-09-13 | `73fbc04` | 2026-09-14 — 420 passed / 3 skipped en venv limpio (Windows, Py 3.12); CI de GitHub verde en `8c317ed` |
| 06-001 | Mayor | `fastapi`/`starlette` con 14 CVEs conocidos | 2026-09-13 | `73fbc04` | 2026-09-14 — `pip-audit`: "No known vulnerabilities found" con `starlette==1.6.0` |
| 11-001 | Menor | `.env.example` sin aclarar que es específico de Docker | 2026-09-13 | `73fbc04` | 2026-09-14 — nota presente en `.env.example:7-12` |

## Obsoletos

| ID | Título | Motivo | Fecha |
|---|---|---|---|

(ninguno)

---

## Notas (no forman parte del veredicto, contexto de continuidad)

- **03-N02** — Comentarios desactualizados en el actualizador: "cada 5 min" (`install-nativo.sh:607,636`) con timer de 1 min; referencia a `docs/actualizaciones.md` inexistente (`:589`); `git config --system --add safe.directory` sin comprobar duplicados (`:370`). 2026-09-14.
- **10-N01** — `upgrade-nativo.sh` ejecuta el backup dos veces por el re-exec de `:157-162`. 2026-09-14.
- **01-N01** — Google Fonts como dependencia externa del panel (`frontend/index.html:15-19`). 2026-09-14.
- **06-N01** — `docker-socket-proxy` con permisos casi totales (`docker-compose.yml:24-33`); ya reconocido en `update_service.py:7-10`. 2026-09-14.
- **13-N01** — Bus factor de facto 1 (`git shortlog -sn --all`: prácticamente un único autor bajo
  distintas configuraciones de git). No accionable, solo contexto de riesgo de continuidad.

---

## Historial de auditorías

| Fecha | Modo | Veredicto | Crít. | May. | Men. | Informe |
|---|---|---|---|---|---|---|
| 2026-09-13 | full | NO APTO | 0 | 2 | 3 | `2026-09-13-audit-full.md` |
| 2026-09-14 | full | APTO CON RESERVAS | 0 | 3 | 6 | `2026-09-14-audit-full.md` |
| 2026-09-14 (correcciones) | — | APTO* | 0 | 0 | 3 abiertos (Menor, previos) | 05-005/10-001/08-001/13-001/14-001/11-002 corregidos el mismo día; *pendiente de verificar el flujo de actualización en la VM tras el push* |
| 2026-09-13 (correcciones) | — | APTO* | 0 | 0 | 2 abiertos (Menor) | ver 04-001/06-001/11-001 arriba — reverificado el mismo día tras corregir ambos Mayores; *pendiente de commit/push para que el CI de GitHub lo confirme también* |
