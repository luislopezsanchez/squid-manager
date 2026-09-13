// Contenido del artículo "Ancho de banda" (Delay Pools) de la biblioteca
// de Documentación. Ver docsActividadRed.ts para la razón de que esto
// viva aparte de los diccionarios de i18n/*.json.
export const DOC_ANCHO_BANDA: Record<'es' | 'en' | 'pt', string> = {
  es: `
## Para qué sirve

Limita cuánto ancho de banda puede consumir cierto tráfico -no lo bloquea, lo hace más lento-. Útil para que una descarga grande o un usuario intensivo no dejen sin enlace al resto: en vez de prohibir, se le pone un techo.

## Las clases (1 a 5)

Cada clase agrega un nivel más de granularidad sobre la anterior:

- **Clase 1**: un único límite global, compartido por todos.
- **Clase 2**: límite global + un límite por usuario individual.
- **Clase 3**: suma un límite intermedio por red (subred /24).
- **Clase 4**: límite global + límite por grupo (requiere una ACL de tipo tag).
- **Clase 5**: la más flexible -global, por red, por usuario y por tag- para políticas complejas.

Cuantos más niveles, más fino el control, pero también más parámetros que mantener: conviene elegir la clase más simple que resuelva el caso real, no la más completa por si acaso.

## Restore y límite

Cada nivel tiene dos números: **restore** (a qué velocidad se "rellena" el balde de bytes disponibles, por segundo) y **límite** (el tamaño máximo de ese balde, cuánto se puede ráfaga antes de que empiece a limitar). El panel los pide en unidades humanas (bytes/s, KB/s, MB/s) y los convierte al formato que espera Squid.

## A qué tráfico aplica

Un delay pool se asocia opcionalmente a una ACL: sin ACL, aplica a todo; con una ACL (por ejemplo, un grupo o una lista de dominios de streaming), el límite solo rige para ese tráfico puntual.

## Ejemplo concreto

Una **Clase 2** asociada a la ACL \`streaming_video\`, con:
- Global: restore \`5 MB/s\`, límite \`10 MB/s\` (el conjunto de todo el streaming nunca supera los 5 MB/s sostenidos, con ráfagas de hasta 10 MB/s).
- Por usuario: restore \`512 KB/s\`, límite \`1 MB/s\` (cada persona individual queda tope en medio megabyte por segundo sostenido).

Con esto, ver un video de a uno anda bien, pero diez personas mirando streaming a la vez no saturan el enlace completo -cada una cede lugar a las demás dentro del límite global.
`.trim(),
  en: `
## What this is for

Limits how much bandwidth certain traffic can use -it doesn't block it, it slows it down. Useful so a large download or a heavy user doesn't starve everyone else's link: instead of forbidding, a ceiling is set.

## The classes (1 to 5)

Each class adds one more level of granularity on top of the previous one:

- **Class 1**: a single global limit, shared by everyone.
- **Class 2**: global limit + a limit per individual user.
- **Class 3**: adds an intermediate per-network limit (/24 subnet).
- **Class 4**: global limit + per-group limit (requires a tag-type ACL).
- **Class 5**: the most flexible -global, per network, per user and per tag- for complex policies.

The more levels, the finer the control, but also more parameters to maintain: it's better to pick the simplest class that solves the actual case, not the most complete one just in case.

## Restore and limit

Each level has two numbers: **restore** (how fast the bucket of available bytes "refills", per second) and **limit** (the maximum size of that bucket, how much can burst before it starts throttling). The panel asks for these in human units (bytes/s, KB/s, MB/s) and converts them to the format Squid expects.

## What traffic it applies to

A delay pool is optionally tied to an ACL: without an ACL, it applies to everything; with one (for example, a group or a list of streaming domains), the limit only governs that specific traffic.

## Concrete example

A **Class 2** pool tied to the \`video_streaming\` ACL, with:
- Global: restore \`5 MB/s\`, limit \`10 MB/s\` (all streaming combined never sustains more than 5 MB/s, with bursts up to 10 MB/s).
- Per user: restore \`512 KB/s\`, limit \`1 MB/s\` (each individual person is capped at half a megabyte per second sustained).

With this, watching a video alone works fine, but ten people streaming at once don't saturate the whole link -each one yields room to the others within the global cap.
`.trim(),
  pt: `
## Para que serve

Limita quanto de banda certo tráfego pode consumir -não bloqueia, deixa mais lento-. Útil para que um download grande ou um usuário intenso não deixem o resto sem link: em vez de proibir, se coloca um teto.

## As classes (1 a 5)

Cada classe soma mais um nível de granularidade sobre a anterior:

- **Classe 1**: um único limite global, compartilhado por todos.
- **Classe 2**: limite global + um limite por usuário individual.
- **Classe 3**: soma um limite intermediário por rede (sub-rede /24).
- **Classe 4**: limite global + limite por grupo (requer uma ACL do tipo tag).
- **Classe 5**: a mais flexível -global, por rede, por usuário e por tag- para políticas complexas.

Quanto mais níveis, mais fino o controle, mas também mais parâmetros para manter: é melhor escolher a classe mais simples que resolva o caso real, não a mais completa por precaução.

## Restore e limite

Cada nível tem dois números: **restore** (a que velocidade o "balde" de bytes disponíveis se enche de novo, por segundo) e **limite** (o tamanho máximo desse balde, quanto pode rajar antes de começar a limitar). O painel pede esses valores em unidades humanas (bytes/s, KB/s, MB/s) e os converte para o formato que o Squid espera.

## A que tráfego se aplica

Um delay pool é opcionalmente associado a uma ACL: sem ACL, se aplica a tudo; com uma (por exemplo, um grupo ou uma lista de domínios de streaming), o limite vale só para esse tráfego específico.

## Exemplo concreto

Uma **Classe 2** associada à ACL \`streaming_video\`, com:
- Global: restore \`5 MB/s\`, limite \`10 MB/s\` (todo o streaming junto nunca ultrapassa 5 MB/s sustentados, com rajadas de até 10 MB/s).
- Por usuário: restore \`512 KB/s\`, limite \`1 MB/s\` (cada pessoa individual fica limitada a meio megabyte por segundo sustentado).

Com isso, assistir a um vídeo sozinho funciona bem, mas dez pessoas assistindo streaming ao mesmo tempo não saturam o link inteiro -cada uma cede espaço para as outras dentro do limite global.
`.trim(),
}
