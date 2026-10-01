# Política de seguridad

## Versiones con soporte de seguridad

Solo la última versión publicada de la serie 1.x. Actualiza desde **Sistema → Actualizaciones** o con
`upgrade-nativo.sh` / `upgrade-docker.sh`.

## Cómo informar de una vulnerabilidad

**No abras un issue público.** Usa una de estas dos vías:

1. En GitHub: pestaña **Security → Report a vulnerability** de este repositorio (informe privado).
2. Por correo a **networkingenier@gmail.com**, con el asunto «SquidManager - seguridad».

Incluye la versión (`/health` o la pantalla Contacto), el modo de despliegue (Docker o nativo), los pasos para
reproducirlo y el impacto que ves. Es un proyecto mantenido por una persona: intento responder en unos días y
corregir lo grave lo antes posible. Te mencionaré en las notas de la versión si lo deseas.

## Qué está dentro del alcance

El panel y su API, los scripts de instalación y actualización, la configuración de Squid que se genera y los
helpers de autenticación. Fuera de alcance: vulnerabilidades de Squid, PostgreSQL u otros componentes (informa
a sus proyectos) y configuraciones inseguras hechas a propósito (por ejemplo, exponer el panel sin TLS a
Internet; ver `docs/production.md`).

## Para quien administra una instalación

Lee `docs/production.md` (TLS por delante, `TRUSTED_PROXY_HOSTS`) y `docs/audits/` (estado de la última
auditoría de seguridad).
