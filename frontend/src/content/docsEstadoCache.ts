// Contenido del artículo "Estado del caché" de la biblioteca de
// Documentación. Ver docsActividadRed.ts para la razón de que esto viva
// aparte de los diccionarios de i18n/*.json.
export const DOC_ESTADO_CACHE: Record<'es' | 'en' | 'pt', string> = {
  es: `
## Para qué sirve

Muestra qué tan bien está funcionando la caché de Squid -no el tráfico en sí (eso es Actividad de red), sino la eficiencia con la que Squid evita volver a descargar lo que ya descargó antes. Los datos vienen directo del Cache Manager de Squid, no de \`access.log\`.

## Aciertos (hit ratio)

El porcentaje de peticiones que Squid pudo responder desde la caché, en vez de ir a buscarlas de nuevo a Internet. Se muestra en dos ventanas (5 y 60 minutos) para distinguir un bache puntual de una tendencia real. El color de cada tarjeta cambia según qué tan sano es el número -no es una alarma configurable, es solo para que el ojo vaya directo a lo que conviene mirar dos veces.

Un aciertos bajo no es necesariamente un problema: mucho del tráfico moderno (streaming, APIs, contenido personalizado) no es cacheable por diseño, sin importar qué tan bien configurada esté la caché.

## Memoria y disco

Cuánto de la caché vive en memoria RAM (más rápido, más chico) y cuánto en disco (más grande, más lento) -y qué porcentaje de la capacidad configurada está en uso. Un disco cerca del 100% no rompe nada -Squid empieza a descartar lo menos usado (LRU)- pero sí reduce la eficiencia si el objeto descartado se vuelve a pedir enseguida.

## Versión y actividad

Versión de Squid en ejecución, tiempo desde el último arranque, clientes activos y total de peticiones recibidas -un panorama rápido de "¿está vivo, y hace cuánto?" sin tener que entrar a los logs.
`.trim(),
  en: `
## What this is for

Shows how well Squid's cache is performing -not the traffic itself (that's Network Activity), but how efficiently Squid avoids re-downloading what it already fetched before. The data comes directly from Squid's Cache Manager, not from \`access.log\`.

## Hit ratio

The percentage of requests Squid could answer from cache, instead of going out to fetch them again. Shown over two windows (5 and 60 minutes) to tell apart a momentary dip from a real trend. Each card's color changes based on how healthy the number is -not a configurable alarm, just so the eye goes straight to what's worth a second look.

A low hit ratio isn't necessarily a problem: a lot of modern traffic (streaming, APIs, personalized content) isn't cacheable by design, no matter how well the cache is configured.

## Memory and disk

How much of the cache lives in RAM (faster, smaller) and how much on disk (bigger, slower) -and what percentage of the configured capacity is in use. A disk near 100% doesn't break anything -Squid starts discarding the least-used items (LRU)- but it does hurt efficiency if a discarded object gets requested again right away.

## Version and activity

The running Squid version, time since last startup, active clients and total requests received -a quick "is it alive, and for how long" overview without having to dig into logs.
`.trim(),
  pt: `
## Para que serve

Mostra o quão bem o cache do Squid está funcionando -não o tráfego em si (isso é Atividade de rede), mas a eficiência com que o Squid evita baixar de novo o que já baixou antes. Os dados vêm direto do Cache Manager do Squid, não do \`access.log\`.

## Taxa de acertos

A porcentagem de requisições que o Squid conseguiu responder a partir do cache, em vez de buscá-las de novo na Internet. É mostrada em duas janelas (5 e 60 minutos) para distinguir uma queda pontual de uma tendência real. A cor de cada cartão muda conforme o quão saudável é o número -não é um alarme configurável, é só para o olho ir direto ao que vale a pena olhar duas vezes.

Uma taxa de acertos baixa não é necessariamente um problema: boa parte do tráfego moderno (streaming, APIs, conteúdo personalizado) não é cacheável por design, não importa o quão bem configurado esteja o cache.

## Memória e disco

Quanto do cache vive em memória RAM (mais rápido, menor) e quanto em disco (maior, mais lento) -e qual porcentagem da capacidade configurada está em uso. Um disco perto de 100% não quebra nada -o Squid começa a descartar o menos usado (LRU)- mas reduz a eficiência se o objeto descartado for pedido de novo logo em seguida.

## Versão e atividade

Versão do Squid em execução, tempo desde a última inicialização, clientes ativos e total de requisições recebidas -um panorama rápido de "está vivo, e há quanto tempo" sem precisar entrar nos logs.
`.trim(),
}
