# Características — SquidManager

Lista completa de funciones, agrupada por área. Para la arquitectura técnica
detrás de cada una, ver [architecture.md](architecture.md).

## Gestión de proxy
- **ACLs visuales** — Crea listas de control de acceso por dominio, IP, horario, regex, puerto, método HTTP y más (29 tipos soportados)
- **Carga masiva de dominios** — Sube un archivo con miles de dominios para una blocklist; por debajo de 200 entra como ACL normal, por encima se respalda en un archivo aparte que Squid lee directo, no como una línea gigante en `squid.conf`
- **Categorías de dominios** — Agrupa dominios bajo un nombre reutilizable (ej: Redes sociales, Streaming), creado a mano o cargado desde archivo, para usarlo directo al crear reglas de acceso o límites de ancho de banda
- **Reglas de acceso** — Ordena reglas `http_access` con botones de subir/bajar
- **Grupos de usuarios** — Agrupa usuarios locales o LDAP y aplica políticas de acceso a todo el grupo de una vez
- **Delay Pools** — Control de ancho de banda por usuario con interfaz visual (sin necesidad de entender el formato `64000/64000 64000/32000`)
- **Configuración general** — Puerto, caché, logging, realm, hostname visible, todo editable desde la web

## Autenticación
- **Usuarios locales** — Gestión completa de usuarios con autenticación básica (htpasswd), con fecha de caducidad opcional
- **Digest (RFC 2617)** — El navegador nunca envía la contraseña en claro, solo un hash; alternativa a Basic para usuarios locales
- **Sin autenticación local (`none`)** — Para un proxy hijo cuyo control de acceso real lo hace un proxy padre encadenado, sin duplicar usuarios en los dos lados
- **LDAP / Active Directory** — Integración con directorio externo, con test de conexión integrado y sincronización paginada
- **Kerberos / Negotiate** — Inicio de sesión único con Active Directory, sin que el navegador pida credenciales
- **Proxy padre encadenado** — Con credenciales fijas o reenviando las del cliente (`passthru`) hacia un padre que exige Digest, NTLM o Negotiate
- **Panel seguro** — Login con JWT, roles (superadmin / admin / solo lectura) y cambio de contraseña obligatorio en el primer acceso; una contraseña correcta nunca queda bloqueada por los intentos fallidos de un tercero

## Seguridad
- **SSL Bump** — Intercepta y filtra tráfico HTTPS (no solo HTTP)
- **Bloqueo HTTPS por SNI** — Bloquea dominios antes de desencriptar (ej: Facebook, YouTube por HTTPS)
- **Exclusión de dominios sensibles** — Banca, sanidad o apps con *certificate pinning* pueden excluirse del descifrado
- **Auditoría completa** — Log de todos los cambios: quién, qué, cuándo, con retención automática
- **Certificado CA** — Generación automática + descarga desde el panel, con instaladores para Windows, macOS e iOS
- **Backend sin privilegios en los dos modos** — En Docker, el backend ya no monta el socket de Docker directo: habla con él a través de un proxy de socket acotado (`docker-socket-proxy`) que bloquea build/swarm/secretos/plugins, y corre como usuario sin privilegios — igual que en modo nativo

## Operación
- **Aplicar cambios en caliente** — Valida la configuración contra Squid antes de escribirla; recarga (`squid -k reconfigure`) o reinicia solo cuando de verdad hace falta (cambio de puerto)
- **Cambio de puerto automático** — Detecta cambios de puerto y recrea el contenedor sin perder la configuración si algo falla
- **Dashboard** — Tráfico en tiempo real, top usuarios y dominios, estado del sistema
- **Histórico de logs** — Meses ya cerrados, organizados por año/mes con un resumen precalculado (usuarios, dominios, denegados), con retención configurable — separado del visor en vivo
- **Backup y migración** — Backup automático de la base de datos con retención (script listo para cron, en los dos modos de despliegue), exporta toda la configuración a JSON, o importa un `squid.conf` tradicional con un informe previo de qué se puede traer y qué no (soporta `include`)
- **Notificaciones** — Avisos por email o Telegram cuando se aplican cambios o se detecta actividad sospechosa
- **Syslog externo** — Reenvía los logs de acceso a un servidor syslog (SIEM, ELK, Splunk) además de escribirlos localmente

## Asistente de IA
- **Preguntas en lenguaje natural sobre el panel** — Responde citando de qué archivo y sección de la documentación salió la respuesta; nunca ve tu base de datos, tu `squid.conf` real ni credenciales — ver [asistente-ia.md](asistente-ia.md)
- **Búsqueda híbrida** — Combina búsqueda semántica (embeddings) y de texto completo sobre la documentación en español
- **Apagado por defecto** — Exige activarlo y configurar dos API keys (un proveedor de chat + Jina AI para los embeddings); la documentación viaja a esos servicios externos al reindexar y al preguntar

## Despliegue e idiomas
- **Dos modos de despliegue** — Con Docker (un solo comando levanta todo) o **sin Docker**, con Squid, el panel y PostgreSQL como servicios del sistema. Se elige con `DEPLOY_MODE` y el resto del producto es idéntico — ver [instalacion-nativa.md](instalacion-nativa.md)
- **Actualizar es un solo comando** — `upgrade-docker.sh` / `upgrade-nativo.sh`: backup previo, código nuevo traído de forma segura y todo reconstruido y reiniciado, preservando tu configuración — ver [actualizacion.md](actualizacion.md)
- **Actualizaciones desde el propio panel** (instalación nativa) — Avisa cuándo hay una versión nueva en GitHub y qué cambió; aprobarla —ahora o programada— nunca le da al panel web permisos nuevos, solo deja la aprobación para un mecanismo aparte que ya corría con privilegios propios — ver [actualizaciones-automaticas.md](actualizaciones-automaticas.md)
- **Panel en tres idiomas** — Español, inglés y portugués, seleccionable desde el propio panel. Los mensajes de error de la API también se traducen, y las páginas de error que ven los usuarios del proxy siguen su propio idioma — ver [idiomas.md](idiomas.md)
