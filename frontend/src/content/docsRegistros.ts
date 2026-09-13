// Contenido del artículo "Registros" de la biblioteca de Documentación.
// Ver docsActividadRed.ts para la razón de que esto viva aparte de los
// diccionarios de i18n/*.json.
export const DOC_REGISTROS: Record<'es' | 'en' | 'pt', string> = {
  es: `
## Para qué sirve

Es el visor en vivo de \`access.log\`: cada petición que Squid procesa, con hora, IP, usuario, método, dominio, estado, tamaño y latencia. Se actualiza solo cada 5 segundos (desactivable) y sirve para responder "¿qué está pasando ahora mismo?" -a diferencia de Actividad de red, que agrega y resume, acá se ve la petición individual.

## Qué se muestra

Una tabla con las últimas peticiones, más filtros por usuario, código de estado, dominio, y un toggle para ver solo las denegadas. Arriba, un resumen rápido (total de entradas, usuarios distintos, dominios más visitados).

## Exportar

Tres formatos, cada uno pensado para una audiencia distinta:

- **CSV**: para abrir en una hoja de cálculo.
- **NDJSON**: para ingestar en un SIEM/ELK/Splunk (una línea, un objeto JSON).
- **Log crudo**: el formato nativo de Squid, para herramientas ya hechas para eso (AWStats, SARG).

La exportación respeta los filtros activos -si filtraste por un usuario, el archivo exportado trae solo lo suyo.

## Qué NO es

Esto es \`access.log\` en vivo, con una ventana de retención limitada (Squid lo rota). Para consultar tráfico de meses anteriores, esa es la sección **Histórico** -un sistema completamente aparte, con sus propios archivos mensuales.
`.trim(),
  en: `
## What this is for

This is the live viewer of \`access.log\`: every request Squid processes, with time, IP, user, method, domain, status, size and latency. It refreshes on its own every 5 seconds (can be turned off) and answers "what's happening right now?" -unlike Network Activity, which aggregates and summarizes, here you see the individual request.

## What you see

A table with the latest requests, plus filters by user, status code, domain, and a toggle to show only denied ones. Above it, a quick summary (total entries, distinct users, most visited domains).

## Exporting

Three formats, each aimed at a different audience:

- **CSV**: to open in a spreadsheet.
- **NDJSON**: to ingest into a SIEM/ELK/Splunk (one line, one JSON object).
- **Raw log**: Squid's native format, for tools already built for it (AWStats, SARG).

The export respects the active filters -if you filtered by a user, the exported file only has their entries.

## What this is NOT

This is the live \`access.log\`, with a limited retention window (Squid rotates it). To look at traffic from previous months, that's the **Historical** section -a completely separate system, with its own monthly files.
`.trim(),
  pt: `
## Para que serve

É o visualizador ao vivo do \`access.log\`: cada requisição que o Squid processa, com hora, IP, usuário, método, domínio, status, tamanho e latência. Atualiza sozinho a cada 5 segundos (desativável) e serve para responder "o que está acontecendo agora?" -diferente de Atividade de rede, que agrega e resume, aqui se vê a requisição individual.

## O que é mostrado

Uma tabela com as últimas requisições, mais filtros por usuário, código de status, domínio, e um alternador para ver só as negadas. Acima, um resumo rápido (total de entradas, usuários distintos, domínios mais visitados).

## Exportar

Três formatos, cada um pensado para um público diferente:

- **CSV**: para abrir em uma planilha.
- **NDJSON**: para ingerir em um SIEM/ELK/Splunk (uma linha, um objeto JSON).
- **Log bruto**: o formato nativo do Squid, para ferramentas já feitas para isso (AWStats, SARG).

A exportação respeita os filtros ativos -se você filtrou por um usuário, o arquivo exportado traz só as entradas dele.

## O que isso NÃO é

Isso é o \`access.log\` ao vivo, com uma janela de retenção limitada (o Squid o rotaciona). Para consultar tráfego de meses anteriores, essa é a seção **Histórico** -um sistema completamente separado, com seus próprios arquivos mensais.
`.trim(),
}
