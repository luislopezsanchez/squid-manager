// Contenido del artículo "Actividad de red" de la biblioteca de
// Documentación. Vive aparte (no en los diccionarios de i18n/*.json) porque
// es prosa larga por idioma, no strings cortos de interfaz -meterlo en
// traducir() con el texto español entero como clave haría esa clave
// gigante e imposible de mantener.
export const DOC_ACTIVIDAD_RED: Record<'es' | 'en' | 'pt', string> = {
  es: `
## Para qué sirve

Esta sección **no configura nada**: ningún ajuste de acá cambia cómo Squid deja o no deja navegar a los usuarios. Es pura salida de datos -un reporte sobre lo que ya pasó, tomado directamente de \`access.log\`- para responder preguntas concretas sin tener que leer el log a mano:

- ¿Quién está consumiendo más ancho de banda?
- ¿Qué sitios se visitan más, estén permitidos o no?
- ¿La política de bloqueo actual está funcionando de verdad, o es solo teoría en la configuración?
- ¿Quién insiste más contra una regla de acceso?

## Qué se muestra

Cuatro vistas, cada una con su propia pregunta:

| Pestaña | Responde a... |
|---|---|
| **Usuarios** | Quién consume más — por datos (MB/GB) o por cantidad de peticiones. No son lo mismo: pocas peticiones pueden pesar mucho (una descarga grande) y muchas peticiones pueden pesar poco. |
| **Sitios visitados** | Qué dominios se visitan más, para decidir con datos reales si vale la pena sumar una ACL nueva. |
| **Sitios bloqueados** | Contra qué está chocando la política de acceso ahora mismo. |
| **Usuarios con más bloqueos** | Quién insiste más contra una regla — unos pocos bloqueos son ruido normal, una cifra alta y sostenida amerita una conversación. |

Cada tabla incluye un **anillo de concentración** (qué porcentaje del total real acaparan los primeros 3) y, al hacer clic en cualquier fila, un **detalle** con las peticiones concretas de ese usuario o dominio (drill-down).

## Filtro de tiempo

Arriba a la derecha se elige la ventana: **Recientes** (últimas 1.000 peticiones registradas, sin importar cuándo ocurrieron), **Última hora**, **Últimas 24 horas** o **Últimos 7 días**. Cambia todas las pestañas a la vez.

## Qué se exporta a PDF

El botón **Exportar PDF** genera un informe con las cuatro tablas (top 10 de cada una) más los totales reales de toda la ventana seleccionada — pensado para adjuntar o imprimir sin depender de una captura de pantalla.

## Cuándo ocurrió cada cosa

- **IPs compartidas**: cada fila muestra desde cuándo hasta cuándo se vio esa IP con más de una cuenta (con precisión de hora). Sale de la lista cuando pasa la ventana elegida sin que se repita.
- **Cuota excedida**: cada fila indica cuándo se agotó la cuota y **cuándo se restablece**; ahí desaparece de la lista (o antes, si subes o quitas el límite).

## Una gráfica propia por pestaña

La tarjeta de evolución cambia con la pestaña: datos o peticiones (Usuarios), sitios distintos (Sitios visitados), peticiones bloqueadas, usuarios con bloqueos e IPs compartidas por periodo. Con la ventana de 1 h las que no son de tráfico piden 24 h o más.

## Informe en PDF

**Exportar PDF** genera un informe con el resumen, «lo más destacado», y por cada pestaña una explicación, su tabla y su gráfica. Respeta la ventana o el rango de fechas elegido, la zona horaria y el idioma del panel.
`.trim(),
  en: `
## What this is for

This section **does not configure anything**: no setting here changes how Squid does or doesn't let users browse. It's pure data output — a report on what already happened, read straight from \`access.log\` — to answer concrete questions without reading the log by hand:

- Who is using the most bandwidth?
- Which sites get visited the most, allowed or not?
- Is the current blocking policy actually working, or just theory in the configuration?
- Who pushes back the most against an access rule?

## What you see

Four views, each answering its own question:

| Tab | Answers... |
|---|---|
| **Users** | Who consumes the most — by data (MB/GB) or by number of requests. These aren't the same: few requests can weigh a lot (one big download), and many requests can weigh little. |
| **Visited sites** | Which domains get visited most, to decide with real data whether a new ACL is worth adding. |
| **Blocked sites** | What the access policy is actually colliding with right now. |
| **Users with most blocks** | Who pushes back most against a rule — a few blocks are normal noise, a high and sustained count from the same person is worth a conversation. |

Each table includes a **concentration ring** (what share of the real total the top 3 account for) and, clicking any row, a **detail view** with the actual requests for that user or domain (drill-down).

## Time filter

Top right, pick the window: **Recent** (last 1,000 requests logged, regardless of when), **Last hour**, **Last 24 hours**, or **Last 7 days**. It changes every tab at once.

## What the PDF export includes

The **Export PDF** button generates a report with all four tables (top 10 of each) plus the real totals for the whole selected window — meant to attach or print without relying on a screenshot.

## When each thing happened

- **Shared IPs**: each row shows since when until when that IP was seen with more than one account (hour precision). It leaves the list when the chosen window passes without it repeating.
- **Quota exceeded**: each row says when the quota was exhausted and **when it resets**; it disappears from the list then (or earlier if you raise or remove the limit).

## A chart of its own per tab

The evolution card changes with the tab: data or requests (Users), distinct sites (Sites visited), blocked requests, users with blocks and shared IPs per period. With the 1 h window the non-traffic ones ask for 24 h or more.

## PDF report

**Export PDF** produces a report with the summary, highlights, and for each tab an explanation, its table and its chart. It follows the chosen window or date range, the time zone and the panel language.
`.trim(),
  pt: `
## Para que serve

Esta seção **não configura nada**: nenhum ajuste aqui muda como o Squid deixa ou não os usuários navegarem. É pura saída de dados -um relatório sobre o que já aconteceu, lido direto do \`access.log\`- para responder perguntas concretas sem ter que ler o log manualmente:

- Quem está consumindo mais largura de banda?
- Quais sites são mais visitados, permitidos ou não?
- A política de bloqueio atual está funcionando de verdade, ou é só teoria na configuração?
- Quem mais insiste contra uma regra de acesso?

## O que é mostrado

Quatro visões, cada uma respondendo sua própria pergunta:

| Aba | Responde a... |
|---|---|
| **Usuários** | Quem consome mais — por dados (MB/GB) ou por número de requisições. Não são a mesma coisa: poucas requisições podem pesar muito (um download grande), e muitas requisições podem pesar pouco. |
| **Sites visitados** | Quais domínios são mais visitados, para decidir com dados reais se vale a pena adicionar uma nova ACL. |
| **Sites bloqueados** | Contra o que a política de acesso está realmente esbarrando agora. |
| **Usuários com mais bloqueios** | Quem mais insiste contra uma regra — poucos bloqueios são ruído normal, um número alto e sustentado da mesma pessoa merece uma conversa. |

Cada tabela inclui um **anel de concentração** (qual porcentagem do total real os 3 primeiros representam) e, ao clicar em qualquer linha, um **detalhe** com as requisições concretas daquele usuário ou domínio (drill-down).

## Filtro de tempo

No canto superior direito, escolha a janela: **Recentes** (últimas 1.000 requisições registradas, independente de quando ocorreram), **Última hora**, **Últimas 24 horas** ou **Últimos 7 dias**. Muda todas as abas de uma vez.

## O que é exportado em PDF

O botão **Exportar PDF** gera um relatório com as quatro tabelas (top 10 de cada uma) mais os totais reais de toda a janela selecionada — pensado para anexar ou imprimir sem depender de uma captura de tela.

## Quando aconteceu cada coisa

- **IPs compartilhados**: cada linha mostra desde quando até quando esse IP foi visto com mais de uma conta (precisão de hora). Sai da lista quando a janela escolhida passa sem se repetir.
- **Cota excedida**: cada linha indica quando a cota se esgotou e **quando é reiniciada**; nesse momento sai da lista (ou antes, se você aumentar ou remover o limite).

## Um gráfico próprio por aba

O cartão de evolução muda com a aba: dados ou requisições (Usuários), sites distintos (Sites visitados), requisições bloqueadas, usuários com bloqueios e IPs compartilhados por período. Com a janela de 1 h as que não são de tráfego pedem 24 h ou mais.

## Relatório em PDF

**Exportar PDF** gera um relatório com o resumo, os destaques e, por aba, uma explicação, sua tabela e seu gráfico. Respeita a janela ou o intervalo de datas escolhido, o fuso horário e o idioma do painel.
`.trim(),
}
