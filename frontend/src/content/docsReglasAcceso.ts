// Contenido del artículo "Reglas de acceso" de la biblioteca de
// Documentación. Ver docsActividadRed.ts para la razón de que esto viva
// aparte de los diccionarios de i18n/*.json.
export const DOC_REGLAS_ACCESO: Record<'es' | 'en' | 'pt', string> = {
  es: `
## Para qué sirve

Es donde las ACLs se convierten en política real: una regla dice **permitir** o **denegar** el tráfico que coincide con una o más ACLs. Una ACL sola (ver esa sección) no bloquea nada -recién cuando una regla la referencia, empieza a tener efecto.

## El orden importa

Squid evalúa las reglas en orden, de arriba hacia abajo, y aplica la **primera que coincide** -no seguí buscando algo "más específico" más abajo. Una regla "denegar todo" puesta primero deja sin efecto a cualquier "permitir" que venga después. El orden se cambia arrastrando las reglas en la lista.

## Combinar ACLs en una regla

Una regla puede citar varias ACLs a la vez (por ejemplo, un grupo de usuarios y un horario): todas tienen que cumplirse para que la regla aplique. Anteponer \`!\` a una ACL invierte la condición ("que NO sea este grupo", "que NO sea este horario").

## Qué pasa con el tráfico HTTPS

Una regla que cita una ACL de dominio se duplica automáticamente por dentro para aplicar también sobre el nombre de dominio que viaja en el saludo TLS (SNI) -sin eso, bloquear un dominio solo afectaría al tráfico HTTP sin cifrar, y hoy casi todo es HTTPS. Esto es automático, no hay que crear una regla aparte para HTTPS.
`.trim(),
  en: `
## What this is for

This is where ACLs become real policy: a rule says **allow** or **deny** traffic that matches one or more ACLs. An ACL on its own (see that section) blocks nothing -only once a rule references it does it start to take effect.

## Order matters

Squid evaluates rules in order, top to bottom, and applies the **first one that matches** -it doesn't keep looking for something "more specific" further down. A "deny all" rule placed first cancels out any "allow" that comes after it. The order is changed by dragging rules in the list.

## Combining ACLs in a rule

A rule can cite several ACLs at once (for example, a user group and a time window): all of them have to match for the rule to apply. Prefixing an ACL with \`!\` inverts the condition ("NOT this group", "NOT this time window").

## What happens with HTTPS traffic

A rule that cites a domain ACL is automatically duplicated internally to also apply to the domain name that travels in the TLS handshake (SNI) -without that, blocking a domain would only affect unencrypted HTTP traffic, and today almost everything is HTTPS. This is automatic; there's no need to create a separate rule for HTTPS.
`.trim(),
  pt: `
## Para que serve

É onde as ACLs viram política de verdade: uma regra diz **permitir** ou **negar** o tráfego que corresponde a uma ou mais ACLs. Uma ACL sozinha (ver essa seção) não bloqueia nada -só quando uma regra a referencia é que ela passa a ter efeito.

## A ordem importa

O Squid avalia as regras em ordem, de cima para baixo, e aplica a **primeira que corresponder** -não continua procurando algo "mais específico" mais abaixo. Uma regra "negar tudo" colocada primeiro anula qualquer "permitir" que venha depois. A ordem é alterada arrastando as regras na lista.

## Combinar ACLs em uma regra

Uma regra pode citar várias ACLs ao mesmo tempo (por exemplo, um grupo de usuários e um horário): todas precisam ser satisfeitas para a regra se aplicar. Colocar \`!\` antes de uma ACL inverte a condição ("que NÃO seja este grupo", "que NÃO seja este horário").

## O que acontece com o tráfego HTTPS

Uma regra que cita uma ACL de domínio é duplicada automaticamente por dentro para também se aplicar sobre o nome de domínio que viaja no handshake TLS (SNI) -sem isso, bloquear um domínio só afetaria o tráfego HTTP sem criptografia, e hoje quase tudo é HTTPS. Isso é automático, não é preciso criar uma regra separada para HTTPS.
`.trim(),
}
