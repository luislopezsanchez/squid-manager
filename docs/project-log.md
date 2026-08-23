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
   - Login JWT funciona (admin/admin123)
   - CRUD de usuarios del proxy operativo
   - Squid proxy en puerto 3128 con autenticación básica
   - Proxy enruta tráfico correctamente con credenciales válidas
   - Deniega acceso sin credenciales

### Verificación final
```bash
# Con credenciales → funciona
curl -x http://testuser:test123@localhost:3128 http://httpbin.org/ip
# → {"origin": "172.18.0.1, 179.24.100.152"}

# Sin credenciales → denegado
curl -x http://localhost:3128 http://httpbin.org/ip
# → ERROR: Cache Access Denied
```

### Estado de los contenedores
| Contenedor | Puerto | Estado |
|-----------|--------|--------|
| squidmgr-db | 5432 (interno) | Healthy |
| squidmgr-backend | 8000 | Running |
| squidmgr-proxy | 3128 | Running |
| squidmgr-frontend | 3000 | Running |

### URLs de acceso
- Panel web: http://TU_SERVIDOR:3000
- API docs: http://TU_SERVIDOR:8000/docs
- Proxy: http://TU_SERVIDOR:3128

### Credenciales por defecto
- Admin panel: admin / admin123
- Usuario proxy de prueba: testuser / test123

---

## Próximos pasos (Fase 3)

1. UI: Gestión de ACLs (crear, editar, eliminar ACLs personalizadas)
2. UI: Gestión de reglas de acceso (http_access con orden drag-and-drop)
3. Validador de sintaxis de ACLs antes de aplicar
4. Aplicar cambios en caliente (squid -k reconfigure)
5. Página de configuración general de Squid (puertos, caché, logging)

---

## Riesgos activos
1. **passlib + bcrypt 5.x**: Incompatible, fijado a 4.2.1. Monitorear futuras versiones.
2. **Docker socket montado**: El backend tiene acceso completo a Docker. En producción, restringir permisos.
3. **CORS abierto a ***: Restringir en producción al dominio del frontend.
4. **Archivo htpasswd en volumen compartido**: Ambos contenedores (backend y squid) montan squid-config. Sincronización correcta verificada.