# SquidManager - Bitácora del Proyecto

**Proyecto:** SquidManager - Panel de gestión web para Squid Proxy  
**Repositorio:** /opt/squid-manager (servidor de pruebas)  
**Licencia:** Freeware (uso permitido, sin modificar/redistribuir/comercializar — ver [LICENSE](../LICENSE))  
**Fecha de inicio:** 21 de Agosto, 2026

---

## Fase 1: Investigación y Diseño (COMPLETADA)

### Objetivo
Investigar la documentación de Squid y proyectos similares para diseñar la arquitectura del sistema.

### Acciones realizadas
- Mapeadas 415 directivas de Squid, identificadas las críticas para el MVP (ACLs, auth, http_access, caché, delay pools)
- Analizados 5 repositorios de referencia:
  - ckazi/squid-easy (Go) - patrón all-in-one
  - SimpleGeek/squid-config-ui (Svelte) - bypass temporal
  - 39ff/squid-db-auth-web (PHP/Laravel) - modelo de datos
  - mfaraco/squid-proxy-control (Python) - helper personalizado
  - kaelthasmanu/SquidStats (Python/Flask) - arquitectura modular completa ⭐
- Diseñada arquitectura: FastAPI + React + PostgreSQL + Squid en Docker

### Decisiones
- Stack: Python/FastAPI (backend), React/Vite (frontend), PostgreSQL (BD), Squid (proxy)
- Arquitectura desacoplada con 4 contenedores
- BD como fuente de verdad, squid.conf generado dinámicamente con Jinja2
- SDK Docker para control del contenedor Squid (reconfigure)

---

## Fase 2: MVP Backend + Squid Funcional (COMPLETADA)

### Objetivo
Levantar los contenedores y lograr que Squid funcione con autenticación básica gestionada desde la web.

### Acciones realizadas
1. Preparado servidor Ubuntu 24.04: Docker 29.7.2 + Compose v5.5.0
2. Creada estructura de directorios en /opt/squid-manager/
3. Desarrollados 50+ archivos del proyecto:
   - Backend: FastAPI con 8 modelos, 5 routers, 3 servicios, Jinja2 template
   - Frontend: React + Vite + TailwindCSS con Login, Dashboard, ProxyUsers
   - Squid: Dockerfile + entrypoint con configuración inicial
   - Docker Compose: 4 servicios (db, backend, squid, frontend)
4. Resueltos problemas:
   - Compatibilidad passlib/bcrypt (fijada bcrypt==4.2.1)
   - Paquetes squid-ldap-auth no existen en Ubuntu 24.04 (helpers incluidos en squid)
   - PID file stale en reinicios (limpieza en entrypoint)
   - Backend sin acceso a Docker (montado /var/run/docker.sock)
5. Verificado funcionamiento completo:
   - API responde en puerto 8000
   - Login JWT funciona
   - CRUD de usuarios del proxy operativo
   - Squid proxy en puerto 3128 con autenticación básica
   - Proxy enruta tráfico correctamente con credenciales válidas
   - Deniega acceso sin credenciales

### Verificación final
```bash
# Con credenciales → funciona
curl -x http://usuario:contraseña@localhost:3128 http://httpbin.org/ip
# → {"origin": "..."}

# Sin credenciales → denegado
curl -x http://localhost:3128 http://httpbin.org/ip
# → ERROR: Cache Access Denied
```

### Estado de los contenedores (en esta fase)
| Contenedor | Puerto | Estado |
|-----------|--------|--------|
| squidmgr-db | 5432 (interno) | Healthy |
| squidmgr-backend | 8000 (público en esta fase) | Running |
| squidmgr-proxy | 3128 | Running |
| squidmgr-frontend | 3000 | Running |

> Nota de la Fase 4: el puerto del backend ya no se publica al host desde la auditoría de seguridad — se accede solo por la red interna de Docker. Esta tabla refleja el estado en el momento de esta fase, no el actual.

### URLs de acceso (en esta fase)
- Panel web: http://TU_SERVIDOR:3000
- API docs: http://TU_SERVIDOR:8000/docs
- Proxy: http://TU_SERVIDOR:3128

### Credenciales (en esta fase)
En esta fase el admin y un usuario de prueba se creaban con contraseñas fijas de ejemplo. Desde la Fase 4, no hay contraseñas por defecto: se generan al azar y se exige cambiarlas en el primer acceso — ver [docs/authentication.md](authentication.md).

---

## Fase 3: ACLs, reglas, SSL Bump y LDAP (COMPLETADA)

Cubre lo registrado en el `CHANGELOG.md` bajo `0.2.0`, `0.3.0` y `0.5.0`: gestión visual de ACLs y reglas de acceso con reordenamiento, validador de sintaxis, aplicar cambios en caliente, configuración general de Squid, SSL Bump completo con bloqueo por SNI, delay pools con interfaz visual, integración LDAP con allow-list estricto, grupos de usuarios, auditoría y notificaciones. El detalle línea a línea está en el CHANGELOG; esta bitácora no repite lo que ya queda registrado ahí.

> Nota de la Fase 5: el allow-list estricto se invirtió a deny-list — los usuarios LDAP navegan apenas se sincronizan, no al revés. Ver [docs/authentication.md](authentication.md).

---

## Fase 4: Auditoría de seguridad, corrección de datos y rediseño visual (COMPLETADA)

### Objetivo
Auditar la plataforma completa contra su propio comportamiento en ejecución, corregir lo que no coincidía, y renovar la identidad visual con un logo nuevo.

### Acciones realizadas
Ver el detalle completo en `CHANGELOG.md` bajo `[0.6.0]`. En resumen:
- Auditoría de seguridad: roles, rate limiting, CORS, exposición del puerto 8000, revocación de sesión al cambiar contraseña, retirada de contraseñas fijas del código
- SSL Bump: diagnosticado y corregido el fallo de permisos que impedía generar certificados dinámicos
- Validación real de la configuración antes de aplicarla (antes se daba por válida sin comprobar nada)
- Integridad de datos: migraciones con Alembic, referencias entre ACLs/grupos/reglas, backup completo
- Rendimiento: lectura del access.log desde el final en vez de cargarlo entero
- Identidad visual: logo del calamar, paleta derivada del logo, iconos de línea propios sustituyendo a los emojis
- Auditoría de la documentación: los 13 documentos del repositorio se contrastaron contra el código real y se actualizaron (esta misma bitácora incluida)

### Verificación
Cada corrección se verificó ejecutándola contra el servidor en marcha, no solo revisando el código. El detalle de qué se probó y qué resultado dio está fuera de esta bitácora — quedó en la conversación de la sesión de auditoría, no en un documento del repositorio.

---

## Fase 5: Prueba funcional completa y primera ronda de mejoras visuales (COMPLETADA)

### Objetivo
Probar cada función de la plataforma contra el sistema en marcha, no solo revisar el código, y corregir los bugs reales que salieran a la luz — antes de tocar nada visual, a pedido explícito de que primero quedara confirmado que todo funciona como se espera.

### Acciones realizadas
Ver el detalle completo en `CHANGELOG.md` bajo `[0.7.0]`. En resumen:
- Condición de carrera en la revocación de sesión (`iat` truncado vs `password_changed_at` con microsegundos)
- Rendimiento del dashboard: de 4-8 segundos a 20-70 ms, cambiando `container.stats()` por lectura directa de cgroups
- Botones de Usuarios sin feedback visual durante una acción de varios segundos, causa real de que parecieran no funcionar
- "Forzar re-autenticación" eliminado: verificado en vivo que no lograba lo que prometía, por un límite real de HTTP Basic Auth
- LDAP invertido de allow-list estricto a deny-list, y su filtro de sincronización dejó de estar fijo a Active Directory
- Sección Usuarios unificada (local + LDAP, buscador, filtro, grupos por usuario)
- Dashboard: sparklines, tarjeta Sistema con indicadores circulares, curva de tráfico sin artefactos visuales, aciertos de caché, latencia, usuarios con más peticiones denegadas cruzado contra el estado real de la cuenta

### Verificación
Cada corrección y cada función revisada se probó contra el servidor en marcha — incluyendo, en más de un caso, reproduciendo el problema primero para confirmar la causa antes de tocar código. El detalle línea a línea de qué se probó y qué resultado dio quedó en la conversación de la sesión, no en este documento.

---

## Fase 6: Exportación NDJSON/nativa, syslog externo y auditoría de la página Auditoría (COMPLETADA)

### Objetivo
Seguir la misma disciplina de prueba en vivo aplicada en la Fase 5, esta vez sobre Registros (formatos de exportación y reenvío a un SIEM) y sobre la propia página de Auditoría.

### Acciones realizadas
Ver el detalle completo en `CHANGELOG.md` bajo `[0.8.0]`. En resumen:
- Icono de descarga sin tamaño (misma causa raíz encontrada en 3 páginas: Registros, Backup, Certificado)
- Exportación de logs en NDJSON y en formato nativo de Squid, además de CSV
- Reenvío opcional a syslog externo (UDP/TCP, RFC 3164/5424), apagado por defecto, verificado en vivo con receptores reales
- Auditoría: la página solo reconocía la mitad de las entidades y acciones reales que el backend genera, mostrando nombres técnicos en crudo; corregido el mapeo completo y las tarjetas de resumen, que antes mezclaban eventos de sesión con cambios de configuración reales

### Verificación
Icono corregido y validado contra el bundle desplegado; formatos de exportación y reenvío a syslog probados en vivo con receptores UDP/TCP reales y tráfico real del proxy; corrección de Auditoría verificada contrastando las entidades y acciones que el código realmente escribe (`grep` sobre `entity=`/`action=` en todo el backend) contra lo que el frontend reconocía.

---

## Fase 7: Auditoría integral del proyecto (COMPLETADA)

### Objetivo
Cerrar una sesión larga de trabajo (externalización de ACLs a archivo, rediseño de menú/Documentación/Panorama, auditoría completa de i18n frontend+backend, instalación limpia y upgrade real verificados de punta a punta) con una auditoría de aptitud objetiva de todo el proyecto, no solo de lo tocado en la sesión.

### Acciones realizadas
- Auditoría completa (`skill` `project-audit`, modo `full`) sobre `pruebas @ 4d06a8d` (recién fusionada con `main`, trayendo 7 commits de fixes -v0.24.1 a v0.24.7- que `pruebas` no tenía).
- Verificado ejecutando, no solo leyendo: suite de tests backend (`pytest`), estado real del CI en GitHub Actions, `pip-audit`/`npm audit`, búsqueda de secretos en árbol e historial, CRLF en scripts, reversibilidad de las 23 migraciones.
- **Hallazgo principal**: la suite de tests está rota (60/434 fallando) por dos cambios de esta misma sesión (Fase 1 de externalización de ACLs) que no se probaron contra `pytest` antes de subirse -los dobles de prueba (`_FakeQuery` y similares, duplicados en 6 archivos) no soportan `.options()` ni `.commit()`, agregados a `config_generator.py`/`squid_service.py`. Confirmado también por el propio CI de GitHub (`run #90`, `conclusion: failure`).
- Segundo hallazgo: `fastapi==0.115.14` fija una `starlette` con 14 CVEs conocidos.
- Informe completo en `docs/audits/2026-09-13-audit-full.md`, ledger de hallazgos en `docs/audits/findings.md`.

### Verificación
Cada afirmación del informe lleva su comando y su salida real (no se asumió nada): la suite se corrió en la VM real (Python 3.12.3), el estado del CI se confirmó contra la API de GitHub (no solo local), y el ciclo instalación-limpia→upgrade se había verificado en vivo inmediatamente antes de esta auditoría.

### Veredicto
**NO APTO** — por regla explícita (suite de tests fallando), independientemente de que el sistema funcione correctamente en la práctica. Sin hallazgos Críticos. Plan de acción de 5 puntos en el informe, el primero (arreglar los dobles de prueba) de esfuerzo bajo.

---

## Fase 8: Segunda auditoría integral, tras la semana de fixes del actualizador (COMPLETADA)

### Objetivo
Re-auditar `main @ 8c317ed` (v0.24.8) después de los 14 commits posteriores a la auditoría del 2026-09-13 (casi todos sobre actualizaciones automáticas, instalación nativa y `reset-admin-password.sh`), reverificar las tres correcciones de aquella auditoría y buscar errores de configuración y comportamientos inesperados antes de corregirlos.

### Acciones realizadas
- Auditoría `project-audit` modo `full` desde Windows (sin VM): suite en venv limpio (420 passed / 3 skipped), CI de GitHub verde en los 3 últimos commits, `pip-audit` y `npm audit` limpios, `tsc --noEmit` (1 error), mapa de autorización de los 23 routers, CRLF/secretos/`git ls-files`.
- 04-001, 06-001 y 11-001 reverificados como corregidos en `73fbc04`.
- **Hallazgos nuevos**: `docker-compose.yml` nunca pasa `DATA_KEY` al backend (cifrado en reposo inoperante en Docker, 05-005); `autoupdate-check.sh` lee `ExecMainStatus` de una unidad transient ya recolectada por `--collect`, así que un fallo de actualización puede reportarse como "ok" (10-001, *Probable*, pendiente de reproducir en VM); IP pública de un servidor real en 4 comentarios de scripts (08-001); typecheck del frontend roto y no ejecutado por nadie (13-001); mensaje 413 fuera de i18n (14-001); nginx nativo sin CSP/gzip (11-002).
- Informe: `docs/audits/2026-09-14-audit-full.md`; ledger actualizado en `docs/audits/findings.md`.

### Veredicto
**APTO CON RESERVAS** — 0 Críticos, 3 Mayores con reserva explícita. Contexto de continuidad: el usuario iba a describir comportamientos inesperados observados en vivo; cruzarlos primero contra 10-001 y el doble backup de `upgrade-nativo.sh` antes de buscar causas nuevas.

---

## Riesgos activos

| Riesgo | Estado |
|--------|--------|
| Docker socket montado en el backend | **Sigue abierto.** Es una decisión de arquitectura: el backend necesita controlar Squid. Contenerlo requeriría un proxy de socket restringido o un agente intermedio — ver `docs/architecture.md`. |
| SSL Bump descifra todo el HTTPS salvo lo excluido explícitamente | **Mitigado, no eliminado.** Desde la Fase 4 existe `ssl_bump_exclude` para banca, sanidad y apps con certificate pinning, pero por defecto está vacío: hay que rellenarlo a propósito. |
| ~~passlib + bcrypt 5.x incompatible~~ | **Resuelto en la Fase 4.** passlib se retiró; se usa bcrypt directamente. |
| ~~CORS abierto a `*`~~ | **Resuelto en la Fase 4.** Lista explícita de orígenes, vacía por defecto. |
| ~~Puerto 8000 del backend público~~ | **Resuelto en la Fase 4.** Ya no se publica al host. |
| Archivo htpasswd en volumen compartido | Sigue siendo el mecanismo (backend y squid montan `squid-config`), ahora con permisos `600` en vez de los por defecto. Sincronización correcta verificada de nuevo tras la auditoría. |

---

## Mejoras futuras pendientes

### Índice por tema

Las mejoras de abajo están escritas en orden cronológico (cuándo se
investigó cada una). Esta tabla las agrupa por tema y por estado, para ver
de un vistazo qué queda realmente pendiente — los enlaces apuntan a la
entrada completa más abajo.

| Estado | Tema | Mejora |
|--------|------|--------|
| ✅ Implementado | Directorio activo / autenticación | [ACLs por grupo de Active Directory / LDAP](#acls-por-grupo-de-active-directory--ldap) — verificado en vivo contra un AD real, incluida pertenencia anidada |
| ✅ Implementado | Directorio activo / autenticación | [Ajustes finos de Kerberos](#funciones-inspiradas-en-squidstats-comparación-2026-09-18) (children/startup/idle, pelar `@REALM`) |
| ✅ Implementado | Ancho de banda y cuotas | [Rediseño de control de ancho de banda, límites por tipo de archivo y cuotas de navegación](#rediseño-de-ancho-de-banda-y-cuotas-de-navegación-2026-09-18) — incluye cuotas para usuarios LDAP y aplicación en bloque, verificado en vivo con un usuario LDAP real |
| ✅ Implementado | Ancho de banda y cuotas | [Terminar una conexión activa de un cliente](#funciones-inspiradas-en-squidstats-comparación-2026-09-18) — el corte real no se pudo verificar en la VM de pruebas por falta de reglas de conntrack ahí (limitación del entorno, no del código) |
| ✅ Implementado | Reglas de acceso y contenido | [Categorización de dominios](#categorización-de-dominios-2026-09-18) (manual + importación desde HaGeZi) |
| ✅ Implementado | Monitoreo y observabilidad | [Monitoreo centralizado de varias instancias](#monitoreo-centralizado-de-varias-instancias-panel-central) — reutiliza el rol "viewer" que ya existía, sin mecanismo de autenticación nuevo |
| ✅ Implementado | Monitoreo y observabilidad | [Estadísticas de caché de Squid](#funciones-inspiradas-en-squidstats-comparación-2026-09-18) (vía Cache Manager) — ya estaba hecho de una sesión anterior, esta lista no se había actualizado |
| ✅ Implementado | Monitoreo y observabilidad | [Conexiones activas en tiempo real](#funciones-inspiradas-en-squidstats-comparación-2026-09-18) — vía `mgr:client_list`, mismo mecanismo de Cache Manager de arriba |
| ✅ Implementado | Monitoreo y observabilidad | [Nuevos KPIs de dashboard](#dashboard-nuevos-kpis-para-las-funciones-de-arriba-2026-09-18) — solo el aviso de cuotas por agotarse; caché y conexiones activas se dejaron en su propia pantalla a propósito |
| ✅ Implementado | Multi-nodo / escalabilidad | [Sincronizar configuración entre nodos](#evaluado-alcance-reducido-clustering-de-squid-para-balanceo-de-carga) — manual, a pedido, reutilizando el monitoreo centralizado; el balanceo de carga en sí sigue fuera de lo que Squid permite configurar |
| ✅ Implementado | Asistente de IA | [Agente de IA más capaz (agéntico)](#agente-de-ia-más-capaz-agéntico) — solo lectura + propuestas que el administrador confirma a mano, nunca aplica nada solo |
| ✅ Implementado | Plataforma / operaciones | [Actualizar instalaciones Docker desde el panel](#actualizar-instalaciones-docker-desde-el-propio-panel) — sin verificar en vivo por falta de un entorno Docker disponible |
| ✅ Implementado | Dashboard / rendimiento | [Rediseño responsivo del Dashboard y saneamiento del backend](#dashboard-rediseño-responsivo-y-saneamiento-del-backend-2026-09-24) — Sistema al header, límite de tasa, rutas síncronas en todo `app/routes/`, chequeo de i18n en CI, code-splitting |
| 🟡 Pendiente | Dashboard / rendimiento | Espacio libre junto a "Tráfico de red en tiempo real" (quedó vacío al sacar la tarjeta Sistema) — KPI a definir junto con las mejoras de Análisis |
| 🟡 Pendiente | Dashboard / rendimiento | Latencia (mediana/p95) y Total transferido acumulado, que mostraba la tarjeta Sistema, no tienen lugar hoy — se perdieron, no se movieron |
| 🟡 Pendiente | Plataforma / operaciones | `backend/app/routes/access_rules.py`, `admins.py`, `central.py` y `squid_config.py` ya tienen la corrección de rutas síncronas aplicada en el working tree, pero no comiteada — mezclada con trabajo pendiente de otra sesión en los mismos archivos, necesita revisión aparte antes de commitear |
| 🟡 Pendiente | Plataforma / operaciones | `/central/dashboard` (Panel Central) tiene el mismo patrón de bloqueo que se corrigió hoy en el resto de rutas — no se tocó porque no se probó en esta sesión |
| ✅ Implementado | Análisis de datos | [Top dominios por bytes e IPs compartidas](#dashboard-rediseño-responsivo-y-saneamiento-del-backend-2026-09-24) — Fase 1 de la propuesta del 2026-09-24 |
| 🟡 Pendiente | Análisis de datos | Rango de fechas libre en reportes, detección de anomalías por reglas simples — Fase 2 de la propuesta del 2026-09-24, ver más abajo |

---

### Actualizar instalaciones Docker desde el propio panel

Hoy, "actualizar desde el panel" (aprobar y aplicar sin SSH) solo existe en
instalación nativa (`update_service.py` corta la funcionalidad entera con un
guard de `DEPLOY_MODE == "native"`). En Docker, el panel solo avisa que hay
una versión nueva y le dice al admin que corra `upgrade-docker.sh` a mano.

Investigado (no implementado) el 2026-09-14: no es un ajuste chico. El
mecanismo nativo funciona porque systemd ya es un componente de confianza,
siempre presente en el host, que `install-nativo.sh` deja preparado una vez
(`squidmanager-autoupdate.timer` + una única línea de `sudo` sin argumentos
en `/etc/sudoers.d/squidmanager`) — el panel (sin privilegios) solo puede
"adelantar" cuándo corre ese mecanismo, nunca decirle qué hacer.

Docker no tiene un equivalente: `install.sh` no instala nada a nivel del
host (ni timer, ni servicio, ni sudoers), y actualizar en modo Docker
significa `docker compose up -d --build` — reconstruir la imagen y recrear
los contenedores, **incluido el propio backend que estaría ejecutando esa
orden**. Es el mismo problema de fondo que resolvió `systemd-run` en
nativo (lanzar el proceso real fuera del cgroup de quien lo lanza), pero
Docker no tiene una forma nativa de lograr eso. Además, el
`docker-socket-proxy` que ya usa el backend bloquea explícitamente el build
de imágenes, a propósito (ver `docker-compose.yml`, sección del proxy).

Lo único que ya está resuelto: el backend ya tiene montado el directorio
completo del proyecto (con `.git`), así que el acceso a los archivos y al
repositorio no es el problema — el hueco es específicamente el paso de
"reconstruirme y recrearme a mí mismo".

**Opciones evaluadas, de más a menos seguras:**

1. **Timer de systemd en el host** (instalado por `install.sh`, corre como
   root, mismo patrón que ya usa nativo) — el backend solo escribiría un
   archivo de estado, igual que ya hace hoy, sin ganar ningún permiso nuevo
   sobre Docker. La opción recomendada: reutiliza casi textual un mecanismo
   ya probado en producción.
2. **Contenedor "actualizador" dedicado**, con su propio acceso acotado,
   disparado por el backend a través de un canal angosto (un archivo de
   cola, no un socket completo). Un RCE en el backend ya no alcanza solo,
   pero exige mantener un segundo componente.
3. **Dar al backend actual un socket de Docker sin restricciones** (o
   habilitar `BUILD=1` en el proxy que ya tiene) — el cambio más simple,
   pero el más riesgoso: cualquier RCE en el backend (el componente más
   expuesto a la red) pasaría a poder reconstruir o reemplazar cualquier
   contenedor del host. Es justo lo que el proxy actual existe para evitar.

No se estimó esfuerzo de implementación todavía; queda para cuando se
decida abordarlo.

**Actualización (2026-09-19) — implementado con la opción 1 (recomendada),
sin verificación en vivo por falta de un entorno Docker disponible en
esta sesión (limitación del entorno de trabajo, no del diseño; ver el
detalle al final).**

Extiende `update_service.py` (antes rechazaba cualquier llamada fuera de
`DEPLOY_MODE=native` con un error) para que comprobar contra GitHub y
aprobar una actualización funcionen igual en Docker -son operaciones sin
privilegios, solo escriben el archivo de estado ya existente
(`.update_state.json`), que en Docker resulta estar en el mismo volumen
del proyecto que ya se monta en el mismo path dentro y fuera del
contenedor (`docker-compose.yml`): el host ya podía leerlo sin ningún
cambio. Lo único exclusivo de nativo es el "empujón" inmediato vía sudo
(`_disparar_verificacion_inmediata`) -en Docker no hay sudo hacia el host
desde dentro de un contenedor, así que aprobar "ahora" espera al próximo
tic del temporizador del host (hasta 1 minuto, contra "segundos" en
nativo).

Nuevo `docker-autoupdate-check.sh`, más simple que su equivalente nativo
a propósito: nativo necesita lanzar la actualización real en una unidad de
systemd APARTE (vía `systemd-run`) porque el propio backend corre en el
mismo host, como el mismo tipo de servicio systemd que la actualización
reinicia -si el proceso que la lanza comparte cgroup con lo que se
reinicia, se mata a sí mismo a mitad de camino-. El temporizador de
Docker no tiene ese problema: ya es un proceso del host, completamente
ajeno al ciclo de vida de los contenedores que reinicia, así que invoca
`upgrade-docker.sh` directo y en primer plano, sin necesitar una unidad
transient ni un archivo de resultado intermedio.

Instalado por `install.sh` (temporizador `squidmanager-docker-autoupdate.timer`,
cada minuto, igual cadencia que nativo) y, para que una instalación Docker
ya existente no se quede afuera hasta que alguien vuelva a correr
`install.sh` a mano, el mismo bloque de instalación (idempotente) se sumó
también a `upgrade-docker.sh`: la próxima actualización manual de
cualquier instalación existente ya deja el temporizador funcionando solo.
También se sumó `git` a la imagen del backend -sin él,
`update_service.py` no tiene forma de saber qué commit tiene desplegado
desde dentro del contenedor, y la comprobación de "hay una actualización
disponible" nunca detectaría ninguna.

**Limitación del entorno de trabajo:** esta sesión no tuvo acceso a una
instalación Docker real para probar el temporizador de punta a punta (la
VM de pruebas disponible es nativa). Se verificó lo que sí se pudo sin
ese entorno: sintaxis de los scripts de bash (`bash -n`), los 553 tests
de backend (3 nuevos, sobre el cambio de compuertas de modo en
`update_service.py`), y que la instalación nativa existente sigue
funcionando exactamente igual que antes (nada de lo tocado le cambia el
comportamiento). Queda pendiente una verificación en vivo contra una
instalación Docker real la próxima vez que haya una disponible.

### ACLs por grupo de Active Directory / LDAP

Pedido por usuarios reales del proyecto (2026-09-18): poder crear reglas de
acceso basadas en la pertenencia a un grupo del directorio (AD u otro LDAP),
no solo por usuario individual o por grupo local sincronizado.

Investigado contra la documentación oficial de Squid: es viable. Squid trae
un helper propio para esto, `ext_ldap_group_acl` (empaquetado junto con
`squid`/`squid-common`, no requiere compilar nada aparte), declarado como
`external_acl_type`. Consulta al directorio **en vivo, request por
request** — no requiere sincronizar membresías de grupo a la base de datos
propia. Sintaxis y opciones: manpage `ext_ldap_group_acl(8)`
(https://manpages.debian.org/testing/squid/ext_ldap_group_acl.8.en.html).

Encaja con lo que ya existe: la configuración LDAP (bind DN, password
cifrada, search base) ya está en el panel (**LDAP**, modelo `LdapConfig`),
y ya existe el concepto de "grupo → ACL `proxy_auth`" para grupos locales
(**Grupos de usuarios**, ver [authentication.md](authentication.md#grupos-de-usuarios)).
La pieza nueva sería un tipo de grupo adicional ("grupo de AD/LDAP") que en
vez de listar miembros propios, genera un `external_acl_type` parametrizado
con la configuración LDAP ya existente.

Limitación a tener en cuenta y ya documentada en
[configuration.md](configuration.md#configuración-de-ldap): la contraseña
de bind queda visible en la línea de comandos del helper (`ps`) mientras
corre — se mitiga usando una cuenta de bind de solo lectura, sin
privilegios de administrador de dominio (recomendación ya vigente para el
bind actual, no exclusiva de esta función nueva).

No se estimó esfuerzo de implementación todavía.

**Actualización (2026-09-19) — implementado con un helper propio en vez
de `ext_ldap_group_acl`, y verificado en vivo contra el Active Directory
real de la VM de pruebas.** Se optó por un helper Python
(`squid/ldap_group_helper.py`) en vez del binario `ext_ldap_group_acl`
sugerido originalmente: la contraseña de bind quedaría igual de expuesta
en la línea de comandos con cualquiera de los dos, pero un helper propio
reutiliza la MISMA configuración de conexión que ya lee
`auth_helper.py` (`/etc/squid/ldap_helper.conf`, escrito por el backend)
en vez de mantener una segunda copia de bind_dn/password en el
`external_acl_type` del squid.conf generado — una fuente de verdad menos
para desincronizar.

**Grupos** ganó un `source` (`local`, el único que existía, o `ldap`).
Un grupo `local` sigue igual que siempre; uno `ldap` no tiene miembros
propios — en su lugar tiene `ldap_group_name` (el nombre del grupo en el
directorio) y `ldap_group_nested` (si además de miembros directos hay
que contar grupos anidados, vía la regla de coincidencia recursiva de
Active Directory `1.2.840.113556.1.4.1941` — no funciona en OpenLDAP).
Los dos se usan igual en las reglas de acceso, como cualquier ACL.

**Bug real encontrado y corregido al probarlo en vivo:** el primer
intento generaba `acl ad_grupo external ldap_group_helper "Admins. del
dominio" direct` (nombre entre comillas, para los grupos con espacio en
el nombre) — `squid -k parse` lo rechazó con `Can not open file Admins.
for reading`. Resulta que squid.conf **no** admite comillas como forma
genérica de escapar espacios en un parámetro de ACL: para varios tipos
de ACL (confirmado para esta), un valor entre comillas se interpreta
como "leer la lista desde este archivo", no como un string literal.
Solución: el nombre del grupo se codifica `%XX` (igual que ya hace el
protocolo de Squid con los helpers para valores con espacios, ver
`auth_helper.py`) antes de escribirlo en el squid.conf generado, sin
comillas — un único token sin espacios, que el propio helper decodifica
con `unquote()` al recibirlo.

**Verificado en vivo, contra el AD real de la VM de pruebas (no
simulado):** se probó con dos grupos reales del directorio —
"Admins. del dominio" (Domain Admins) y "Grupo de replicación de
contraseña RODC denegada", que contiene al primero como miembro
anidado, sin contener directamente a ningún usuario real—:

| Usuario | Grupo | Modo | Esperado | Resultado real |
|---|---|---|---|---|
| llopez | Admins. del dominio | direct | OK (es miembro directo) | OK |
| squidmanager | Admins. del dominio | direct | ERR (no es miembro) | ERR |
| llopez | RODC denegada | direct | ERR (no es miembro directo) | ERR |
| llopez | RODC denegada | nested | OK (miembro vía "Admins. del dominio") | OK |
| squidmanager | RODC denegada | nested | ERR (no pertenece de ninguna forma) | ERR |

Las cinco combinaciones dieron el resultado esperado, probando el
helper real (`/usr/lib/squid/squidmanager_ldap_group_helper`) contra el
servidor LDAP real, no una simulación. `squid -k parse` acepta la
configuración generada sin warnings.

No implementado en esta vuelta: la excepción de SSL Bump por grupo
(`no_bump`) para grupos de LDAP — el bloque `ssl_bump` de la plantilla
usa `proxy_auth` con la lista de miembros directo, no el helper externo;
se rechaza explícitamente al crear/editar un grupo LDAP con `no_bump`
en vez de aceptarlo y no hacer nada.

516 tests de backend pasan (24 nuevos: 6 del generador de configuración,
12 del helper de grupos LDAP con conexión simulada, 6 de la validación
de la ruta).

### Monitoreo centralizado de varias instancias (panel "central")

Pedido por usuarios reales del proyecto (2026-09-18): un panel central que
vea las estadísticas de varios Squid/SquidManager como si fueran "nodos
hijos".

Investigado: Squid no tiene ningún mecanismo nativo de agregación entre
instancias (confirmado en https://wiki.squid-cache.org/Features/CacheManager/Index
— cada Squid expone su propio Cache Manager/SNMP, sin fan-in). La
agregación tendría que construirse en la capa de aplicación, no en Squid.

Encaja bien con la arquitectura actual, incluso mejor que si dependiera de
Squid: SquidManager ya no lee del Cache Manager de Squid — tiene su propio
`metrics_service.py` (parseo de `access.log` + `/proc`/cgroups) expuesto en
`/api/metrics/*`. Un "panel central" sería, en esencia, un modo/pantalla
nueva donde una instancia guarda una lista de instancias "hijas" (URL +
token de acceso) y sondea periódicamente el `/api/metrics/dashboard` ya
existente de cada una, agregando resultados — sin tocar Squid ni requerir
que los Squids se conozcan entre sí.

Pendiente de definir: cómo se autentica el panel central contra cada hijo
(¿token de servicio nuevo, distinto del JWT de un admin humano?), y qué pasa
si un hijo no responde (timeout, nodo marcado como "no disponible" sin
tumbar el resto del dashboard).

**Actualización (2026-09-19) — implementado y verificado en vivo.**

La duda de autenticación se resolvió sin inventar un mecanismo nuevo:
SquidManager **ya tenía** un rol "viewer" (solo lectura, ver `Admin.role` y
`require_writer` en `auth_service.py`) que nunca se usaba desde ningún lado
del código todavía. El panel central se autentica contra cada nodo con el
login normal (`POST /api/auth/login`) usando una cuenta -recomendada,
`viewer`- ya existente en ese nodo, y con el JWT que le devuelve pide su
`GET /api/metrics/dashboard`, también ya existente. Cero mecanismos nuevos
en el nodo remoto: cualquier instancia de SquidManager ya sabe ser "nodo
hijo" de otra sin ningún cambio, con solo crearle una cuenta de solo
lectura.

Tabla nueva `monitored_nodes` (migración 0032): nombre, URL, usuario y
contraseña -cifrada en reposo con `EncryptedString`, igual que las otras
siete credenciales de terceros que ya cifra el proyecto (LDAP, SMTP,
Kerberos, etc.; ver `crypto_service.py`). Como con la contraseña de bind de
LDAP, no viaja en los backups -un restore la deja en blanco y el nodo
deshabilitado, con una advertencia para volver a cargarla a mano.

Rutas nuevas bajo `/api/central/`: `GET/POST /nodes`, `PUT/DELETE
/nodes/{id}`, `POST /test` (prueba credenciales antes de guardar, igual que
`POST /api/ldap/test`), y `GET /dashboard` (el dashboard de este servidor
+ el de cada nodo habilitado, en una sola llamada). Cada nodo se consulta
con `httpx` síncrono de forma secuencial (mismo estilo que el resto del
proyecto para llamadas salientes, ver `ai_service.py`) con un timeout
corto (6s): un nodo caído no cuelga la vista más que unos segundos, y
nunca tumba a los demás -cualquier fallo (timeout, credenciales
rechazadas, no es un SquidManager) se devuelve como parte del resultado
en vez de propagarse.

Página nueva "Panel central" (grupo de menú "Monitoreo centralizado",
anotado como hueco pendiente desde la reorganización del menú del
2026-09-09): tarjetas con el estado de cada nodo (tráfico actual, usuarios
activos, CPU, memoria, o el motivo si está caído) que se refrescan solas
cada 30s -mucho más espaciado que el dashboard local (5s), porque cada
ciclo implica un login real contra cada nodo, no solo leer el propio
proceso- más la gestión de altas/bajas de nodos.

**Verificado en vivo contra la VM de pruebas** (sin una segunda instancia
de SquidManager disponible, se armó un nodo que apunta a sí misma -mismo
mecanismo, origen y destino son la misma instancia solo para la prueba):
creada una cuenta `viewer` real y un nodo real apuntando a
`http://127.0.0.1:3000` (el puerto real donde escucha nginx en instalación
nativa -primer intento fallido con el puerto 80, que en esta VM sirve el
sitio nginx "default" de Debian, no el panel: encontrado y corregido en el
momento). Con eso: login exitoso, `GET /api/central/dashboard` devolvió
"Este servidor" + el nodo de prueba con datos reales (tráfico, CPU,
memoria) en la misma respuesta, `GET /api/central/nodes` enmascaró la
contraseña como `***`, y probar con una contraseña incorrecta devolvió el
error esperado sin lanzar ninguna excepción. 537 tests de backend pasan
(16 nuevos: login/dashboard simulados con httpx, y validación de URL/
enmascarado de contraseña).

No se estimó esfuerzo de implementación todavía.

### Evaluado y descartado: SSL Bump con certificado público (Let's Encrypt)

Pedido por usuarios reales del proyecto (2026-09-18): usar un certificado
"válido" (Let's Encrypt) en vez de la CA autofirmada para SSL Bump, para
evitar tener que instalar la CA en cada equipo cliente.

**No es viable, y no es una limitación de SquidManager que se pueda resolver
a futuro.** SSL Bump exige que Squid tenga la clave privada de la CA con la
que firma, al vuelo, cada certificado dinámico por dominio — ninguna CA
pública entrega su clave privada a un tercero para eso, y el CPS de Let's
Encrypt (sección 1.4.2, https://letsencrypt.org/documents/isrg-cps-v2.6/)
prohíbe explícitamente usar sus certificados para interceptar comunicaciones
cifradas (MITM). Detalle completo y por qué, documentado para los usuarios
en [ssl-bump.md](ssl-bump.md#se-puede-usar-un-certificado-público-lets-encrypt-en-vez-de-la-ca-autofirmada).

Sí se mantiene como válida la sugerencia, ya documentada, de usar Let's
Encrypt para el certificado HTTPS del propio panel web (no tiene relación
con SSL Bump).

### Evaluado, alcance reducido: clustering de Squid para balanceo de carga

Pedido por usuarios reales del proyecto (2026-09-18): instalaciones de Squid
en clúster para balanceo de carga.

Squid no tiene un modo nativo de clustering activo-activo con estado
compartido (confirmado en https://wiki.squid-cache.org/Features/LoadBalance
y https://wiki.squid-cache.org/Features/SmpScale): `cache_peer` con
CARP/round-robin balancea la salida hacia varios padres, no la entrada de
clientes; `workers` (SMP) escala en una sola máquina, no entre servidores.
No hay ninguna directiva de "cluster" de Squid que el panel pueda exponer.

Si se retoma, el alcance realista no es "balanceo de carga" sino, como
mucho, una guía de despliegue detrás de un balanceador externo (HAProxy,
keepalived+VRRP) con Squids idénticos, más quizás a futuro una función de
sincronizar configuración (ACLs/reglas/usuarios) entre varias instancias —
dejando claro que el balanceo en sí queda fuera de lo que Squid permite
configurar. Aviso importante para documentar si se implementa: con
Kerberos/Negotiate y NTLM, un balanceador round-robin puro rompe la
negociación por falta de afinidad de sesión — hace falta afinidad por IP de
cliente como mínimo.

**Actualización (2026-09-18):** la parte de guía de despliegue ya está
escrita — ver [balanceo-de-carga.md](balanceo-de-carga.md), con ejemplo de
HAProxy, la afinidad de sesión explicada y cómo usar el backup/restore JSON
ya existente para mantener ACLs/reglas iguales entre nodos (manual, no
automático). Queda pendiente, si se retoma, automatizar esa sincronización.

No se estimó esfuerzo de implementación de la sincronización automática.

**Actualización (2026-09-19) — la sincronización se implementó, deliberadamente
manual y a pedido, no automática/programada.** Aprovecha directamente la
tabla `monitored_nodes` que ya trae el monitoreo centralizado (mismo
mecanismo de login contra el nodo remoto): `POST
/api/central/nodes/{id}/sync` arma el mismo JSON que ya arma `GET
/api/backup/export` (se extrajo `build_backup_dict()` de esa ruta para
reusarlo) y lo manda directo al `POST /api/backup/restore` del nodo remoto,
sin archivo intermedio.

Se descartó a propósito una sincronización automática/programada: empujar
cambios de configuración solos, en segundo plano, a instancias remotas de
producción sin que un admin lo dispare a mano es un perfil de riesgo
distinto (y mayor) al de todo lo demás en este proyecto, donde nada se
aplica sin una acción explícita ("Aplicar cambios" incluido). La cuenta
guardada para un nodo de solo monitoreo (rol `viewer`, la recomendada) no
alcanza para sincronizar -se rechaza con un mensaje claro-, así que
sincronizar de verdad exige guardarle al nodo una cuenta con permisos de
escritura, una decisión aparte y explícita del administrador.

Verificado en vivo contra la VM de pruebas (nodo apuntando a sí misma, dos
cuentas de prueba: una `viewer` y una con permisos de escritura): la cuenta
`viewer` fue rechazada con el mensaje esperado; la cuenta con permisos
sincronizó de verdad -18 ajustes, 18 ACLs, 2 reglas, 2 delay pools, 2
grupos y 6 usuarios LDAP restaurados, con las advertencias esperadas sobre
las ACLs de archivo (su contenido no viaja en el backup, hay que
recargarlas aparte). 5 tests nuevos de backend sobre
`sincronizar_configuracion()` (éxito, login rechazado, sin permisos de
escritura, error genérico, respuesta no JSON).

### Huella de autoría en el código fuente (2026-09-18)

Pedido por el autor del proyecto: algún medio para poder identificar copias
o reusos no autorizados del código, coherente con la licencia Freeware
vigente (sin permiso para modificar/redistribuir).

Implementado: una huella no funcional (no altera ningún comportamiento,
verificado con typecheck/build antes y después) repetida en más de un punto
del código, de forma redundante. Se descartó a propósito cualquier mecanismo
de aviso por red ("phone home") — inaceptable en un producto de seguridad
que administra tráfico ajeno; ver la discusión completa de por qué en la
conversación del 2026-09-18.

El detalle de qué es y dónde está **a propósito no se documenta acá** — este
archivo es parte del propio repositorio público, y describirlo aquí
anularía su función. Queda registrado con el autor por fuera de este
documento.

### Funciones inspiradas en SquidStats (comparación, 2026-09-18)

A pedido del autor, se comparó SquidManager contra
[SquidStats](https://github.com/kaelthasmanu/SquidStats) (analizado también
en la Fase 1, como referencia de arquitectura). No se copió código — se
identificaron funciones de concepto que SquidManager no tiene, verificando
cada una contra el código propio antes de anotarla.

Dato de fondo que explica varios de los puntos: SquidStats se apoya en el
**Cache Manager de Squid** (`mgr:info`, conexiones activas, stats de caché);
SquidManager hoy **nunca lo consulta** — todas sus métricas salen de
parsear `access.log` y `/proc`/cgroups.

#### Ajustes finos de Kerberos (children/startup/idle, quitar `@REALM` del log)

Verificado en `backend/app/templates/squid.conf.j2:43`: `auth_param
negotiate children 10` está fijo en la plantilla, sin exponer `startup`/
`idle` en el panel, y no hay opción de "pelar" el `@REALM` del nombre de
usuario que llega a logs (relevante si a futuro hay cuotas por usuario, ver
más abajo). Ajuste chico a la pantalla de Kerberos ya existente, no una
función nueva. No se estimó esfuerzo.

**Actualización (2026-09-18) — implementado.** `children`/`startup`/`idle`
expuestos en la pantalla de Kerberos, y opción para pelar el `@REALM` del
nombre de usuario antes de que llegue al log (commit
`ed76bdc`, ver [kerberos.md](kerberos.md)).

#### Estadísticas de caché de Squid (vía Cache Manager)

Entradas almacenadas, capacidad usada/libre, tamaño de disco/inodos,
antigüedad de objetos cacheados — información que Squid ya calcula solo,
expuesta por su Cache Manager (`mgr:storedir` y similares), nunca leída hoy
por SquidManager. Requiere habilitar acceso local al manager en
`squid.conf` (`acl manager`, `http_access allow localhost manager`) y un
servicio nuevo en el backend que lo consulte y lo muestre en el dashboard.
Aditivo, no toca las métricas actuales basadas en logs. No se estimó
esfuerzo.

**Actualización — ya estaba implementado antes de esta entrada** (commit
`d6b87f8`, "estadisticas de cache (Cache Manager de Squid)"): esta lista de
pendientes simplemente nunca se había actualizado para reflejarlo. La
integración con el Cache Manager ya existe (`GET
/squid-internal-mgr/<reporte>` sobre el propio puerto de Squid, ver
`ProxyRuntime.cache_manager_report()`), con `mgr:info` y `mgr:storedir`
parseados en `cache_manager_service.py` y mostrados en Reportes → Estado
del caché. Este hallazgo (2026-09-19) es justo lo que hizo mucho más barato
el punto siguiente.

#### Conexiones activas en tiempo real

Bytes leídos/escritos de una conexión **mientras sigue abierta**, no solo
al cerrarse — estructuralmente imposible de obtener parseando `access.log`
(esa línea recién se escribe cuando la conexión termina). Depende de la
misma integración con Cache Manager del punto anterior. No se estimó
esfuerzo.

**Actualización (2026-09-19) — implementado, y mucho más barato de lo
estimado gracias al hallazgo de arriba: la integración con Cache Manager
ya existía.** Solo hizo falta sumar `client_list` a la lista de reportes
permitidos (`REPORTES_PERMITIDOS` en `cache_manager_service.py`) y un
parser nuevo -mismo patrón que `mgr:info`/`mgr:storedir`, cada campo con su
propio regex, tolerante a que un reporte puntual falle sin tumbar el
resto-. `mgr:client_list` da la cuenta de conexiones **ya establecidas en
este instante** por cliente (dirección, nombre si lo resuelve, conexiones
activas, peticiones HTTP/ICP) directo de la memoria de Squid, no de logs.

Nuevo `GET /api/cache-manager/active-connections`, con una tabla nueva
("Conexiones activas ahora") en la misma pantalla de Estado del caché.
Verificado en vivo contra la VM de pruebas: `curl
http://127.0.0.1:3128/squid-internal-mgr/client_list` devolvió datos reales
de dos clientes (localhost y un cliente real con 126 peticiones HTTP), y el
parser los interpretó correctamente. 10 tests de backend pasan sobre el
parser (con el texto real capturado en esa prueba como fixture).

#### Terminar una conexión activa de un cliente

`conntrack -D -s IP` en Linux (paquete `conntrack` + reglas de `iptables`
para que trackee el puerto del proxy), `pfctl -k IP` en BSD/macOS —
verificado en el propio README de SquidStats, con una advertencia
explícita a replicar: en Docker o detrás de NAT hay que ejecutarlo en el
host que sostiene el estado real de la conexión, si no, no corta nada.
Encaja con el adaptador de runtime que ya existe en
`backend/app/services/runtime/` (mismo patrón que ya distingue nativo vs
Docker para reconfigure/restart) — sería una operación más de ese
adaptador. No se estimó esfuerzo.

**Actualización (2026-09-19) — implementado, con una limitación real
encontrada al probarlo en vivo que conviene tener presente.** Nueva
operación `disconnect_client(ip)` en el adaptador de runtime:

- **Nativo**: `conntrack -D -s <ip>` con sudo (nueva línea de sudoers,
  sin comodines salvo esta —la IP es por naturaleza un argumento
  variable—, y el paquete `conntrack` sumado a `install-nativo.sh`).
  Devuelve éxito tanto si cortó algo como si no había ninguna conexión
  que coincidiera (exit 1 de `conntrack -D`): no es un error, solo
  significa que ya no había nada que cortar.
- **Docker**: **no implementado a propósito**, no por falta de tiempo —
  la imagen de Squid no trae `conntrack` instalado, y aunque lo trajera,
  el contenedor no corre con la capacidad `NET_ADMIN` que hace falta
  para que `conntrack -D` borre de verdad una entrada. Sumar esa
  capacidad es una decisión de seguridad del despliegue que no
  corresponde activar en silencio desde acá. El endpoint (`POST
  /api/network/disconnect`) devuelve un mensaje explicando esto en vez
  de fingir que funciona.

Endpoint nuevo y botón "Terminar conexión" en el visor de logs en vivo,
junto a la IP de cada entrada — no depende de la vista de "conexiones
activas en tiempo real" (esa sigue sin implementarse, es una mejora
aparte) porque ya alcanza con las IPs que el propio log muestra.

**Encontrado al probarlo en vivo contra la VM de pruebas (que resultó
ser un contenedor LXC de Proxmox, no una VM completa —confirmado con
`systemd-detect-virt` → `lxc`):** con una descarga real en curso a
través del proxy, `conntrack -L` mostraba **cero conexiones registradas**
(`nf_conntrack_count = 0`) a pesar de que el módulo `nf_conntrack` está
cargado — el motivo es que no hay ninguna regla de `iptables`/`nftables`
en esa máquina que dispare el tracking (las tres cadenas están vacías,
política ACCEPT sin reglas), algo común en una instalación mínima sin
firewall propio, y que puede agravarse dentro de un contenedor LXC según
qué tan privilegiado esté respecto al netfilter del host. No se pudo
verificar en vivo el corte real de una conexión por esto — sí se verificó
que el comando se arma bien, que el sudoers/paquete quedan instalados, y
que el manejo de "no había nada que cortar" no se confunde con un error
real. **Queda como nota para soporte:** si un admin reporta que "terminar
conexión" no corta nada, lo primero a revisar es `sysctl
net.netfilter.nf_conntrack_count` y si hay algo (aunque sea una regla
trivial) enganchando conntrack en esa máquina — sin eso, ni esta función
ni cualquier otra herramienta basada en `conntrack` va a poder hacer nada,
independientemente de SquidManager.

489 tests de backend pasan (5 nuevos: comando exacto que arma el modo
nativo, manejo de "sin conexión que coincida", ausencia del binario, y
que Docker devuelve la limitación en vez de intentarlo).

#### Cuotas por volumen total (no solo velocidad)

**Fusionada con el pedido más detallado del autor (2026-09-18)** — ver la
entrada consolidada
["Rediseño de ancho de banda y cuotas de navegación"](#rediseño-de-ancho-de-banda-y-cuotas-de-navegación-2026-09-18)
más abajo, que incluye periodos (diario/semanal/mensual) y la acción a
tomar al agotarse la cuota. Se deja este párrafo como referencia histórica
de por dónde arrancó la idea (reutilizar la función de deshabilitar usuario
que ya existe).

#### Descartado explícitamente (no copiar de SquidStats)

- **Notificaciones por sesión personal de Telegram (API de usuario, no
  bot)** — SquidManager solo usa bot token (`notification_service.py`), más
  seguro: una sesión personal filtrada compromete la cuenta de Telegram
  entera, un bot token filtrado solo ese canal de notificaciones.
- **Soporte multi-base de datos (SQLite/MariaDB/MySQL/Postgres)** — ya hay
  un compromiso con Postgres por `pgvector` (asistente de IA); sumar esto
  sería mucho esfuerzo por poco beneficio real.
- **Reenvío de logs remotos por syslog para centralizar** — tiene sentido
  en SquidStats porque no asume una app por nodo. El plan ya anotado arriba
  de "monitoreo centralizado" (sondear la API de cada instancia
  SquidManager) es un diseño más seguro: reusa la autenticación y
  auditoría que ya existen, en vez de abrir el Cache Manager a una IP
  externa sin control propio.

### Agente de IA más capaz (agéntico)

Pedido por el autor del proyecto (2026-09-18): el asistente de IA actual
solo hace RAG (búsqueda semántica) sobre `README.md`/`docs/*.md`, y necesita
dos API keys separadas (un proveedor de chat + Jina AI, obligatorio, para
embeddings). Se pidió evaluar subir el nivel: un agente que pueda leer
código fuente/configuración real y, más adelante, proponer o aplicar
cambios de configuración si el admin se lo pide — usando modelos cloud,
idealmente con nivel gratuito (se pensó en OpenRouter).

**Investigado contra la documentación oficial de OpenRouter:**

- **Tool calling (que el modelo ejecute acciones, no solo responda texto):**
  soportado y estandarizado (formato compatible con OpenAI) en toda la API
  de OpenRouter. Gemini y Groq — que SquidManager ya usa hoy para el
  asistente — **también lo soportan**, así que no depende exclusivamente de
  sumar OpenRouter como proveedor nuevo.
- **Modelos gratuitos:** sufijo `:free`. Límite real: 20 peticiones/min y
  50/día sin haber cargado nunca crédito (sube a 1000/día, no de golpe
  /min, si alguna vez se cargó ≥$10). Para un flujo agéntico que hace varias
  idas y vueltas de "herramienta" por pregunta, 50/día se consume rápido.
- **Confiabilidad del tool-calling gratuito:** no uniforme entre modelos —
  OpenRouter publica una métrica pública de "Tool Call Error Rate" por
  modelo, lo que confirma que hay que revisar modelo por modelo antes de
  confiarle una acción estructurada, no asumir que cualquiera gratuito
  sirve igual.
- **Embeddings:** OpenRouter ya expone `/embeddings` (dato nuevo, no lo
  tenía cuando se evaluaron proveedores originalmente), pero no se encontró
  ningún modelo de embeddings gratuito — no resolvería lo de "una sola key
  gratis", solo consolidaría a costo.

**Diseño de seguridad recomendado, no negociable si se implementa:** el
backend ya tiene la infraestructura para hacer esto sin inventar nada
nuevo — cada endpoint que modifica algo ya pasa por `require_writer`
(permisos) y queda en el log de auditoría, y aplicar cambios ya corre
`squid -k parse` antes de tocar el Squid real (`squid_service.py`). El
agente **nunca** debe tener acceso a shell/archivos crudos: sus
"herramientas" deben ser llamadas a esos mismos endpoints ya validados, y
cualquier acción que modifique algo debe requerir confirmación explícita
del admin (mostrar qué va a cambiar, no ejecutarlo solo) antes de
aplicarse — esto además mitiga que un modelo gratuito alucine una llamada
mal armada.

**Alcance sugerido, en dos fases separadas:**
1. Solo diagnóstico (leer código/config para explicar "por qué no
   funciona X") — no escribe nada, riesgo bajo.
2. Modificar configuración — el de mayor riesgo de todo lo anotado en esta
   bitácora; no empezar hasta tener sólida y probada la fase 1.

No se estimó esfuerzo de implementación todavía.

**Actualización (2026-09-20) — implementado, con alcance decidido por el
autor tras una pregunta directa antes de empezar a programar** (el único
punto de esta tanda de mejoras donde hizo falta parar a preguntar: qué
datos reales puede ver un proveedor de IA externo es una decisión de
privacidad/cumplimiento, no una de ingeniería). El autor pidió: responder
preguntas sobre SquidManager, revisar configuraciones reales en busca de
errores, poder "hacer configuraciones" pero **nunca tocar el código
fuente**, y no responder nada fuera de tema.

Diseño resultante -fase 1 y el arranque de fase 2, fusionadas, pero con la
fase 2 reducida a "proponer, nunca ejecutar":

- **Lectura**, ejecutada al toque (`app/services/ai_tools.py`):
  `listar_acls`, `listar_reglas_acceso`, `listar_grupos`,
  `ver_ajustes_squid`, `ver_estado_aplicacion`, `buscar_documentacion`
  (reusa la búsqueda semántica que ya existía). Deliberadamente
  estructurales -nombres, tipos, cantidades- y **nunca** nombres de
  usuario, dominios visitados, ni contenido de logs: quién navegó qué no
  es del asistente, y una ACL de archivo nunca expone su contenido (puede
  tener millones de líneas), solo cuántas tiene.
- **Propuesta**, nunca ejecutada (`proponer_crear_acl`, por ahora la única):
  `ejecutar_herramienta()` la intercepta ANTES de tocar la base y devuelve
  la propuesta tal cual. El modelo no tiene, en ningún punto del código, un
  camino hacia una escritura real -ni siquiera indirecto-. Quien aplica de
  verdad es el administrador, a mano, con el mismo botón "Crear" que ya
  existía en la página de ACLs (el frontend arma la propuesta como una
  tarjeta con "Aplicar"/"Descartar"; "Aplicar" llama al mismo
  `api.createAcl()` de siempre, con la validación y el registro de
  auditoría de siempre). Así se cumple "nunca tocar el código fuente" de
  la forma más literal posible: el agente no tiene ninguna vía de escritura
  propia, ni falsa ni real.
- **Tool-calling implementado para Gemini y para el formato OpenAI-compatible**
  (Groq, NVIDIA NIM) -los dos formatos que la investigación previa había
  confirmado contra la documentación oficial de cada proveedor. Ollama
  Cloud queda fuera del modo agéntico (no confirmado) pero sigue
  funcionando igual que siempre en modo solo-documentación; se rechaza
  explícitamente combinarlo con el modo agéntico, tanto al guardar la
  configuración como al preguntar.
- Bucle acotado a 4 iteraciones (`_MAX_ITERACIONES_AGENTE`): un modelo
  gratuito que no termine de decidir nunca deja la conversación colgada
  indefinidamente.
- Interruptor nuevo (`AiConfig.agentic_enabled`, migración 0033), apagado
  por defecto: activarlo es una decisión explícita del administrador,
  informada en la propia UI de que estos datos reales salen hacia el
  proveedor de IA configurado, no solo la documentación como hasta ahora.

**Verificado en vivo contra la VM de pruebas:** las 6 herramientas de
lectura devuelven datos reales de la base (ACLs, reglas, grupos, ajustes,
estado de aplicación); `proponer_crear_acl` confirmado que NO crea nada
-se probó pidiéndole crear una ACL de prueba y verificando después, contra
la base real, que no existe-; y el rechazo de Ollama Cloud + modo agéntico
funciona tanto al guardar como al preguntar. **No se pudo verificar el
diálogo de punta a punta con un proveedor de IA real** -esta VM no tiene
ninguna API key de Gemini/Groq/NVIDIA configurada, y no correspondía pedir
o usar una sin que el autor lo pidiera-; el bucle de tool-calling en sí
(cuántas rondas, qué se le pasa al modelo en cada formato, cómo se
interpreta una respuesta con herramientas vs. con texto final) se probó
con las respuestas de los proveedores simuladas, no en vivo. 568 tests de
backend pasan (15 nuevos: herramientas de `ai_tools.py`, y el bucle
agéntico contra Gemini y contra el formato OpenAI-compatible).

### Rediseño de ancho de banda y cuotas de navegación (2026-09-18)

Pedido por el autor del proyecto, en tres partes que están relacionadas
entre sí y conviene encarar juntas:

1. Rediseñar Delay Pools para crear una regla de ancho de banda de forma
   simple, para cualquier tipo de objeto (grupo, usuario, tipo de tráfico,
   dominio, etc.).
2. Límites de velocidad para descargas grandes y/o para extensiones de
   archivo específicas.
3. Cuotas de navegación (diaria/semanal/mensual), con una acción
   configurable al agotarse: cortar la navegación hasta el próximo
   periodo, o dejar seguir navegando a velocidad limitada.

#### Punto 1 y 2 son, en el fondo, la misma mejora

Verificado en el código actual (`backend/app/models/delay_pool.py`,
`app/routes/delay_pools.py`, `frontend/src/pages/DelayPools.tsx`): hoy un
delay pool es **clase de Squid (1-5) + parámetros + una sola ACL** elegida
de un desplegable, con la ACL ya creada de antemano en la página de ACLs.
Para usarlo hay que saber de memoria qué clase de Squid corresponde a qué
caso (clase 4 para limitar por usuario, por ejemplo) — no es intuitivo.

La buena noticia: **Squid ya soporta aplicar un delay pool a cualquier tipo
de ACL** (`proxy_auth` para usuario, un grupo, `dstdomain`/`dstdom_regex`
para dominio —incluidas las categorías del punto siguiente—, `url_regex` o
`req_mime_type` para tipo/extensión de archivo, o combinaciones vía
`delay_access` encadenado). No hace falta nada nuevo de Squid — es una
generalización de la interfaz y del modelo de datos de SquidManager: un
asistente que primero pregunte **"¿a qué se aplica este límite?"**
(usuario / grupo / dominio / categoría / tipo de archivo / todo el
tráfico) y arme la clase y la ACL correctas por detrás, en vez de exigir
que el admin conozca la taxonomía de clases de Squid de antemano.

**Matiz honesto sobre "descargas grandes":** Squid no puede reclasificar
una descarga a mitad de camino según cuán pesada termine siendo — el
delay pool se aplica desde que arranca la conexión, no cuando se descubre
que "es grande". El propio mecanismo de balde de fichas ya castiga más a
las transferencias sostenidas que a las cortas (efecto colateral que ya
existe), pero limitar específicamente "archivos de más de X MB" detectados
por adelantado no es algo que los delay pools puedan hacer de forma
nativa — sí es completamente viable limitar por **extensión** (`url_regex`)
o por **tipo de contenido** (`req_mime_type`), que es lo que sí pidió el
punto 2 explícitamente.

Riesgo: medio (toca el generador de `squid.conf` y el modelo de datos de
delay pools, pero de forma aditiva — los pools existentes con una sola ACL
siguen funcionando igual).

**Actualización (2026-09-18) — implementado, probado en vivo con tráfico
real, y verificado contra la documentación oficial de Squid tras una duda
del autor.** Se reemplazó el formulario original (elegir a mano la clase
1-5 de Squid) por un asistente de una sola pantalla: "¿A qué se aplica
este límite?" con una lista ya resuelta (usuarios, grupos, dominios y
categorías, tipos de archivo), una sola velocidad (sin distinguir
restauración de límite, salvo en un "editor técnico" aparte para
combinaciones que ese modelo simple no cubre). Para "tipo de archivo" se
puede crear la lista de extensiones sin salir del formulario.

Verificado en vivo contra la VM de pruebas, descargando de verdad a
través del proxy (no solo `squid -k parse`): con una regla de 50 KB/s,
las cinco variantes (todo el tráfico, usuario específico, dominio, tipo
de archivo, grupo) bajaron la velocidad medida de ~1930 KB/s a ~50-55
KB/s, y en cada caso el tráfico que NO calzaba con la regla (otro
usuario, otro dominio, otra extensión) siguió sin límite — confirma que
el aislamiento por ACL funciona como se espera.

**Duda del autor, resuelta contra la documentación oficial:** ¿por qué
"cada integrante su propio límite" en un grupo termina siendo un límite
por IP/equipo y no por usuario autenticado, si otras plataformas basadas
en Squid sí logran esto? Investigado a fondo:

- Squid sí documenta una clase pensada exactamente para esto —
  [`delay_class`](https://www.squid-cache.org/Doc/config/delay_class/)
  clase 4, "cada usuario limitado a un ancho de banda sin importar en
  cuántos equipos esté logueado". Se probó en vivo (clase 4, con el nivel
  "usuario" en 50 KB/s y el resto en un valor gigante para no
  restringir) — **la conexión se cuelga por completo (0 bytes hasta que
  expira el timeout)**, repetido dos veces, incluida una prueba forzando
  IPv4 puro (la doc oficial aclara que las clases 2-4 solo valen para
  IPv4, clases 1 y 5 sí sirven con IPv6 — se descartó como causa).
- Encontrado un defecto real y **todavía sin corregir** en el propio
  rastreador de Squid: [Launchpad
  #2018472](https://bugs.launchpad.net/bugs/2018472) ("squid crash basic
  auth used delay_pools"), abierto desde 2023 contra Squid 5.2+, que
  apunta a `DelayId::DelayClient()` accediendo a un puntero nulo al
  intentar resolver el usuario autenticado para un delay pool con auth
  Basic — exactamente la combinación que usa SquidManager
  (`proxy_auth_scheme=basic`). Explica de forma consistente lo observado:
  no es un error de configuración de SquidManager, es un defecto de
  Squid en el camino código que resuelve "qué bucket le toca a este
  usuario autenticado".
- Conclusión práctica, ya reflejada en la interfaz: la casilla de "cada
  integrante su propio límite" usa la clase 2 (probada, estable,
  confirmada en vivo con descargas concurrentes), aclarando en el texto
  que el límite es por IP/equipo, no por nombre de usuario — es honesto
  sobre una limitación real de Squid, no un defecto de SquidManager. No
  se activa la clase 4 hasta que ese defecto de Squid se corrija río
  arriba.

**Segunda duda resuelta — HTTPS con SSL Bump:** se encontró en la
documentación un reporte de que "los delay pools no limitan HTTPS"
([Debian #946049](https://bugs.debian.org/cgi-bin/bugreport.cgi?bug=946049)),
lo que hubiera sido grave (casi todo el tráfico real es HTTPS). Verificado
en vivo: el reporte es específicamente sobre HTTPS **sin** SSL Bump (un
túnel `CONNECT` opaco que Squid nunca puede inspeccionar ni frenar bit a
bit). Con SSL Bump activo —que es como SquidManager viene configurado por
defecto— Squid descifra la conexión y la trata como HTTP normal por
dentro, así que los delay pools sí aplican: confirmado descargando un
archivo real por HTTPS a través del proxy con una regla de 50 KB/s
activa, la velocidad bajó de forma consistente con lo esperado.

Backend sin cambios (ya soportaba clase 1 y clase 2 con cualquier ACL);
todo el trabajo fue de interfaz. 462 tests de backend siguen pasando.

#### Punto 3: cuotas de navegación con periodo y acción configurable

Amplía y reemplaza la idea más simple ya anotada arriba en ["Cuotas por
volumen total"](#funciones-inspiradas-en-squidstats-comparación-2026-09-18)
(inspirada en SquidStats, sin periodo ni acción configurable). Ahora con
más detalle:

- **Periodo:** diario, semanal o mensual — se resetea solo al empezar el
  siguiente periodo.
- **Acción al agotarse, a elegir:**
  1. **Cortar la navegación** hasta el próximo periodo — reutiliza la
     función de deshabilitar usuario que **ya existe y ya funciona**
     (purga de credenciales incluida, ver
     [authentication.md](authentication.md)), reactivándola sola al
     empezar el periodo siguiente.
  2. **Limitar la velocidad** en vez de cortar — reutiliza el motor de
     delay pools del punto 1 (una vez rediseñado): al agotar la cuota, se
     mueve al usuario a un pool con un límite bajo en vez de deshabilitarlo.

Combinación interesante con ["Terminar una conexión activa de un
cliente"](#funciones-inspiradas-en-squidstats-comparación-2026-09-18) (ya
anotada arriba): si la acción es "cortar", se podría además terminar de
inmediato sus conexiones ya abiertas en vez de esperar a que las cierre
solo — es opcional, no un requisito para la primera versión.

El cálculo del consumo se apoya en lo que ya existe (SquidManager ya suma
bytes por usuario desde el `access.log` para el dashboard) — lo nuevo es
compararlo contra una cuota configurada y disparar la acción. No se
estimó esfuerzo de implementación todavía.

**Verificado contra fuentes externas (2026-09-18), a pedido del autor
antes de empezar a implementar:** Squid no tiene ningún mecanismo nativo
de cuota por volumen — confirmado que la práctica estándar de la
comunidad es exactamente lo que ya se tenía planeado acá: sumar bytes por
usuario/periodo desde `access.log` (o una tabla propia) y comparar contra
un límite configurado, sin depender de ninguna directiva de Squid para
esto. No cambia nada del diseño ya anotado arriba.

Sobre "Terminar una conexión activa de un cliente" (arriba): confirmado
por el propio mantenedor de Squid (Amos Jeffries, lista squid-users) que
Squid no tiene forma de matar una conexión existente por sí solo — "la
única forma es identificar IP:puerto y usar herramientas de control TCP
del sistema para forzar que muera" (`conntrack`/`iptables`), tal cual ya
estaba anotado. Confirma que el diseño planeado (una operación más del
adaptador de runtime nativo/Docker) es el camino correcto, no un atajo.

**Actualización (2026-09-18) — implementado y probado en vivo contra
tráfico real.** Extiende `ProxyUser` (migración 0028) con `quota_bytes`,
`quota_period` (`daily`/`weekly`/`monthly`), `quota_action`
(`cut`/`throttle`), `quota_throttle_bytes_per_sec`, y el estado en vivo
`quota_bytes_used`/`quota_period_started_at`/`quota_action_applied`. Nace
en NULL para todo usuario existente, mismo criterio que el resto de
mecanismos "apagados hasta que el admin los activa a propósito".

Un hilo de fondo nuevo (`quota_service.py`, arrancado junto a
`start_syslog_forwarder`/`start_category_sync` en el lifespan) sigue el
`access.log` igual que `tail -f` (se extrajo `read_new_lines()` de
`syslog_service.py` a `log_service.py` para no duplicar esa lógica, con
su propio manejo de rotación) y suma bytes por usuario cada ~15 s. Al
agotarse la cuota:
- **"cut"**: deshabilita al usuario exactamente como el interruptor
  manual de Gestión > Usuarios (purga de credenciales incluida).
- **"throttle"**: crea sola una ACL `proxy_auth` (`cuota_usuario_<id>`,
  por id y no por nombre para no reimplementar la validación de
  caracteres de las ACLs) y un delay pool clase 1 al límite configurado
  (migración 0029, columna `quota_user_id` en `delay_pools` para poder
  encontrarlo y borrarlo después sin arriesgarse a tocar uno creado a
  mano).

A diferencia del resto de cambios de configuración del panel (que quedan
en "pendiente de aplicar" hasta que el admin aprieta *Aplicar cambios*),
una cuota agotada **aplica de inmediato** — es cumplimiento automático,
no una edición para revisar. Al empezar el siguiente periodo se revierte
sola (reactiva al usuario o borra el delay pool) y resetea el contador;
si el admin edita o quita la cuota a mano mientras ya estaba aplicada, se
revierte en el acto en vez de esperar al reinicio de periodo.

Verificado en vivo contra la VM de pruebas, con tráfico real a través del
proxy (no solo la lógica en tests): una cuota de 20 KB con acción
"cortar" — tras descargar 50 KB reales, el usuario quedó deshabilitado
solo (confirmado con un 407 al intentar navegar de nuevo) sin intervención
manual. La misma prueba con acción "limitar velocidad" creó el delay pool
solo y la descarga siguiente bajó de ~1900 KB/s a ~53 KB/s. Quitar la
cuota a mano revirtió ambas cosas al instante (usuario reactivado / delay
pool borrado, velocidad de vuelta a lo normal). 485 tests de backend
pasan (23 nuevos: matemática de reinicio de periodo incluyendo meses de
distinta longitud y años bisiestos, disparo/no-repetición de la acción,
acumulación de consumo, reversión, y validación de la API).

Alcance: solo usuarios **locales** del proxy — un usuario LDAP se
deshabilita desde la sincronización LDAP, no tiene una fila propia que
este mecanismo pueda controlar; queda pendiente para una vuelta futura si
hace falta.

No implementado en esta vuelta: "terminar una conexión activa" al
disparar "cortar" (la combinación opcional anotada arriba) — la cuota
corta el acceso a partir de ahora, pero no interrumpe una descarga que ya
estaba en curso en el momento exacto de agotarse.

**Actualización (2026-09-19) — dos huecos reales encontrados al pensar en
un caso concreto (50 usuarios locales + importados de Active Directory,
¿hay que ponerles la cuota uno por uno?), y resueltos con un cambio de
diseño en vez de un parche:**

1. **No había forma de aplicar una cuota a varios usuarios a la vez** —
   solo un formulario de a uno.
2. **Los usuarios LDAP no podían tener cuota en absoluto** — el mecanismo
   dependía de columnas en `proxy_users`, y un usuario importado de AD no
   tiene fila ahí.

**Opción descartada:** duplicar las 7 columnas de cuota en `ldap_users` y
duplicar la lógica de aplicación para cada tabla. Quedaba dos veces casi
lo mismo, con dos migraciones y dos caminos de prueba a mantener en
paralelo indefinidamente.

**Solución adoptada:** la cuota se movió a su propia tabla,
`navigation_quotas` (migración 0030), indexada por **nombre de usuario**,
no por id de una tabla concreta — una cuota es, en el fondo, "este nombre
tiene un límite", sin importar si el nombre es de un usuario local o de
uno importado de LDAP. `quota_service.py` resuelve en el momento de
aplicar/revertir contra cuál de las dos tablas corresponde actuar (si
existe un local y un LDAP con el mismo nombre, gana el local, por ser la
cuenta que de verdad se autentica). El delay pool que crea la acción
"limitar velocidad" pasó a apuntar a `navigation_quotas.id`
(`delay_pools.quota_id`, antes `quota_user_id` contra `proxy_users.id`).

Rutas nuevas, `/api/quotas/` (reemplazan los campos `quota_*` que antes
vivían en `POST`/`PUT /api/proxy-users`):
- `GET /` — todas las cuotas configuradas.
- `PUT /{username}` — crear o reemplazar la cuota de uno.
- `POST /bulk` — la misma cuota para varios nombres de una sola vez
  (resuelve el problema 1); "mejor esfuerzo", un nombre inválido no
  aborta a los demás.
- `DELETE /{username}` — quitarla (reemplaza el flag `remove_quota` que
  tenía el PUT de usuarios).

Interfaz: la columna "Cuota" de Gestión → Usuarios ahora funciona igual
para filas locales y LDAP (antes mostraba "—" para LDAP); se sumó una
casilla de selección por fila y una barra de acción en bloque ("N
seleccionados" → "Aplicar cuota a los seleccionados") que abre el mismo
diálogo en modo "aplicar a varios" (sin valores previos que precargar, sin
opción de "quitar" -no tiene sentido quitarle a todos una cuota que no
todos tenían igual).

**Encontrado al volver a probar en vivo (usuario local + una fila LDAP
sintética, sin servidor LDAP real disponible para generar tráfico
autenticado de verdad contra ese camino -limitación del entorno de
pruebas, no de la función):** cortar a un usuario reinicia Squid por
completo para purgar credenciales (`systemctl restart squid`, no un `-k
reconfigure` liviano) — medido en vivo, **~45 segundos** cada vez. Si
varias cuotas se agotan en la misma vuelta del hilo de fondo (cada 15s),
se procesan una por una: con muchos usuarios cortándose a la vez, esa
vuelta puede tardar varios minutos antes de quedar libre para la
siguiente. No es un bug -cada corte de por sí funciona bien, confirmado
para el camino local (usuario deshabilitado, después un 407 real al
intentar navegar) y para el LDAP sintético (allow-list reescrita,
reconfigure exitoso)- pero es una característica real a tener presente si
esto llega a usarse con muchos usuarios agotando la cuota al mismo
tiempo. Candidato a revisar más adelante si se vuelve un cuello de
botella real (ej. paralelizar los cortes, o separar el reinicio de Squid
de la purga en vez de acoplarlos).

492 tests de backend pasan (26 de cuotas + 6 de validación, reescritos
sobre el nuevo diseño).

**Actualización (2026-09-19) — verificado en vivo contra un usuario LDAP
real (superando la limitación anotada arriba, "sin servidor LDAP real
disponible"), y bug real de fondo encontrado y corregido en el proceso.**

Con el AD real de la VM de pruebas ya configurado (ver [ACLs por grupo de
Active Directory / LDAP](#acls-por-grupo-de-active-directory--ldap)), se
sincronizó, se le puso una cuota real de 5 MB/día con acción "cortar" a
un usuario LDAP real (`llopez`), y minutos después, con tráfico real
generado por ese usuario, **el corte se disparó solo**: quedó deshabilitado
en `ldap_users` y removido del archivo que Squid usa como allow-list —
confirma que la rama LDAP de `_resolver_identidad()` funciona de punta a
punta contra un directorio real, no solo en los tests con dobles.

**Bug real encontrado en el camino:** al reiniciar el backend para este
mismo trabajo, la cuota de `llopez` saltó de 0 a **55 MB de "consumo"** sin
que hubiera navegado nada nuevo. Causa: `quota_service.py` (y también
`syslog_service.py`, mismo patrón) guardaban en `/tmp` hasta dónde habían
leído el `access.log`, pero el servicio corre con `PrivateTmp=yes` —cada
reinicio del backend (deploy, upgrade, un crash, un reboot) borra ese
`/tmp` y el siguiente ciclo relee el log **entero** como si fuera todo
tráfico nuevo, inflando de golpe el consumo de cualquiera que ya tuviera
una cuota activa (y, en el caso de syslog, reenviando el historial
completo de nuevo a un destino externo). No es exclusivo del entorno de
pruebas: le pasaría a cualquier instalación nativa real tras un reinicio
del servicio. Corregido moviendo el archivo de estado a la carpeta del
backend, mismo criterio que ya usaba `metrics_service.py` por el mismo
motivo (auditoría de seguridad de septiembre, hallazgo 05-004) —
verificado con dos reinicios seguidos del backend en la VM, el offset ya
no se pierde.

521 tests de backend pasan.

### Categorización de dominios (2026-09-18)

Pedido por el autor del proyecto: poder agrupar dominios en categorías
reutilizables (ej. "Redes sociales", "Streaming"), usables al crear ACLs o
reglas, cargables de dos formas: (a) manualmente, con un archivo en un
formato a definir, y (b) importadas desde sitios o servicios online
dedicados a esta tarea.

**Verificado en el código actual:** SquidManager **ya tiene** el mecanismo
de base para esto — una ACL de tipo `dstdomain`/`dstdom_regex` puede venir
de un archivo (`source='file'`), con carga masiva de hasta 250 MB y modo
"reemplazar" o "agregar" (`backend/app/routes/acls.py`). Una "categoría" es,
en esencia, darle a este mecanismo ya existente una capa de identidad
reutilizable — que se pueda elegir por nombre desde el creador de reglas y
de delay pools (ver la entrada de arriba), en vez de que cada lista sea una
ACL aislada. Para la parte (a) (carga manual), el formato más simple y ya
compatible es el mismo que hoy acepta la carga de ACL de archivo: un
dominio por línea — no hace falta inventar un formato nuevo.

**Para la parte (b) (importar desde un servicio externo), esto todavía NO
está verificado y no hay que darlo por sentado:** el candidato más natural
a investigar primero es algún proyecto de listas de bloqueo por categoría
pensado específicamente para Squid/SquidGuard (existen proyectos
académicos de este tipo, históricamente usados en instalaciones Squid
reales), pero hace falta confirmar en su momento si siguen mantenidos, en
qué formato exacto distribuyen las listas hoy, y bajo qué licencia se
pueden redistribuir — no se investigó todavía, así que no se nombra ninguno
en concreto acá para no comprometerse con algo sin verificar.

Riesgo: bajo-medio para la parte manual (extiende algo que ya funciona);
la parte de importación externa depende de qué tan estable sea la fuente
que se elija, a evaluar cuando se investigue. No se estimó esfuerzo de
implementación todavía.

**Actualización (2026-09-18) — parte manual implementada y probada en
vivo contra la VM de pruebas.** Backend: columna `is_category` en `acls`
(migración 0025), validada solo para `dstdomain`/`dstdom_regex`; filtro
`GET /api/acls/?is_category=` y soporte en `POST /api/acls/` y
`POST /api/acls/bulk-domains`. Frontend: página nueva **Categorías de
dominios**. Backup/restore actualizado para exportar e importar
`is_category` (antes se perdía el flag al restaurar). Documentado en
[api-reference.md](api-reference.md#categorías-de-dominios),
[panel-web.md](panel-web.md) y [caracteristicas.md](caracteristicas.md).
456 tests siguen pasando; `squid -k parse` valida una categoría real sin
warnings.

Dos ajustes de UX que salieron de probarlo en vivo con el autor, no
previstos en el diseño original:
- **Nombres de categoría normalizados en vivo**: los nombres de ACL de
  Squid no admiten espacios ni mayúsculas (`^[A-Za-z][A-Za-z0-9_-]{0,63}$`,
  ver `squid_names.py`); escribir "Redes Sociales" a mano tiraba el error
  recién al guardar. Ahora se transforma solo mientras se escribe
  ("Redes Sociales" → `redes_sociales`), sin tocar el backend.
- **Autocompletado de categorías existentes al cargar por archivo**:
  probado en vivo, un typo de una sola letra al reescribir el nombre de
  una categoría ya creada (`redessociales` vs `redesociales`) creó una
  categoría nueva separada en lugar de sumarle el dominio a la que ya
  existía — "agregar a lo que ya había" funciona bien cuando el nombre
  coincide exacto, el problema era pedirle al admin que lo reescriba de
  memoria. Se agregó un `<datalist>` con las categorías existentes para
  elegir en vez de retipear.

**Actualización (2026-09-18) — importación externa implementada y
verificada en vivo.** Se investigaron y verificaron contra las fuentes
reales (no de memoria) 5 candidatos: HaGeZi dns-blocklists (activo,
categorías temáticas reales, formato ya compatible, GPL-3.0 — elegido),
oisd.nl (descartado: no ofrece categorías de contenido, solo ads/tracking
genérico), The Block List Project (formato de la raíz incompatible —
"hosts", no dominio-solo—, y licencia inconsistente entre el repo y cada
archivo — queda para una segunda vuelta), "Pi-hole optimized blocklists"
(no es una fuente concreta) y domainCat (descartado: no es una lista
descargable, es scraping en vivo de portales de terceros, abandonado desde
2021).

Diseño adoptado, decidido explícitamente en contra de la sugerencia inicial
de dejarlo "conectado de fábrica": un botón (**"Cargar categorías
predefinidas (HaGeZi)"**), no una sincronización activada sola desde una
instalación nueva — mismo criterio que LDAP/Kerberos/el asistente de IA
(apagado hasta que el admin lo activa a propósito). Una vez cargado, el
refresco diario sí corre solo, sin que haga falta repetir el clic.

Implementado:
- Columnas nuevas en `acls` (migración 0026): `sync_url`, `last_synced_at`,
  `last_sync_status`. Nace en NULL para toda ACL existente — nada empieza
  a sincronizar sin que el admin lo conecte a propósito.
- `category_sync_service.py`: hilo de fondo en el propio proceso (mismo
  patrón que `update_service.start_update_checker` — funciona igual en
  Docker y en nativo, no depende de `systemd` ni de `cron`), refresco cada
  24 h de cualquier ACL con `sync_url`, siempre en modo **"agregar", nunca
  "reemplazar"**: decisión de diseño explícita para no pisar dominios que
  el admin sume a mano sobre una lista externa — la contra documentada es
  que si la fuente saca un dominio de su lista, acá queda pegado igual.
- Refactor: la lógica de mezcla/dedup que antes vivía solo en
  `acls.bulk_domains` se extrajo a `squid_service.aplicar_lista_dominios`,
  compartida por la carga manual y la sincronización automática.
- Endpoints: `POST /api/acls/hagezi-preset` (carga las 9 categorías y
  sincroniza al momento) y `POST /api/acls/{id}/sync-now` (repetir sin
  esperar al refresco diario). `sync_url` también se puede fijar a mano vía
  `PUT /api/acls/{id}` — no atado únicamente al preset de HaGeZi.

**Las 9 categorías curadas** (de un catálogo real de 42 listas de HaGeZi,
verificado en vivo — la mayoría del resto son paquetes combinados que
mezclan todo sin distinguir categoría, o rastreadores de telemetría por
fabricante de hardware pensados para un filtro DNS personal, no para
política de navegación de una organización):

| Categoría | Contenido | Dominios (verificado en vivo) |
|---|---|---|
| `hagezi_gambling` | Apuestas y juego online (`.mini`, no la lista completa de 517.000) | 134.081 |
| `hagezi_nsfw` | Contenido para adultos | 74.633 |
| `hagezi_pirateria` | Piratería | 51.171 |
| `hagezi_social` | Redes sociales en general | 900 |
| `hagezi_fraudes` | Tiendas y sitios falsos, estafas | 17.234 |
| `hagezi_evasion_proxy` | DNS cifrado/VPN/Tor — no es "contenido", protege al proxy mismo de ser evadido | 16.432 |
| `hagezi_popupads` | Pop-ups publicitarios maliciosos | 50.556 |
| `hagezi_amenazas` | Malware/phishing (`tif.mini`, no la versión completa de 2.5 millones) | 186.096 |
| `hagezi_acortadores` | Acortadores de URL — ⚠️ bloquea todos, no solo los usados para evadir bloqueos; alto riesgo de falso positivo, incluida a pedido explícito con esta advertencia | 9.965 |

Verificado en vivo contra la VM de pruebas: descarga de las 9 listas
(~541.000 dominios combinados) en <5 s; `squid -k parse` las acepta sin
warnings en 2.4 s; un dominio agregado a mano sobrevive intacto a un
refresco automático posterior; detección de "sin cambios" evita reescribir
el archivo en disco cuando la fuente no trajo nada nuevo. 462 tests pasan
(6 nuevos para esta función).

**Segunda ronda de ajustes de UX (2026-09-18), a partir de revisar la
pantalla real con el autor:**

- **Nombre amigable separado del técnico** (`display_name`, migración
  0027): las categorías de HaGeZi quedaban en la tabla con nombres como
  `hagezi_gambling` — correcto como identificador de Squid, confuso para
  reconocer de un vistazo. Ahora la tabla muestra un nombre legible
  ("Apuestas y juego online") en grande y el nombre técnico chico debajo;
  el técnico sigue siendo el que hay que usar en reglas/delay pools, sin
  cambios ahí.
- **Las categorías con muchos dominios (`source=file`) no se podían
  editar**: la única acción disponible era "Reemplazar" (volver a subir el
  archivo completo). Ahora tienen un editor de metadatos real
  (`display_name`, descripción, activa/inactiva, y desconectar la
  sincronización) que no toca la lista de dominios — verificado en vivo:
  editar una categoría de 51.171 dominios no le tocó ni uno.
- **Botones secundarios invisibles contra el fondo**: `btn-ghost` es
  discreto a propósito para acciones de baja prioridad, no para las dos
  formas principales de cargar una categoría. Se sumó `btn-accent` (para
  "Cargar categorías predefinidas") y una variante nueva `btn-outline`
  (fondo y borde con color, visible en reposo, no solo al pasar el mouse).
- **Acciones de fila como texto ("Sincronizar ahora", "Reemplazar",
  "Eliminar") reemplazadas por íconos** con tooltip — se sumaron
  `IconEdit` e `IconTrash` (no existían en el proyecto) y una clase
  `.btn-icon` reutilizable, pensada para cualquier tabla con varias
  acciones por fila, no solo esta.

### Dashboard: nuevos KPIs para las funciones de arriba (2026-09-18)

Pedido por el autor del proyecto: una vez que existan las funciones nuevas
(cuotas, ancho de banda rediseñado, categorías, y las de monitoreo — caché
de Squid, conexiones en vivo), sumar sus indicadores al dashboard,
**manteniendo el diseño base de la plataforma** y priorizando que sea
amigable, no sobrecargado.

No es una función en sí misma, sino la fase final de las de arriba —
depende de que cada una exista antes de poder mostrar su dato. Candidatos
razonables una vez implementadas: usuarios cerca de agotar su cuota,
consumo de caché de Squid (entradas, disco), conexiones activas en este
momento. No se estimó esfuerzo ni se definió el diseño visual todavía —
eso se hace recién cuando haya datos reales de qué mostrar.

**Actualización (2026-09-19) — implementado el primero de los tres
candidatos, deliberadamente no los tres.** Se sumó "usuarios cerca de
agotar su cuota" (≥80% de su límite, sin que la acción se haya aplicado
todavía) como un aviso que solo ocupa espacio cuando hay alguien en esa
situación -no una tarjeta fija casi siempre vacía-, con link directo a
Gestión → Usuarios. Los otros dos candidatos (caché de Squid, conexiones
activas) se dejaron **fuera del dashboard principal a propósito**: los dos
ya tienen su propia pantalla dedicada ("Estado del caché", que ahora
también incluye conexiones activas -ver la entrada de "Estadísticas de
caché de Squid" más abajo-), y duplicarlos en el dashboard iba en contra
del propio pedido de "no sobrecargado". Motivo técnico adicional para no
sumar conexiones activas al dashboard: ese dato sale de una consulta en
vivo al Cache Manager de Squid, y el dashboard principal se refresca cada
5 segundos -someter a Squid a esa consulta extra cada 5s por cada admin
con el dashboard abierto no se justificaba por un dato que ya tiene su
propio lugar.

`GET /api/panel/dashboard` (y `/api/metrics/dashboard`) suman el campo
`quotas_en_riesgo` (cuenta, no la lista de nombres -esto se pinta en un
dashboard compartido, no es el lugar para señalar personas-). Nuevo
`contar_cuotas_en_riesgo()` en `quota_service.py`, con `UMBRAL_RIESGO = 0.8`.

### Dashboard: rediseño responsivo y saneamiento del backend (2026-09-24)

Sesión larga a pedido del autor, arrancó revisando el layout del Dashboard
en distintas resoluciones (27" vs. laptop estándar) y terminó destapando
varios problemas de fondo del backend que no eran específicos de esa
pantalla. Resumen de lo implementado, verificado y comiteado a `pruebas`:

**Dashboard (frontend + `metrics_service.py`).** La tarjeta "Sistema"
(CPU/RAM/Disco/SWAP) se saca de al lado del gráfico de tráfico -no entraba
bien en anchos intermedios (~1280-1536px), cortando o envolviendo texto de
forma dispareja- y pasa a una tira minimalista permanente en el header, en
cualquier resolución. Las 5 tarjetas superiores ganan un modo compacto por
debajo de 1536px (sin sparkline, texto/íconos reducidos). En el backend,
`get_dashboard()` dejó de recalcular `top_users`/`top_domains`/
`top_blocked_users` con una ventana que el frontend siempre reemplazaba
-trabajo tirado a la basura en cada refresco de 5s-, se filtran los
marcadores internos `error:*` de Squid para que no aparezcan como si fueran
un dominio visitado, y "Salud de las peticiones" ahora contabiliza las
peticiones sin código de respuesta en vez de que el total no cierre.

**Rate limiting.** El límite general (120 peticiones/min por IP) no
distinguía pestañas: dos pestañas del dashboard abiertas a la vez (cada
una sondeando cada 5s) ya lo superaban, y ahí el backend devolvía 429 en
todas las pestañas por igual sin que hubiera abuso real. Confirmado contra
los logs de nginx (ráfagas de 7 peticiones cada ~2.5s, firma de dos
pollers de 5s desfasados). Subido a 400/min; el límite de login no cambia.

**Rutas síncronas en todo `app/routes/` (el hallazgo más importante).**
`metrics.py` tenía 15 rutas `async def` sin ningún `await` real, haciendo
trabajo bloqueante (parsear `access.log`, consultar el Cache Manager de
Squid) directo sobre el único hilo del event loop -con un solo worker de
uvicorn, eso congela el backend entero para todos los admins, no solo para
quien hizo la petición-. Una auditoría con `ast` (no a mano) sobre los 114
endpoints `async def` del proyecto encontró **92 más con el mismo patrón,
en 24 archivos**. Se corrigieron 92: quitarles `async` alcanza (Starlette
las manda solas a su threadpool) porque ninguna hacía `await` de verdad.
Comiteados 19 archivos limpios; `access_rules.py`, `admins.py`,
`central.py` y `squid_config.py` quedan con la corrección aplicada en el
working tree pero sin commitear, porque ya tenían cambios pendientes de
otra sesión mezclados en el mismo archivo -no pareció correcto arrastrar
ese trabajo a un commit sin que se revise aparte-. `/central/dashboard`
(Panel Central) tiene el mismo patrón y no se tocó por no ser parte de lo
que se estaba probando esta sesión.

**Estado de carga animado + reintento en toda la app.** Las ~30 páginas
del panel mostraban el mismo texto estático "Cargando..." y la mayoría no
manejaba el fallo de la carga inicial -encontrado en vivo en `Smtp.tsx` y
`Notifications.tsx`: si la carga fallaba, la página se quedaba con el
spinner colgado para siempre, porque la condición de salida dependía de un
estado que nunca dejaba de ser `null`-. Nuevo componente compartido
`AsyncState.tsx` (spinner animado + botón "Reintentar"), aplicado en las
~26 páginas con el patrón viejo.

**Chequeo de traducciones en CI.** `traducir("texto")` usa el propio texto
en español como clave: un texto nuevo sin su entrada en `en.json`/
`pt.json` no rompe nada visible en español, así que el hueco se
descubría de a uno, a mano (esta sesión sola: "Aplicar ahora", "n/d",
"Redir.", "errores", "Otros", y 21 más -casi todos los tooltips del
Dashboard, que nunca se habían traducido- al correr el script recién
escrito por primera vez). Nuevo `frontend/scripts/check-i18n.cjs`, sumado
al workflow de CI justo después de `tsc --noEmit`.

**Code-splitting por ruta.** El bundle inicial (823 KB) traía las ~30
páginas del panel juntas sin importar cuál se fuera a mirar primero -Vite
avisaba de esto en cada build ("chunks larger than 500 kB") y nunca se
atendió-. Cada página pasa a `React.lazy()` con un `<Suspense>` que
reutiliza el mismo spinner de arriba. El chunk inicial baja a 420 KB (139
KB gzip, contra 247 KB antes).

**Verificado antes de cada commit:** 596 tests de backend pasan, `tsc
--noEmit` y `npm run check-i18n` limpios, `npm run build` sin warnings de
chunk grande, servido en vivo contra la VM de pruebas después de cada
cambio.

**Pendiente explícito, no por olvido** (ver la tabla de arriba): el
espacio que dejó libre la tarjeta Sistema, dónde mostrar Latencia/Total
transferido, los 4 archivos de rutas sin commitear, y `/central/dashboard`
con el mismo riesgo de bloqueo sin corregir todavía.

#### Propuesta de análisis de datos (comparación con SquidStats, 2026-09-24)

A pedido del autor, con capturas reales de SquidStats como referencia -sin
copiar su diseño, analizando qué conceptos le faltan a SquidManager y
verificando cada uno contra el código propio antes de anotarlo, mismo
criterio que la comparación del 2026-09-18-:

- **Top dominios por bytes transferidos** (no solo por cantidad de
  peticiones): el backend ya calcula `domain_bytes` en `get_top_domains()`;
  solo falta el mismo toggle Datos/Peticiones que "Top usuarios" ya tiene.
  Costo muy bajo.
  **Actualización (2026-09-24) — implementado.** `get_top_domains()` suma
  `sort_by`; toggle Datos/Peticiones en "Top sitios visitados" del Dashboard
  y en la pestaña "Sitios visitados" de Actividad de red.
- **IPs compartidas por varios usuarios**: señal de seguridad real (cuenta
  compartida o mismo equipo con varias cuentas). El cruce usuario+IP ya
  está disponible por línea de log, encajaría en Auditoría sin pantalla
  nueva. Costo bajo.
  **Actualización (2026-09-24) — implementado, como pestaña nueva en
  Actividad de red en vez de en Auditoría** (encaja mejor temáticamente:
  es comportamiento de red, no historial de cambios de configuración).
  Nueva `get_ips_compartidas()`, con su propio render en el frontend -no
  entra en el modelo de ranking de un solo número que usan las demás
  pestañas, cada fila es una IP con varios usuarios-. 8 tests nuevos
  (primeros de metrics_service.py, que no tenía ninguno).
- **Reporte con rango de fechas libre** (no solo ventanas fijas
  1h/24h/7d/30d): se apoya en `historical_log_service.py`, que ya existe.
  Costo medio.
- **Detección de anomalías por reglas simples** (pico de tráfico inusual,
  un usuario contra 10+ sitios bloqueados en poco tiempo) -explícitamente
  no "IA opaca", encaja con `notification_service.py`. Costo medio.
- **Descartado a propósito:** historial de recursos del sistema
  (CPU/RAM/SWAP en el tiempo) -es trabajo de una herramienta de monitoreo
  de infraestructura (Grafana/Zabbix/Netdata), no de un panel de gestión
  de proxy; reconstruirlo adentro sería justo el tipo de función que
  sobrecarga el producto sin aportar algo específico de Squid. Reportes
  programados y export CSV/Excel también quedan afuera por ahora: mismo
  criterio que ya aplicó el proyecto con los KPIs del dashboard -esperar
  un caso real antes de construir.
- Verificado además que las dos propuestas de
  `squid-manager-propuesta-mejoras.md` (autenticación Digest y sistema de
  logs históricos) **ya estaban implementadas por completo**
  (`digest_ha1`/`write_digest_file` en el backend,
  `historical_log_service.py` + `HistoricalLogs.tsx` + tests) -ese
  documento no tiene nada pendiente.
