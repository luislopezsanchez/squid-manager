// Contenido del artículo "Cuotas" de la biblioteca de Documentación.
// Ver docsActividadRed.ts para la razón de que esto viva aparte de los
// diccionarios de i18n/*.json.
export const DOC_CUOTAS: Record<'es' | 'en' | 'pt', string> = {
  es: `
## Para qué sirve

Limita cuánto puede **descargar/subir en total** un usuario (o un grupo entero) durante un periodo -diario, semanal o mensual-, no cuánto ancho de banda instantáneo usa (eso son los **Delay pools**, ver el artículo "Ancho de banda"). Una cuota mide volumen acumulado: 5 GB al mes, por ejemplo, sin importar si se consumen en una tarde o repartidos en todo el mes.

## Por usuario o por grupo

- **Por usuario**: el límite es individual, para un usuario local o LDAP puntual.
- **Por grupo (pool compartido)**: un único cupo se reparte entre **todos** los integrantes del grupo -no es "el mismo límite para cada uno", es una bolsa común que se agota más rápido cuantos más la usen. Solo admite grupos **locales**: un grupo de LDAP resuelve su membresía en vivo contra el directorio, así que no hay de dónde sumar el consumo de cada integrante.

Un usuario puede tener cuota individual **y** pertenecer a un grupo con pool compartido al mismo tiempo -son independientes, y se aplica la que se agote primero.

Si lo que se quiere no es un cupo compartido sino darle a cada integrante de un grupo **su propia** cuota individual de una sola vez (en vez de crear el pool común), está el botón **"Por miembro…"** en la fila del grupo: aplica la misma cuota, pero como cuota individual de cada uno, reemplazando la que ya tuvieran.

## Al agotarse: cortar o limitar

- **Cortar**: deshabilita la cuenta (o a todos los integrantes, si es cuota de grupo) hasta el próximo periodo -mismo efecto que deshabilitarla a mano en Usuarios.
- **Limitar velocidad**: en vez de cortar el acceso, crea automáticamente un Delay pool con el límite de velocidad indicado, aplicado solo a ese usuario o grupo.

En ambos casos se revierte solo, automáticamente, al empezar el siguiente periodo -no hace falta reactivar nada a mano.

## Cómo se mide el consumo

El consumo se calcula leyendo el access.log de Squid cada 15 segundos, no al instante -tras cruzar el límite puede haber un desfase corto (unos segundos) antes de que se aplique la acción. La columna "En riesgo (≥80%)" del panel avisa **antes** de que se corte o limite nada, para poder actuar con margen.

## Ejemplo

Un grupo local \`ventas\` con un pool compartido de 50 GB mensuales: entre los 8 integrantes del grupo pueden consumir esos 50 GB como quieran repartidos, y al agotarse (acción "Cortar") los 8 quedan deshabilitados hasta el 1º del mes siguiente. Si en cambio se quisiera que cada uno de esos 8 tuviera sus propios 50 GB individuales, se usaría "Por miembro…" en vez del pool compartido.
`.trim(),
  en: `
## What this is for

Limits how much a user (or an entire group) can **download/upload in total** during a period -daily, weekly or monthly-, not how much instantaneous bandwidth it uses (that's **Delay pools**, see the "Bandwidth" article). A quota measures accumulated volume: 5 GB per month, for example, regardless of whether it's used up in one afternoon or spread across the whole month.

## Per user or per group

- **Per user**: the limit is individual, for a specific local or LDAP user.
- **Per group (shared pool)**: a single quota is shared among **all** the group's members -it's not "the same limit for each one", it's a common pool that runs out faster the more people use it. Only supports **local** groups: an LDAP group resolves its membership live against the directory, so there's nowhere to add up each member's consumption from.

A user can have an individual quota **and** belong to a group with a shared pool at the same time -they're independent, and whichever runs out first is the one that applies.

If what's wanted isn't a shared pool but giving each group member **their own** individual quota at once (instead of creating the common pool), there's the **"Per member…"** button on the group's row: it applies the same quota, but as each member's own individual quota, replacing whatever they already had.

## When it runs out: cut or throttle

- **Cut**: disables the account (or all members, for a group quota) until the next period -same effect as disabling it by hand in Users.
- **Throttle**: instead of cutting access, it automatically creates a Delay pool with the given speed limit, applied only to that user or group.

In both cases it reverts on its own, automatically, when the next period starts -nothing needs to be reactivated by hand.

## How consumption is measured

Consumption is calculated by reading Squid's access.log every 15 seconds, not instantly -after crossing the limit there can be a short lag (a few seconds) before the action is applied. The "At risk (≥80%)" column in the panel warns **before** anything gets cut or throttled, so there's margin to act.

## Example

A local group \`sales\` with a shared pool of 50 GB per month: the group's 8 members can consume those 50 GB however they split it, and once it runs out (with the "Cut" action) all 8 are disabled until the 1st of the next month. If instead each of those 8 should have their own individual 50 GB, "Per member…" would be used instead of the shared pool.
`.trim(),
  pt: `
## Para que serve

Limita quanto um usuário (ou um grupo inteiro) pode **baixar/enviar no total** durante um período -diário, semanal ou mensal-, não quanta largura de banda instantânea ele usa (isso são os **Delay pools**, veja o artigo "Largura de banda"). Uma cota mede volume acumulado: 5 GB por mês, por exemplo, sem importar se é consumido numa tarde ou distribuído ao longo do mês todo.

## Por usuário ou por grupo

- **Por usuário**: o limite é individual, para um usuário local ou LDAP específico.
- **Por grupo (pool compartilhado)**: uma única cota é dividida entre **todos** os integrantes do grupo -não é "o mesmo limite para cada um", é uma bolsa comum que se esgota mais rápido quanto mais gente a usa. Só admite grupos **locais**: um grupo LDAP resolve sua associação em tempo real consultando o diretório, então não há de onde somar o consumo de cada integrante.

Um usuário pode ter cota individual **e** pertencer a um grupo com pool compartilhado ao mesmo tempo -são independentes, e vale a que se esgotar primeiro.

Se o que se quer não é uma cota compartilhada, mas sim dar a cada integrante de um grupo **sua própria** cota individual de uma vez (em vez de criar o pool comum), há o botão **"Por integrante…"** na linha do grupo: aplica a mesma cota, mas como cota individual de cada um, substituindo a que já tivessem.

## Ao se esgotar: cortar ou limitar

- **Cortar**: desabilita a conta (ou todos os integrantes, se for cota de grupo) até o próximo período -mesmo efeito de desabilitá-la manualmente em Usuários.
- **Limitar velocidade**: em vez de cortar o acesso, cria automaticamente um Delay pool com o limite de velocidade indicado, aplicado só a esse usuário ou grupo.

Em ambos os casos, reverte sozinho, automaticamente, ao começar o próximo período -não é preciso reativar nada manualmente.

## Como o consumo é medido

O consumo é calculado lendo o access.log do Squid a cada 15 segundos, não instantaneamente -depois de ultrapassar o limite pode haver uma pequena defasagem (alguns segundos) antes que a ação seja aplicada. A coluna "Em risco (≥80%)" do painel avisa **antes** que algo seja cortado ou limitado, para dar margem de ação.

## Exemplo

Um grupo local \`vendas\` com um pool compartilhado de 50 GB mensais: entre os 8 integrantes do grupo, podem consumir esses 50 GB como quiserem dividir, e ao se esgotar (ação "Cortar") os 8 ficam desabilitados até o dia 1º do mês seguinte. Se em vez disso cada um desses 8 devesse ter seus próprios 50 GB individuais, usaria-se "Por integrante…" em vez do pool compartilhado.
`.trim(),
}
