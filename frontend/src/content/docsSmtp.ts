// Contenido del artículo "SMTP" de la biblioteca de Documentación. Ver
// docsActividadRed.ts para la razón de que esto viva aparte de los
// diccionarios de i18n/*.json.
export const DOC_SMTP: Record<'es' | 'en' | 'pt', string> = {
  es: `
## Para qué sirve

El servidor de correo saliente **único** de todo SquidManager: lo usan tanto las alertas de **Notificaciones** como el formulario de **Contacto**, así el correo se configura una sola vez, no dos veces en dos lugares distintos.

## Campos, con ejemplo

- **Servidor SMTP**: la dirección del relay de correo. Ejemplo: \`smtp.gmail.com\`.
- **Puerto**: \`587\` para STARTTLS (Gmail, Outlook, la mayoría de servicios) o \`465\` para SSL/TLS implícito (algunos servicios lo piden así).
- **Cifrado**: STARTTLS o SSL/TLS implícito -tienen que coincidir con lo que el servidor espera en ese puerto; si no coinciden, la conexión falla.
- **Usuario**: la cuenta que autentica contra el servidor. Ejemplo: \`alertas@miempresa.com\`.
- **Contraseña**: se guarda cifrada. Una vez guardada no se vuelve a mostrar -al editar, dejar el campo vacío mantiene la que ya había.
- **Remitente (From)**: qué dirección aparece como emisor del correo. Ejemplo: \`alertas@miempresa.com\` o \`no-responder@miempresa.com\`.

## Con Gmail específicamente

Gmail no acepta la contraseña normal de la cuenta por SMTP -hay que generar una **contraseña de aplicación** (16 caracteres) desde la configuración de seguridad de la cuenta de Google, y usar esa en el campo de contraseña.

## Probar antes de confiar

El botón de prueba manda un correo real a un destinatario que se indica en el momento, usando la configuración actual (guardada o no) -así se confirma que las credenciales y el puerto funcionan antes de depender de una alerta real que nunca llegue.
`.trim(),
  en: `
## What this is for

The **single** outgoing mail server for all of SquidManager: used by both **Notifications** alerts and the **Contact** form, so mail only needs to be configured once, not twice in two different places.

## Fields, with an example

- **SMTP server**: the mail relay's address. Example: \`smtp.gmail.com\`.
- **Port**: \`587\` for STARTTLS (Gmail, Outlook, most services) or \`465\` for implicit SSL/TLS (some services require this).
- **Encryption**: STARTTLS or implicit SSL/TLS -has to match what the server expects on that port; if they don't match, the connection fails.
- **User**: the account that authenticates against the server. Example: \`alerts@mycompany.com\`.
- **Password**: stored encrypted. Once saved it isn't shown again -when editing, leaving the field empty keeps the existing one.
- **Sender (From)**: which address shows up as the mail's sender. Example: \`alerts@mycompany.com\` or \`no-reply@mycompany.com\`.

## With Gmail specifically

Gmail doesn't accept the account's regular password over SMTP -an **app password** (16 characters) has to be generated from the Google account's security settings, and used in the password field.

## Test before relying on it

The test button sends a real email to a recipient specified on the spot, using the current configuration (saved or not) -confirming credentials and port work before depending on a real alert that never arrives.
`.trim(),
  pt: `
## Para que serve

O servidor de e-mail de saída **único** de todo o SquidManager: usado tanto pelos alertas de **Notificações** quanto pelo formulário de **Contato**, assim o e-mail é configurado uma única vez, não duas vezes em dois lugares diferentes.

## Campos, com exemplo

- **Servidor SMTP**: o endereço do relay de e-mail. Exemplo: \`smtp.gmail.com\`.
- **Porta**: \`587\` para STARTTLS (Gmail, Outlook, a maioria dos serviços) ou \`465\` para SSL/TLS implícito (alguns serviços exigem assim).
- **Criptografia**: STARTTLS ou SSL/TLS implícito -precisa coincidir com o que o servidor espera nessa porta; se não coincidir, a conexão falha.
- **Usuário**: a conta que autentica no servidor. Exemplo: \`alertas@minhaempresa.com\`.
- **Senha**: é salva criptografada. Uma vez salva não é mostrada de novo -ao editar, deixar o campo vazio mantém a que já havia.
- **Remetente (From)**: qual endereço aparece como remetente do e-mail. Exemplo: \`alertas@minhaempresa.com\` ou \`nao-responder@minhaempresa.com\`.

## Com o Gmail especificamente

O Gmail não aceita a senha normal da conta por SMTP -é preciso gerar uma **senha de aplicativo** (16 caracteres) nas configurações de segurança da conta do Google, e usar essa no campo de senha.

## Testar antes de confiar

O botão de teste envia um e-mail real para um destinatário indicado na hora, usando a configuração atual (salva ou não) -assim se confirma que as credenciais e a porta funcionam antes de depender de um alerta real que nunca chega.
`.trim(),
}
