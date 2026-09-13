// Contenido del artículo "Panorama" de la biblioteca de Documentación.
// Ver docsActividadRed.ts para la razón de que esto viva aparte de los
// diccionarios de i18n/*.json.
export const DOC_PANORAMA: Record<'es' | 'en' | 'pt', string> = {
  es: `
## Para qué sirve

A diferencia de Tendencias (que sigue a un usuario o dominio puntual), Panorama mira **todo el tráfico junto** para responder preguntas de comportamiento general: ¿cuándo pesa más el tráfico?, ¿viene creciendo o hubo un pico puntual? Es el lugar para justificar con datos un cambio de horario de una política, o para saber cuándo esperar más carga en el enlace.

## Qué se muestra

**Volumen de tráfico**: un gráfico de línea cuyas barras se adaptan a la ventana de tiempo elegida, para que realmente cambien de forma según lo que selecciones y no solo de escala:

- **Última hora**: un punto cada 5 minutos.
- **Últimas 24 horas**: un punto por hora (24 puntos).
- **Últimos 7 días** o **Últimos 30 días**: un punto por día calendario (7 o ~30 puntos).

El toggle Datos/Peticiones cambia qué métrica se grafica, y arriba se destaca el momento (hora o día, según la granularidad) con más tráfico.

Esta sección puede ir sumando más gráficos de panorama general con el tiempo.
`.trim(),
  en: `
## What this is for

Unlike Trends (which follows one specific user or domain), Overview looks at **all traffic together** to answer general behavior questions: when does traffic weigh the most? Is it growing, or was there a one-off spike? It's the place to justify changing a policy's schedule with real data, or to know when to expect more load on the link.

## What you see

**Traffic volume**: a line chart whose bars adapt to the chosen time window, so the shape of the chart actually changes with your selection instead of just its scale:

- **Last hour**: one point every 5 minutes.
- **Last 24 hours**: one point per hour (24 points).
- **Last 7 days** or **Last 30 days**: one point per calendar day (7 or ~30 points).

The Data/Requests toggle switches which metric is charted, and the busiest moment (hour or day, depending on the granularity) is highlighted above it.

This section may keep gaining more overview-level charts over time.
`.trim(),
  pt: `
## Para que serve

Diferente de Tendências (que acompanha um usuário ou domínio específico), Panorama olha **todo o tráfego junto** para responder perguntas de comportamento geral: quando o tráfego pesa mais? Está crescendo, ou houve um pico pontual? É o lugar para justificar com dados uma mudança de horário de uma política, ou para saber quando esperar mais carga no link.

## O que é mostrado

**Volume de tráfego**: um gráfico de linha cujas barras se adaptam à janela de tempo escolhida, para que a forma do gráfico realmente mude conforme a seleção, não só a escala:

- **Última hora**: um ponto a cada 5 minutos.
- **Últimas 24 horas**: um ponto por hora (24 pontos).
- **Últimos 7 dias** ou **Últimos 30 dias**: um ponto por dia calendário (7 ou ~30 pontos).

O alternador Dados/Requisições muda qual métrica é exibida, e o momento (hora ou dia, dependendo da granularidade) com mais tráfego é destacado acima.

Esta seção pode ganhar mais gráficos de panorama geral com o tempo.
`.trim(),
}
