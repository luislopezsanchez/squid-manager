// Contenido del artículo "Notificaciones" de la biblioteca de
// Documentación. Ver docsActividadRed.ts para la razón de que esto viva
// aparte de los diccionarios de i18n/*.json.
export const DOC_NOTIFICACIONES: Record<'es' | 'en' | 'pt', string> = {
  es: `
## Para qué sirve

Avisa por email, Telegram o XMPP (chat interno) cuando pasa algo relevante en el panel -sin tener que estar mirando Auditoría todo el día para enterarse.

## Tres canales, independientes entre sí

- **Email**: usa el servidor SMTP configurado en Sistema > SMTP -el mismo que usa Contacto, para no tener que configurar el correo saliente dos veces en dos lugares distintos.
- **Telegram**: un bot propio (token) y el ID del chat o canal donde se mandan los avisos.
- **XMPP**: el chat interno de tu empresa (Openfire, Prosody, ejabberd…). SquidManager no instala ningún servidor: se conecta como un cliente más al que ya tengas. Indicas el servidor (IP o nombre) y el puerto (5222 con STARTTLS, 5223 con SSL), la cuenta emisora con su contraseña (por ejemplo \`squid@miempresa.local\`, que crea tu administrador del chat), los destinatarios (uno o varios usuarios) y, si quieres, una sala de grupo. Si tu servidor usa un certificado propio, desmarca «Verificar certificado del servidor».

Cada uno se activa por separado, y cada uno tiene su propio botón de prueba -antes de depender de una notificación real, conviene confirmar que efectivamente llega.

## Qué eventos avisan

Cada tipo de evento se activa o desactiva por separado: aplicar cambios, cambios de usuarios, cambios de ACLs, cambios de reglas de acceso, y alertas de seguridad (por ejemplo, varios inicios de sesión fallidos seguidos). No hace falta activarlos todos -conviene elegir los que de verdad importa saber en el momento, y dejar el resto para revisar en Auditoría cuando haga falta.

## Ejemplo

- **Email**: destinatarios \`red@miempresa.com, seguridad@miempresa.com\` (varios, separados por coma), con "Alertas de seguridad" y "Aplicar cambios" activados.
- **Telegram**: bot token (se pega una sola vez, no se vuelve a mostrar) y chat ID \`-1001234567890\` (el ID de un grupo/canal, no un usuario individual, para que el aviso lo vea todo el equipo).

## Avisos de cuota y de sitios bloqueados

Además de los cambios y las alertas de seguridad, puedes recibir dos avisos más:

- **Cuota agotada**: cuando un usuario o grupo llega al límite de su cuota (se le corta el acceso o se le baja la velocidad). Ejemplo: «El usuario ana llegó a su cuota diaria: 500 MB de 500 MB. Se ha cortado el acceso».
- **Intentos de entrar a sitios bloqueados**: cuando un usuario acumula cierto número de peticiones bloqueadas en 10 minutos (por defecto 10; se cambia en la misma pantalla). El aviso dice quién es y a qué sitios intentó entrar. Se manda una sola vez por usuario y por hora.

## Correos con formato

Todos los avisos por correo llegan con diseño: una franja de color según la gravedad, lo ocurrido en una frase, **qué significa**, **qué puedes hacer** y la fecha y hora en la zona horaria de la instalación. El idioma es el del panel cuando guardaste la configuración.

## Reporte diario por correo

Un resumen de las últimas 24 horas que llega a los administradores con correo: usuarios activos, sitios, datos y peticiones, los que más navegaron, los sitios bloqueados más intentados, cuotas agotadas y alertas.

1. Configura el servidor en **Sistema → SMTP**.
2. Pon un correo en tu cuenta de administrador (**Administradores**).
3. Activa «Reporte diario», elige la hora (por defecto 23:55) y guarda.

Si falta alguno de los dos requisitos, la casilla queda bloqueada y la pantalla dice cuál. El botón **Enviar el reporte ahora** manda uno de prueba.
`.trim(),
  en: `
## What this is for

Alerts by email, Telegram or XMPP (internal chat) when something relevant happens in the panel -without having to watch Audit all day to find out.

## Three channels, independent of each other

- **Email**: uses the SMTP server configured under System > SMTP -the same one Contact uses, so outgoing mail doesn't need to be set up twice in two different places.
- **Telegram**: your own bot (token) and the chat or channel ID where alerts are sent.
- **XMPP**: your company's internal chat (Openfire, Prosody, ejabberd…). SquidManager does not install any server: it connects as one more client to the one you already have. You enter the server (IP or name) and port (5222 with STARTTLS, 5223 with SSL), the sender account and its password (for example \`squid@mycompany.local\`, created by your chat administrator), the recipients (one or several users) and, optionally, a group room. If your server uses a self-signed certificate, untick «Verify the server certificate».

Each one is turned on separately, and each has its own test button -before relying on a real notification, it's worth confirming it actually arrives.

## Which events notify

Each event type is turned on or off separately: applying changes, user changes, ACL changes, access rule changes, and security alerts (for example, several failed logins in a row). There's no need to enable all of them -it's better to pick the ones that genuinely matter to know about right away, and leave the rest to review in Audit when needed.

## Example

- **Email**: recipients \`network@mycompany.com, security@mycompany.com\` (several, comma-separated), with "Security alerts" and "Apply changes" enabled.
- **Telegram**: bot token (pasted once, never shown again) and chat ID \`-1001234567890\` (a group/channel ID, not an individual user, so the whole team sees the alert).

## Quota and blocked-site notices

Besides changes and security alerts you can receive two more notices:

- **Quota reached**: when a user or group hits its quota limit (access is cut or speed reduced). Example: "User ana reached her daily quota: 500 MB of 500 MB. Access has been cut".
- **Attempts to reach blocked sites**: when a user accumulates a number of blocked requests in 10 minutes (10 by default; changed on the same screen). The notice says who and which sites they tried. It is sent once per user per hour.

## Formatted emails

All email notices arrive designed: a colored band by severity, what happened in one sentence, **what it means**, **what you can do** and the date and time in the installation's time zone. The language is the panel's when you saved the settings.

## Daily report by email

A summary of the last 24 hours sent to administrators with an email: active users, sites, data and requests, top browsers, most attempted blocked sites, exhausted quotas and alerts.

1. Configure the server in **System → SMTP**.
2. Put an email on your administrator account (**Administrators**).
3. Enable "Daily report", pick the time (23:55 by default) and save.

If either requirement is missing the checkbox is locked and the screen says which one. **Send the report now** sends a test.
`.trim(),
  pt: `
## Para que serve

Avisa por e-mail, Telegram ou XMPP (chat interno) quando algo relevante acontece no painel -sem precisar ficar olhando Auditoria o dia todo para saber.

## Três canais, independentes entre si

- **E-mail**: usa o servidor SMTP configurado em Sistema > SMTP -o mesmo que Contato usa, para não precisar configurar o e-mail de saída duas vezes em dois lugares diferentes.
- **Telegram**: um bot próprio (token) e o ID do chat ou canal para onde os avisos são enviados.
- **XMPP**: o chat interno da sua empresa (Openfire, Prosody, ejabberd…). O SquidManager não instala nenhum servidor: conecta-se como mais um cliente ao que você já tem. Você informa o servidor (IP ou nome) e a porta (5222 com STARTTLS, 5223 com SSL), a conta emissora com sua senha (por exemplo \`squid@suaempresa.local\`, criada pelo administrador do chat), os destinatários (um ou vários usuários) e, se quiser, uma sala de grupo. Se o servidor usar certificado próprio, desmarque «Verificar certificado do servidor».

Cada um é ativado separadamente, e cada um tem seu próprio botão de teste -antes de depender de uma notificação real, vale confirmar que ela realmente chega.

## Quais eventos avisam

Cada tipo de evento é ativado ou desativado separadamente: aplicar alterações, mudanças de usuários, mudanças de ACLs, mudanças de regras de acesso, e alertas de segurança (por exemplo, vários logins malsucedidos seguidos). Não é preciso ativar todos -o melhor é escolher os que realmente importa saber na hora, e deixar o resto para revisar em Auditoria quando precisar.

## Exemplo

- **E-mail**: destinatários \`rede@minhaempresa.com, seguranca@minhaempresa.com\` (vários, separados por vírgula), com "Alertas de segurança" e "Aplicar alterações" ativados.
- **Telegram**: token do bot (colado uma única vez, não é mostrado de novo) e chat ID \`-1001234567890\` (o ID de um grupo/canal, não de um usuário individual, para que o aviso seja visto por toda a equipe).

## Avisos de cota e de sites bloqueados

Além das mudanças e dos alertas de segurança, você pode receber mais dois avisos:

- **Cota esgotada**: quando um usuário ou grupo atinge o limite da cota (o acesso é cortado ou a velocidade reduzida). Exemplo: «O usuário ana atingiu sua cota diária: 500 MB de 500 MB. O acesso foi cortado».
- **Tentativas de acessar sites bloqueados**: quando um usuário acumula certo número de requisições bloqueadas em 10 minutos (10 por padrão; muda na mesma tela). O aviso diz quem é e quais sites tentou acessar. É enviado uma vez por usuário por hora.

## E-mails com formato

Todos os avisos por e-mail chegam com design: uma faixa de cor conforme a gravidade, o ocorrido em uma frase, **o que significa**, **o que você pode fazer** e a data e hora no fuso da instalação. O idioma é o do painel quando você salvou a configuração.

## Relatório diário por e-mail

Um resumo das últimas 24 horas enviado aos administradores com e-mail: usuários ativos, sites, dados e requisições, quem mais navegou, sites bloqueados mais tentados, cotas esgotadas e alertas.

1. Configure o servidor em **Sistema → SMTP**.
2. Coloque um e-mail na sua conta de administrador (**Administradores**).
3. Ative «Relatório diário», escolha o horário (23:55 por padrão) e salve.

Se faltar um dos requisitos, a caixa fica bloqueada e a tela diz qual. **Enviar o relatório agora** envia um de teste.
`.trim(),
}
