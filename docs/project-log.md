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

## Riesgos activos

| Riesgo | Estado |
|--------|--------|
| Docker socket montado en el backend | **Sigue abierto.** Es una decisión de arquitectura: el backend necesita controlar Squid. Contenerlo requeriría un proxy de socket restringido o un agente intermedio — ver `docs/architecture.md`. |
| SSL Bump descifra todo el HTTPS salvo lo excluido explícitamente | **Mitigado, no eliminado.** Desde la Fase 4 existe `ssl_bump_exclude` para banca, sanidad y apps con certificate pinning, pero por defecto está vacío: hay que rellenarlo a propósito. |
| ~~passlib + bcrypt 5.x incompatible~~ | **Resuelto en la Fase 4.** passlib se retiró; se usa bcrypt directamente. |
| ~~CORS abierto a `*`~~ | **Resuelto en la Fase 4.** Lista explícita de orígenes, vacía por defecto. |
| ~~Puerto 8000 del backend público~~ | **Resuelto en la Fase 4.** Ya no se publica al host. |
| Archivo htpasswd en volumen compartido | Sigue siendo el mecanismo (backend y squid montan `squid-config`), ahora con permisos `600` en vez de los por defecto. Sincronización correcta verificada de nuevo tras la auditoría. |
