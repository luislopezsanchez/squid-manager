// Contenido del artículo "Histórico" de la biblioteca de Documentación.
// Ver docsActividadRed.ts para la razón de que esto viva aparte de los
// diccionarios de i18n/*.json.
export const DOC_HISTORICO: Record<'es' | 'en' | 'pt', string> = {
  es: `
## Para qué sirve

Consultar tráfico de **meses anteriores**, cuando el \`access.log\` en vivo (sección Registros) ya lo rotó y descartó. Es un sistema completamente aparte, pensado para no competir por recursos con las métricas en vivo: los archivos mensuales se generan y se indexan una vez al mes, no en cada petición al panel.

## Qué se muestra

Un mes se elige de una lista (cada uno con su tamaño, rango de fechas y totales ya calculados: usuarios y dominios únicos, códigos de estado, top dominios/usuarios, bytes totales, denegadas). Al entrar a un mes, la tabla de entradas funciona igual que Registros -mismos filtros por usuario, estado, dominio y denegadas- pero sobre ese archivo cerrado, no sobre tráfico en vivo.

## Por qué no se actualiza solo

Un mes ya cerrado no cambia: no tiene sentido volver a consultarlo cada pocos segundos como sí hace el visor en vivo. Los totales que se ven en la lista de meses vienen de un índice que se arma por separado (una vez), no se recalculan al abrir la página.

## Si un mes no aparece

Si el mes no tiene índice todavía (recién archivado, o la tarea mensual no corrió), aparece marcado como tal en vez de mostrar datos incompletos o incorrectos.
`.trim(),
  en: `
## What this is for

Looking up traffic from **previous months**, once the live \`access.log\` (Logs section) has already rotated and discarded it. It's a completely separate system, designed to not compete for resources with live metrics: monthly files are generated and indexed once a month, not on every request to the panel.

## What you see

A month is picked from a list (each with its size, date range and totals already computed: unique users and domains, status codes, top domains/users, total bytes, denied requests). Once inside a month, the entries table works the same as Logs -same filters by user, status, domain and denied- but over that closed file, not live traffic.

## Why it doesn't refresh on its own

A month that's already closed doesn't change: there's no point querying it every few seconds like the live viewer does. The totals shown in the month list come from an index built separately (once), not recalculated when you open the page.

## If a month doesn't show up

If the month doesn't have an index yet (just archived, or the monthly task hasn't run), it's marked as such instead of showing incomplete or incorrect data.
`.trim(),
  pt: `
## Para que serve

Consultar tráfego de **meses anteriores**, quando o \`access.log\` ao vivo (seção Registros) já o rotacionou e descartou. É um sistema completamente separado, pensado para não competir por recursos com as métricas ao vivo: os arquivos mensais são gerados e indexados uma vez por mês, não a cada requisição ao painel.

## O que é mostrado

Um mês é escolhido de uma lista (cada um com seu tamanho, intervalo de datas e totais já calculados: usuários e domínios únicos, códigos de status, top domínios/usuários, bytes totais, negadas). Ao entrar em um mês, a tabela de entradas funciona igual à de Registros -mesmos filtros por usuário, status, domínio e negadas- mas sobre esse arquivo fechado, não sobre tráfego ao vivo.

## Por que não atualiza sozinho

Um mês já fechado não muda: não faz sentido consultá-lo a cada poucos segundos como faz o visualizador ao vivo. Os totais mostrados na lista de meses vêm de um índice montado separadamente (uma vez), não recalculados ao abrir a página.

## Se um mês não aparecer

Se o mês ainda não tem índice (recém-arquivado, ou a tarefa mensal não rodou), ele aparece marcado como tal em vez de mostrar dados incompletos ou incorretos.
`.trim(),
}
