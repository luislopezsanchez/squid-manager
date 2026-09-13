// Contenido del artículo "Grupos" de la biblioteca de Documentación.
// Ver docsActividadRed.ts para la razón de que esto viva aparte de los
// diccionarios de i18n/*.json.
export const DOC_GRUPOS: Record<'es' | 'en' | 'pt', string> = {
  es: `
## Para qué sirve

Agrupa usuarios (locales o LDAP, mezclados) para poder referenciarlos juntos en una **Regla de acceso** -por ejemplo, "el grupo Gerencia no tiene restricciones de horario" o "el grupo Invitados solo navega a sitios permitidos"- en vez de tener que nombrar usuario por usuario en cada regla.

## Miembros

Se agregan por nombre de usuario, con autocompletado que combina usuarios locales y LDAP. Un mismo usuario puede estar en varios grupos a la vez.

## "Sin descifrar HTTPS para este grupo"

Un grupo puede marcarse para que su tráfico HTTPS **no se descifre** (no pase por SSL Bump), aunque el resto de la red sí lo tenga activado. Pensado para excepciones legítimas -por ejemplo, dispositivos que no aceptan el certificado del proxy, o tráfico donde descifrar generaría más problemas que beneficios.

Importante: esto exime del descifrado, **no** de las reglas de bloqueo por dominio -si el grupo tiene un sitio bloqueado, sigue bloqueado igual, solo que Squid lo hace mirando el SNI (el nombre de dominio que viaja sin cifrar en el saludo TLS) en vez de la URL completa.

## Ejemplo

Un grupo \`gerencia\`, descripción "Directorio y gerentes de área", con los miembros \`jrodriguez\`, \`mgomez\`, \`acastro\`. Ese nombre (\`gerencia\`) es después el que se usa en **Reglas de acceso** para eximirlos de una restricción, por ejemplo \`allow gerencia\` antes de una regla \`deny\` más general.
`.trim(),
  en: `
## What this is for

Groups users (local or LDAP, mixed) so they can be referenced together in an **Access rule** -for example, "the Management group has no time restrictions" or "the Guests group can only browse to allowed sites"- instead of having to name each user individually in every rule.

## Members

Added by username, with autocomplete that combines local and LDAP users. The same user can belong to several groups at once.

## "Don't decrypt HTTPS for this group"

A group can be marked so its HTTPS traffic **isn't decrypted** (doesn't go through SSL Bump), even if the rest of the network has it enabled. Meant for legitimate exceptions -for example, devices that don't accept the proxy's certificate, or traffic where decrypting would cause more problems than it solves.

Important: this exempts from decryption, **not** from domain-blocking rules -if the group has a site blocked, it stays blocked, just that Squid checks it by looking at the SNI (the domain name that travels unencrypted in the TLS handshake) instead of the full URL.

## Example

A group \`management\`, description "Directors and area managers", with members \`jrodriguez\`, \`mgomez\`, \`acastro\`. That name (\`management\`) is then what's used in **Access rules** to exempt them from a restriction, for example \`allow management\` before a more general \`deny\` rule.
`.trim(),
  pt: `
## Para que serve

Agrupa usuários (locais ou LDAP, misturados) para poder referenciá-los juntos em uma **Regra de acesso** -por exemplo, "o grupo Gerência não tem restrições de horário" ou "o grupo Convidados só navega para sites permitidos"- em vez de precisar nomear usuário por usuário em cada regra.

## Membros

São adicionados pelo nome de usuário, com autocompletar que combina usuários locais e LDAP. Um mesmo usuário pode estar em vários grupos ao mesmo tempo.

## "Não descriptografar HTTPS para este grupo"

Um grupo pode ser marcado para que seu tráfego HTTPS **não seja descriptografado** (não passe pelo SSL Bump), mesmo que o resto da rede tenha isso ativado. Pensado para exceções legítimas -por exemplo, dispositivos que não aceitam o certificado do proxy, ou tráfego onde descriptografar geraria mais problemas do que benefícios.

Importante: isso isenta da descriptografia, **não** das regras de bloqueio por domínio -se o grupo tem um site bloqueado, ele continua bloqueado, só que o Squid verifica olhando o SNI (o nome de domínio que viaja sem criptografia no handshake TLS) em vez da URL completa.

## Exemplo

Um grupo \`gerencia\`, descrição "Diretoria e gerentes de área", com os membros \`jrodriguez\`, \`mgomez\`, \`acastro\`. Esse nome (\`gerencia\`) é depois o usado em **Regras de acesso** para isentá-los de uma restrição, por exemplo \`allow gerencia\` antes de uma regra \`deny\` mais geral.
`.trim(),
}
