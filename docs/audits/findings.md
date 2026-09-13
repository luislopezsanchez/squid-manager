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
| 04-002 | Menor | 4 | Sin suite de tests para el frontend | `frontend/package.json` sin script `test`; sin archivos `*.test.tsx` | 2026-09-13 | 2026-09-13 |
| 03-001 | Menor | 3 | 6 copias independientes del mismo doble de prueba (`_FakeQuery`/`_Consulta`) | Ver lista de archivos en el informe 2026-09-13-audit-full.md | 2026-09-13 | 2026-09-13 |
| 09-001 | Menor | 9 | N+1 en `find_references` al listar ACLs sin uso | `backend/app/services/squid_names.py:119`, `backend/app/routes/acls.py` (`list_unused_acls`) | 2026-09-13 | 2026-09-13 |

## Riesgos aceptados

| ID | Sev | Título | Motivo de la aceptación | Aceptado el | Revisar el |
|---|---|---|---|---|---|

(ninguno todavía)

## Corregidos

| ID | Sev | Título | Corregido el | Commit | Reverificado el |
|---|---|---|---|---|---|
| 04-001 | Mayor | Suite de tests rota: 60/434 fallando | 2026-09-13 | *(pendiente de commit)* | 2026-09-13 — 435/435 pasan, verificado también con `test_acl_sin_regla_no_emite_sni` nuevo para no perder cobertura del caso que el test viejo cubría por accidente |
| 06-001 | Mayor | `fastapi`/`starlette` con 14 CVEs conocidos | 2026-09-13 | *(pendiente de commit)* | 2026-09-13 — `pip-audit` limpio, instalación desde cero de `requirements.txt` verificada, suite completa + arranque real + apply real re-verificados con las versiones nuevas |
| 11-001 | Menor | `.env.example` sin aclarar que es específico de Docker | 2026-09-13 | *(pendiente de commit)* | 2026-09-13 — corregido con una nota, no un renombre: `TOKEN_EXPIRE` no estaba muerto, lo traduce `docker-compose.yml:126`; renombrarlo habría roto el despliegue Docker |

## Obsoletos

| ID | Título | Motivo | Fecha |
|---|---|---|---|

(ninguno)

---

## Notas (no forman parte del veredicto, contexto de continuidad)

- **13-N01** — Bus factor de facto 1 (`git shortlog -sn --all`: prácticamente un único autor bajo
  distintas configuraciones de git). No accionable, solo contexto de riesgo de continuidad.

---

## Historial de auditorías

| Fecha | Modo | Veredicto | Crít. | May. | Men. | Informe |
|---|---|---|---|---|---|---|
| 2026-09-13 | full | NO APTO | 0 | 2 | 3 | `2026-09-13-audit-full.md` |
| 2026-09-13 (correcciones) | — | APTO* | 0 | 0 | 2 abiertos (Menor) | ver 04-001/06-001/11-001 arriba — reverificado el mismo día tras corregir ambos Mayores; *pendiente de commit/push para que el CI de GitHub lo confirme también* |
