// Contenido del artículo "Notificaciones" de la biblioteca de
// Documentación. Ver docsActividadRed.ts para la razón de que esto viva
// aparte de los diccionarios de i18n/*.json.
export const DOC_NOTIFICACIONES: Record<'es' | 'en' | 'pt', string> = {
  es: `
## Para qué sirve

Avisa por email o Telegram cuando pasa algo relevante en el panel -sin tener que estar mirando Auditoría todo el día para enterarse.

## Dos canales, independientes entre sí

- **Email**: usa el servidor SMTP configurado en Sistema > SMTP -el mismo que usa Contacto, para no tener que configurar el correo saliente dos veces en dos lugares distintos.
- **Telegram**: un bot propio (token) y el ID del chat o canal donde se mandan los avisos.

Cada uno se activa por separado, y cada uno tiene su propio botón de prueba -antes de depender de una notificación real, conviene confirmar que efectivamente llega.

## Qué eventos avisan

Cada tipo de evento se activa o desactiva por separado: aplicar cambios, cambios de usuarios, cambios de ACLs, cambios de reglas de acceso, y alertas de seguridad (por ejemplo, varios inicios de sesión fallidos seguidos). No hace falta activarlos todos -conviene elegir los que de verdad importa saber en el momento, y dejar el resto para revisar en Auditoría cuando haga falta.

## Ejemplo

- **Email**: destinatarios \`red@miempresa.com, seguridad@miempresa.com\` (varios, separados por coma), con "Alertas de seguridad" y "Aplicar cambios" activados.
- **Telegram**: bot token (se pega una sola vez, no se vuelve a mostrar) y chat ID \`-1001234567890\` (el ID de un grupo/canal, no un usuario individual, para que el aviso lo vea todo el equipo).
`.trim(),
  en: `
## What this is for

Alerts by email or Telegram when something relevant happens in the panel -without having to watch Audit all day to find out.

## Two channels, independent of each other

- **Email**: uses the SMTP server configured under System > SMTP -the same one Contact uses, so outgoing mail doesn't need to be set up twice in two different places.
- **Telegram**: your own bot (token) and the chat or channel ID where alerts are sent.

Each one is turned on separately, and each has its own test button -before relying on a real notification, it's worth confirming it actually arrives.

## Which events notify

Each event type is turned on or off separately: applying changes, user changes, ACL changes, access rule changes, and security alerts (for example, several failed logins in a row). There's no need to enable all of them -it's better to pick the ones that genuinely matter to know about right away, and leave the rest to review in Audit when needed.

## Example

- **Email**: recipients \`network@mycompany.com, security@mycompany.com\` (several, comma-separated), with "Security alerts" and "Apply changes" enabled.
- **Telegram**: bot token (pasted once, never shown again) and chat ID \`-1001234567890\` (a group/channel ID, not an individual user, so the whole team sees the alert).
`.trim(),
  pt: `
## Para que serve

Avisa por e-mail ou Telegram quando algo relevante acontece no painel -sem precisar ficar olhando Auditoria o dia todo para saber.

## Dois canais, independentes entre si

- **E-mail**: usa o servidor SMTP configurado em Sistema > SMTP -o mesmo que Contato usa, para não precisar configurar o e-mail de saída duas vezes em dois lugares diferentes.
- **Telegram**: um bot próprio (token) e o ID do chat ou canal para onde os avisos são enviados.

Cada um é ativado separadamente, e cada um tem seu próprio botão de teste -antes de depender de uma notificação real, vale confirmar que ela realmente chega.

## Quais eventos avisam

Cada tipo de evento é ativado ou desativado separadamente: aplicar alterações, mudanças de usuários, mudanças de ACLs, mudanças de regras de acesso, e alertas de segurança (por exemplo, vários logins malsucedidos seguidos). Não é preciso ativar todos -o melhor é escolher os que realmente importa saber na hora, e deixar o resto para revisar em Auditoria quando precisar.

## Exemplo

- **E-mail**: destinatários \`rede@minhaempresa.com, seguranca@minhaempresa.com\` (vários, separados por vírgula), com "Alertas de segurança" e "Aplicar alterações" ativados.
- **Telegram**: token do bot (colado uma única vez, não é mostrado de novo) e chat ID \`-1001234567890\` (o ID de um grupo/canal, não de um usuário individual, para que o aviso seja visto por toda a equipe).
`.trim(),
}
