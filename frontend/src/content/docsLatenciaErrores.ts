// Contenido del artículo "Latencia y errores" de la biblioteca de
// Documentación. Ver docsActividadRed.ts para la razón de que esto viva
// aparte de los diccionarios de i18n/*.json.
export const DOC_LATENCIA_ERRORES: Record<'es' | 'en' | 'pt', string> = {
  es: `
## Para qué sirve

Igual que Actividad de red, esta sección **no configura nada** — es salida de datos tomada de \`access.log\` para responder dos preguntas de salud del proxy:

- ¿Qué tan rápido responden los sitios a través de Squid?
- ¿Cuántos fallos reales (de servidor o de red) está habiendo, y dónde?

## Qué se muestra

**Pestaña Latencia**: promedio, mediana (p50) y p95 sobre toda la ventana, más el ranking de los dominios más lentos. Un promedio general alto suele ser el enlace de salida; un promedio alto en un solo dominio suele ser ese sitio o servidor, no el proxy. Los túneles HTTPS (CONNECT) se excluyen del cálculo — ahí el tiempo mide cuánto duró la conexión abierta, no cuánto tardó en responder, y mezclarlo arruinaría el promedio.

**Pestaña Errores HTTP**: códigos de error agrupados por frecuencia (\`por código\`) y por dominio que los genera (\`por dominio\`), con el total real y qué porcentaje concentran los primeros 3. Los códigos **4xx** (ej. 404) se muestran en ámbar — un recurso que no existe, a veces solo un link roto — y los **5xx** (502, 504...) en rojo — el proxy o la red fallando de verdad.

**No incluye** 401/403/407: esos son bloqueos de política de acceso, ya cubiertos en Actividad de red → Sitios/usuarios bloqueados. Contarlos acá duplicaría el mismo dato bajo otro nombre.

## Filtro de tiempo y drill-down

Mismo filtro que Actividad de red (Recientes / última hora / 24 horas / 7 días), arriba a la derecha. Al hacer clic en cualquier dominio — de "Dominios más lentos" o de "Por dominio" en Errores — se abre el detalle con las peticiones concretas de ese dominio en la ventana elegida.
`.trim(),
  en: `
## What this is for

Just like Network activity, this section **does not configure anything** — it's data output from \`access.log\` answering two proxy-health questions:

- How fast do sites respond through Squid?
- How many real failures (server or network) are happening, and where?

## What you see

**Latency tab**: average, median (p50) and p95 over the whole window, plus a ranking of the slowest domains. A high overall average is usually the outbound link; a high average on just one domain is usually that site or server, not the proxy. HTTPS tunnels (CONNECT) are excluded from the calculation — there the time measures how long the connection stayed open, not how long it took to respond, and mixing it in would ruin the average.

**HTTP errors tab**: error codes grouped by frequency (\`by code\`) and by the domain generating them (\`by domain\`), with the real total and what share the top 3 account for. **4xx** codes (e.g. 404) show in amber — a resource that doesn't exist, sometimes just a broken link — and **5xx** (502, 504...) in red — the proxy or the network actually failing.

**Does not include** 401/403/407: those are access-policy blocks, already covered in Network activity → Blocked sites/users. Counting them here would duplicate the same data under another name.

## Time filter and drill-down

Same filter as Network activity (Recent / last hour / 24 hours / 7 days), top right. Clicking any domain — from "Slowest domains" or "By domain" in Errors — opens the detail view with the actual requests for that domain in the chosen window.
`.trim(),
  pt: `
## Para que serve

Assim como Atividade de rede, esta seção **não configura nada** — é saída de dados lida do \`access.log\` para responder duas perguntas sobre a saúde do proxy:

- Quão rápido os sites respondem através do Squid?
- Quantas falhas reais (de servidor ou de rede) estão acontecendo, e onde?

## O que é mostrado

**Aba Latência**: média, mediana (p50) e p95 sobre toda a janela, mais o ranking dos domínios mais lentos. Uma média geral alta costuma ser o link de saída; uma média alta em um único domínio costuma ser aquele site ou servidor, não o proxy. Os túneis HTTPS (CONNECT) são excluídos do cálculo — ali o tempo mede quanto durou a conexão aberta, não quanto demorou para responder, e misturar isso estragaria a média.

**Aba Erros HTTP**: códigos de erro agrupados por frequência (\`por código\`) e pelo domínio que os gera (\`por domínio\`), com o total real e qual porcentagem os 3 primeiros representam. Códigos **4xx** (ex. 404) aparecem em âmbar — um recurso que não existe, às vezes só um link quebrado — e **5xx** (502, 504...) em vermelho — o proxy ou a rede falhando de verdade.

**Não inclui** 401/403/407: esses são bloqueios de política de acesso, já cobertos em Atividade de rede → Sites/usuários bloqueados. Contá-los aqui duplicaria o mesmo dado sob outro nome.

## Filtro de tempo e drill-down

Mesmo filtro que Atividade de rede (Recentes / última hora / 24 horas / 7 dias), no canto superior direito. Ao clicar em qualquer domínio — de "Domínios mais lentos" ou de "Por domínio" em Erros — abre o detalhe com as requisições concretas daquele domínio na janela escolhida.
`.trim(),
}
