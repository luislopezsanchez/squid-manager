# Panel web — Secciones

El panel se organiza en tres grupos:

| Grupo | Sección | Función |
|-------|---------|---------|
| **Vigilancia** | Dashboard | Estado del proxy, tráfico en tiempo real, top usuarios y dominios |
| | Registros | Visor del access.log, con filtros y alertas de fuerza bruta |
| | Histórico | Meses ya cerrados, con resumen precalculado |
| | Auditoría | Log de todos los cambios realizados |
| **Políticas** | Usuarios | CRUD de usuarios del proxy |
| | Grupos | Agrupa usuarios y aplica políticas al grupo completo |
| | ACLs | CRUD de listas de control de acceso |
| | Categorías de dominios | ACLs de dominio con nombre reutilizable (ej: Redes sociales), para usar en reglas y delay pools |
| | Reglas de acceso | CRUD de reglas `http_access` con reordenamiento |
| | Ancho de banda | CRUD de delay pools (limitación de velocidad) |
| **Sistema** | LDAP | Configuración LDAP/Active Directory |
| | Kerberos | Autenticación Negotiate (SSO) contra Active Directory |
| | Certificado | Descarga CA + instaladores por sistema operativo |
| | Configuración | Parámetros generales de Squid |
| | Notificaciones | Avisos por email y Telegram |
| | Syslog externo | Reenvío del access.log a un SIEM/ELK/Splunk |
| | Proxy padre | Salir a Internet por otro proxy (encadenado) |
| | Backup y migración | Exportar/restaurar configuración, importar squid.conf |
| | Actualizaciones | Ver y aprobar actualizaciones (instalación nativa) — ver [actualizaciones-automaticas.md](actualizaciones-automaticas.md) |
| | Administradores | Gestión de cuentas del panel (solo superadmin) |

Ver también [caracteristicas.md](caracteristicas.md) para el detalle de qué
hace cada función, y [api-reference.md](api-reference.md) para los endpoints
que usa cada sección.
