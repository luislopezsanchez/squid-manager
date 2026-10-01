// Contenido del artículo "Actualizaciones" de la biblioteca de
// Documentación. Ver docsActividadRed.ts para la razón de que esto viva
// aparte de los diccionarios de i18n/*.json.
export const DOC_ACTUALIZACIONES: Record<'es' | 'en' | 'pt', string> = {
  es: `
## Para qué sirve

Comprueba si hay una versión nueva de SquidManager publicada en GitHub, muestra qué cambió (la lista real de commits), y permite aprobarla -de inmediato o programada para una fecha y hora- sin entrar por SSH.

## El panel nunca ejecuta la actualización

Solo puede avisar y dejar aprobada una actualización. Quien la aplica de verdad es un temporizador de systemd en el host, corriendo como root, ya instalado con permisos fijos desde antes -aprobar desde el panel solo escribe un archivo de estado, con los mismos privilegios que guardar cualquier otro ajuste.

## Aplicar ahora

Requiere una cuenta **superadministrador**. En **Actualizaciones**: "Comprobar ahora" (o esperar la comprobación automática, cada 6 horas), revisar la lista de "Novedades", y pulsar "Actualizar ahora". En instalación nativa se aplica en los segundos siguientes; en Docker, el temporizador del host la nota en su próximo ciclo (hasta 1 minuto). Mientras se aplica, el panel puede quedarse sin responder un momento -al terminar aparece un aviso de "Recargar" en cualquier página.

## Programar para más tarde

Mismos pasos, eligiendo fecha y hora y pulsando "Programar" en vez de "Actualizar ahora". Se revisa una vez por minuto; si pasan más de 3 minutos sin arrancar, la tarjeta la marca como "atrasada" -señal de revisar por SSH si el temporizador (\`systemctl status squidmanager-autoupdate.timer\` en nativo, \`squidmanager-docker-autoupdate.timer\` en Docker) sigue corriendo.

## Comprobación automática

Corre cada 6 horas en segundo plano (se puede apagar con el casillero "Comprobar automáticamente"); solo consulta la API pública de GitHub para comparar el commit desplegado, no manda ningún dato del servidor.

## Nativo vs. Docker

La diferencia real está en la demora de "Actualizar ahora": segundos en nativo (puede adelantar el temporizador con sudo), hasta un minuto en Docker (no hay sudo hacia el host desde dentro de un contenedor, siempre espera al próximo tic).


## Si el servidor sale a Internet por un proxy

Las comprobaciones y las actualizaciones necesitan llegar a GitHub. En una instalación nativa detrás de un proxy corporativo, el proxy se guarda en \`/etc/squidmanager/proxy.env\` (lo crea \`install-tras-proxy.sh --nativo\`, o el propio instalador si lo ejecutaste con el proxy exportado) y lo usan el panel y las actualizaciones programadas. Si el panel dice que no puede consultar GitHub, revisa ese fichero y reinicia el servicio del panel. Guía completa: \`docs/instalacion-tras-proxy.md\`.`.trim(),
  en: `
## What this is for

Checks whether a new SquidManager version has been published on GitHub, shows what changed (the real list of commits), and lets you approve it -right away or scheduled for a date and time- without SSHing in.

## The panel never runs the update itself

It can only notify and leave an update approved. What actually applies it is a systemd timer on the host, running as root, already installed with fixed permissions from before -approving from the panel only writes a state file, with the same privileges as saving any other setting.

## Applying it now

Requires a **superadmin** account. On the **Updates** page: "Check now" (or wait for the automatic check, every 6 hours), review the "What's new" list, and press "Update now". On a native install it applies within seconds; on Docker, the host's timer picks it up on its next cycle (up to 1 minute). While it applies, the panel may stop responding for a moment -once done, a "Reload" notice appears on any page.

## Scheduling it for later

Same steps, but pick a date and time and press "Schedule" instead of "Update now". It's checked once a minute; if more than 3 minutes pass without starting, the card marks it as "delayed" -a sign to check over SSH whether the timer (\`systemctl status squidmanager-autoupdate.timer\` on native, \`squidmanager-docker-autoupdate.timer\` on Docker) is still running.

## Automatic check

Runs every 6 hours in the background (can be turned off with the "Check automatically" checkbox); it only queries GitHub's public API to compare the deployed commit, no server data is sent.

## Native vs. Docker

The real difference is in how long "Update now" takes: seconds on native (it can nudge the timer forward via sudo), up to a minute on Docker (there's no sudo to the host from inside a container, so it always waits for the next tick).


## If the server reaches the Internet through a proxy

Checks and updates need to reach GitHub. On a native install behind a corporate proxy, the proxy is saved in \`/etc/squidmanager/proxy.env\` (created by \`install-tras-proxy.sh --nativo\`, or by the installer itself if you ran it with the proxy exported) and is used by the panel and the scheduled updates. If the panel says it cannot query GitHub, check that file and restart the panel service. Full guide: \`docs/instalacion-tras-proxy.md\`.`.trim(),
  pt: `
## Para que serve

Verifica se há uma versão nova do SquidManager publicada no GitHub, mostra o que mudou (a lista real de commits), e permite aprová-la -na hora ou agendada para uma data e horário- sem precisar entrar por SSH.

## O painel nunca executa a atualização

Ele só pode avisar e deixar uma atualização aprovada. Quem realmente a aplica é um temporizador do systemd no host, rodando como root, já instalado com permissões fixas desde antes -aprovar pelo painel só grava um arquivo de estado, com os mesmos privilégios de salvar qualquer outro ajuste.

## Aplicar agora

Requer uma conta de **superadministrador**. Em **Atualizações**: "Verificar agora" (ou espere a verificação automática, a cada 6 horas), revise a lista de "Novidades", e clique em "Atualizar agora". Numa instalação nativa é aplicada nos segundos seguintes; no Docker, o temporizador do host percebe no próximo ciclo (até 1 minuto). Enquanto é aplicada, o painel pode ficar sem responder por um momento -ao terminar, aparece um aviso de "Recarregar" em qualquer página.

## Agendar para mais tarde

Mesmos passos, escolhendo data e horário e clicando em "Agendar" em vez de "Atualizar agora". É verificado uma vez por minuto; se passarem mais de 3 minutos sem começar, o cartão marca como "atrasada" -sinal para verificar por SSH se o temporizador (\`systemctl status squidmanager-autoupdate.timer\` no nativo, \`squidmanager-docker-autoupdate.timer\` no Docker) ainda está rodando.

## Verificação automática

Roda a cada 6 horas em segundo plano (pode ser desligada com a caixa "Verificar automaticamente"); só consulta a API pública do GitHub para comparar o commit instalado, nenhum dado do servidor é enviado.

## Nativo vs. Docker

A diferença real está na demora de "Atualizar agora": segundos no nativo (pode adiantar o temporizador via sudo), até um minuto no Docker (não há sudo para o host de dentro de um contêiner, então sempre espera o próximo tique).


## Se o servidor acessa a Internet por um proxy

As verificações e atualizações precisam chegar ao GitHub. Numa instalação nativa atrás de um proxy corporativo, o proxy fica guardado em \`/etc/squidmanager/proxy.env\` (criado por \`install-tras-proxy.sh --nativo\`, ou pelo próprio instalador se você o executou com o proxy exportado) e é usado pelo painel e pelas atualizações agendadas. Se o painel disser que não consegue consultar o GitHub, confira esse arquivo e reinicie o serviço do painel. Guia completo: \`docs/instalacion-tras-proxy.md\`.`.trim(),
}
