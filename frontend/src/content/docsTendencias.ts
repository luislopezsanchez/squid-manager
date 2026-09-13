// Contenido del artículo "Tendencias" de la biblioteca de Documentación.
// Ver docsActividadRed.ts para la razón de que esto viva aparte de los
// diccionarios de i18n/*.json.
export const DOC_TENDENCIAS: Record<'es' | 'en' | 'pt', string> = {
  es: `
## Para qué sirve

Las demás secciones de Análisis muestran una foto fija del período elegido (el total, el top 10). Tendencias responde una pregunta distinta: **cómo evolucionó** un usuario o un dominio puntual a lo largo de ese mismo período — ¿el consumo fue parejo, o hubo un pico concreto un día o una hora determinada?

## Cómo se usa

1. Elige si vas a buscar por **Usuario** o por **Dominio**.
2. Escribe el nombre exacto (tal como aparece en Actividad de red — ej. \`mgomez\` o \`github.com\`) y presioná **Ver tendencia**.
3. Elegí la ventana de tiempo (Recientes / última hora / 24 horas / 7 días) — el gráfico se reparte en 20 intervalos iguales dentro de esa ventana, no en horas fijas, para que funcione igual de bien con una ventana corta que con una larga.
4. El toggle **Datos / Peticiones** cambia qué métrica se grafica, igual que en Actividad de red.

## Acceso directo desde el detalle

En Actividad de red y en Latencia y errores, al hacer clic en un usuario o dominio se abre un detalle con sus peticiones concretas — ahí mismo hay un botón **Ver tendencia** que trae directo a esta página con ese usuario o dominio ya cargado, sin tener que volver a escribirlo.
`.trim(),
  en: `
## What this is for

The other Analytics sections show a fixed snapshot of the chosen period (the total, the top 10). Trends answers a different question: **how a specific user or domain changed** over that same period — was usage steady, or was there a spike on one particular day or hour?

## How to use it

1. Choose whether to search by **User** or by **Domain**.
2. Type the exact name (as it appears in Network activity — e.g. \`mgomez\` or \`github.com\`) and press **View trend**.
3. Pick the time window (Recent / last hour / 24 hours / 7 days) — the chart is split into 20 equal intervals within that window, not fixed hours, so it works just as well with a short window as with a long one.
4. The **Data / Requests** toggle switches which metric is charted, same as in Network activity.

## Direct access from the detail view

In Network activity and Latency and errors, clicking a user or domain opens a detail view with its actual requests — right there is a **View trend** button that takes you straight to this page with that user or domain already loaded, no need to type it again.
`.trim(),
  pt: `
## Para que serve

As outras seções de Análise mostram uma foto fixa do período escolhido (o total, o top 10). Tendências responde a uma pergunta diferente: **como evoluiu** um usuário ou domínio específico ao longo desse mesmo período — o consumo foi constante, ou houve um pico em um dia ou hora determinado?

## Como usar

1. Escolha se vai buscar por **Usuário** ou por **Domínio**.
2. Digite o nome exato (como aparece em Atividade de rede — ex. \`mgomez\` ou \`github.com\`) e aperte **Ver tendência**.
3. Escolha a janela de tempo (Recentes / última hora / 24 horas / 7 dias) — o gráfico é dividido em 20 intervalos iguais dentro dessa janela, não em horas fixas, para funcionar igualmente bem com uma janela curta ou longa.
4. O alternador **Dados / Requisições** muda qual métrica é exibida, igual em Atividade de rede.

## Acesso direto a partir do detalhe

Em Atividade de rede e em Latência e erros, ao clicar em um usuário ou domínio abre um detalhe com suas requisições concretas — ali mesmo há um botão **Ver tendência** que leva direto a esta página com aquele usuário ou domínio já carregado, sem precisar digitar de novo.
`.trim(),
}
