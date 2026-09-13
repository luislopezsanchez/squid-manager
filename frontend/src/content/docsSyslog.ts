// Contenido del artículo "Syslog externo" de la biblioteca de
// Documentación. Ver docsActividadRed.ts para la razón de que esto viva
// aparte de los diccionarios de i18n/*.json.
export const DOC_SYSLOG: Record<'es' | 'en' | 'pt', string> = {
  es: `
## Para qué sirve

Reenvía cada línea de \`access.log\` a un SIEM o herramienta de auditoría externa, en tiempo real, a medida que ocurre -no es un reemplazo de Registros/Histórico dentro del panel, es un canal adicional para quien ya centraliza logs de toda la infraestructura en otro lado.

Es opcional: mientras esté apagado, no se manda nada a ningún lado, y apagarlo en cualquier momento no afecta a Registros ni a Histórico -son sistemas independientes.

## Configuración

Servidor y puerto de destino, protocolo (UDP o TCP), facility (la categoría estándar de syslog para poder filtrar del lado receptor) y formato del mensaje (RFC 3164, el clásico y más compatible, o RFC 5424, estructurado y con fecha ISO).

**UDP vs. TCP**: UDP es más simple pero no confirma entrega -si el destino no está escuchando, el mensaje se pierde en silencio. TCP, si falla la conexión, reintenta en el siguiente lote.

**Ejemplo de configuración**: servidor \`10.0.5.20\`, puerto \`514\` (el estándar de syslog), protocolo \`UDP\`, facility \`local0\` (para poder filtrar del lado del SIEM justo el tráfico de este proxy y no mezclarlo con otros sistemas que también mandan syslog), formato \`RFC 5424\` si el SIEM lo soporta -trae fecha en ISO 8601, más fácil de parsear que el formato clásico.

## Probar

Antes de confiar en el reenvío, el botón de prueba manda un mensaje de ejemplo con la configuración actual (guardada o no) y confirma si llegó -sin esto, un typo en la IP del destino recién se notaría cuando alguien fuera a buscar un log que nunca llegó.
`.trim(),
  en: `
## What this is for

Forwards every line of \`access.log\` to a SIEM or external audit tool, in real time, as it happens -it's not a replacement for Logs/Historical inside the panel, it's an extra channel for someone who already centralizes logs from the whole infrastructure elsewhere.

It's optional: while it's off, nothing is sent anywhere, and turning it off at any point doesn't affect Logs or Historical -they're independent systems.

## Configuration

Destination server and port, protocol (UDP or TCP), facility (the standard syslog category, to filter on the receiving end) and message format (RFC 3164, the classic and most compatible one, or RFC 5424, structured with an ISO date).

**UDP vs. TCP**: UDP is simpler but doesn't confirm delivery -if the destination isn't listening, the message is silently lost. TCP retries on the next batch if the connection fails.

**Example configuration**: server \`10.0.5.20\`, port \`514\` (the syslog standard), protocol \`UDP\`, facility \`local0\` (so the SIEM side can filter exactly this proxy's traffic without mixing it with other systems that also send syslog), format \`RFC 5424\` if the SIEM supports it -it carries an ISO 8601 date, easier to parse than the classic format.

## Test

Before relying on the forwarding, the test button sends a sample message with the current configuration (saved or not) and confirms whether it arrived -without this, a typo in the destination IP would only show up when someone went looking for a log that never arrived.
`.trim(),
  pt: `
## Para que serve

Reenvia cada linha do \`access.log\` para um SIEM ou ferramenta de auditoria externa, em tempo real, conforme acontece -não é um substituto de Registros/Histórico dentro do painel, é um canal adicional para quem já centraliza logs de toda a infraestrutura em outro lugar.

É opcional: enquanto estiver desligado, nada é enviado para lugar nenhum, e desligá-lo a qualquer momento não afeta Registros nem Histórico -são sistemas independentes.

## Configuração

Servidor e porta de destino, protocolo (UDP ou TCP), facility (a categoria padrão do syslog, para filtrar do lado receptor) e formato da mensagem (RFC 3164, o clássico e mais compatível, ou RFC 5424, estruturado e com data ISO).

**UDP vs. TCP**: UDP é mais simples mas não confirma entrega -se o destino não estiver escutando, a mensagem se perde silenciosamente. TCP, se a conexão falhar, tenta de novo no próximo lote.

**Exemplo de configuração**: servidor \`10.0.5.20\`, porta \`514\` (o padrão do syslog), protocolo \`UDP\`, facility \`local0\` (para poder filtrar do lado do SIEM justo o tráfego deste proxy sem misturar com outros sistemas que também enviam syslog), formato \`RFC 5424\` se o SIEM suportar -traz data em ISO 8601, mais fácil de interpretar que o formato clássico.

## Testar

Antes de confiar no reenvio, o botão de teste envia uma mensagem de exemplo com a configuração atual (salva ou não) e confirma se chegou -sem isso, um erro de digitação no IP de destino só seria percebido quando alguém fosse procurar um log que nunca chegou.
`.trim(),
}
