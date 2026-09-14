# SquidManager - Bitácora del Proyecto

**Proyecto:** SquidManager - Panel de gestión web para Squid Proxy  
**Repositorio:** /opt/squid-manager (servidor de pruebas)  
**Licencia:** Apache-2.0  
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
