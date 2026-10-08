# Privacidad: qué sale de tu instalación

SquidManager **no tiene telemetría ni analítica**: no envía estadísticas de uso ni datos de tu red al autor ni
a nadie. Todo lo que guarda (usuarios, ACLs, registros, auditoría, configuración) queda en tu servidor. Las
únicas conexiones salientes son estas, y todas son opcionales o las provoca una acción tuya:

| Conexión | Cuándo ocurre | Qué se envía | Cómo evitarla |
|---|---|---|---|
| **GitHub** (`api.github.com`) | Comprobación de actualizaciones (cada 6 h si está activa) | Una consulta pública de commits; no se envía ningún dato de tu servidor | Sistema → Actualizaciones → desmarcar «Comprobar automáticamente» |
| **HaGeZi** (`raw.githubusercontent.com`) | Solo si activas las listas de bloqueo (se refrescan una vez al día) | Una descarga | No activar esas categorías |
| **Proveedor de IA** (el que elijas) | Solo si configuras el Asistente de IA y haces una pregunta | La pregunta, el contexto de la documentación y, en modo agéntico, los datos que el asistente consulta de tu panel (por ejemplo usuarios o sitios) | No configurar el asistente, o usar «Ollama en tu red» (no sale de tu red) |
| **Telegram** | Solo si activas los avisos por Telegram | El texto de cada aviso | No activarlos |
| **Tu servidor XMPP** | Solo si activas los avisos por XMPP | El texto de cada aviso, al servidor de mensajería que tú indicas (normalmente interno) | No activarlos |
| **Tu servidor SMTP** | Avisos y reporte por correo | El contenido de cada correo, a los destinatarios que tú configuras | No configurar SMTP |
| **Formulario de Contacto** | Cuando alguien lo envía | Su mensaje, el email de respuesta que escriba y, si lo marca, versión/modo de despliegue/Squid/sistema. **Nunca** usuarios, direcciones ni claves | Variable `CONTACT_EMAIL` del `.env`: pon el correo de tu equipo, o déjala vacía para no enviar nada (el mensaje se guarda en tu instalación). Solo sale si hay un SMTP configurado y sale por ese SMTP |

Los usuarios locales del proxy que entran al panel (portal de autoservicio, ver
[docs/authentication.md](authentication.md#portal-de-autoservicio-de-los-usuarios-locales)) ven únicamente sus propios datos:
su consumo diario, peticiones, bloqueos, cuota, correo y grupos. No ven sitios visitados ni datos de otros usuarios, y nada de esto sale
de tu servidor.

Desde 1.0.0 las fuentes del panel se sirven desde el propio servidor (antes se pedían a Google Fonts), así que
abrir el panel ya no envía la IP del administrador a ningún tercero.

El destino actual del formulario de Contacto se muestra en la propia pantalla Contacto.
