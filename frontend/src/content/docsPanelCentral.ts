// Contenido del artículo "Panel central" de la biblioteca de Documentación.
// Ver docsActividadRed.ts para la razón de que esto viva aparte de los
// diccionarios de i18n/*.json.
export const DOC_PANEL_CENTRAL: Record<'es' | 'en' | 'pt', string> = {
  es: `
## Para qué sirve

Ver el tráfico, usuarios activos, CPU y memoria de **este servidor y de otras instancias de SquidManager** ("nodos") en una sola pantalla, sin sincronizar nada entre ellos. Útil cuando hay varias sucursales o varios proxys, cada uno con su propio SquidManager, y se quiere un vistazo centralizado sin montar un sistema de monitoreo aparte.

## Dos tipos de nodo

- **SquidManager**: otra instancia de este mismo panel. Se agrega con la URL de su panel, un usuario y una contraseña -el login normal de ese panel remoto, no un mecanismo de token nuevo. **Recomendado: una cuenta con rol "Solo lectura" dedicada a esto**, nunca la de un admin humano.
- **Squid básico**: un Squid sin SquidManager delante, sin cuenta que crear -se lee directamente su Cache Manager (\`squid-internal-mgr\`). Da menos datos (versión y clientes conectados, no tráfico en tiempo real ni usuarios activos), pero sirve para vigilar un proxy que todavía no tiene el panel instalado.

## Habilitar y "Monitorizar mis propios nodos"

Son dos interruptores independientes:

- **Habilitar**: prende todo el lado *saliente* -poder agregar, editar, probar y sincronizar nodos propios desde acá. Apagado, esas acciones ni siquiera están disponibles (el backend las rechaza, no es solo un ocultamiento visual).
- **Monitorizar mis propios nodos**: decide si este servidor le presta sus propios nodos configurados a **su padre** (otro SquidManager que lo tenga a él como nodo). Apagarlo no te desconecta de tu padre -eso nunca depende de ningún interruptor local, alcanza con que la cuenta que tu padre guardó siga siendo válida acá.

Que **a este servidor lo monitoreen** (que otro SquidManager lo tenga agregado como nodo) nunca depende de ninguno de los dos interruptores: alcanza con que la cuenta guardada allá sea válida acá, igual que cualquier otro login al panel.

## El árbol es real, no un solo nivel

Si un nodo remoto tiene, a su vez, sus propios nodos configurados, aparecen también en el árbol (nietos, bisnietos...), sin que este servidor necesite jamás las credenciales de nada más allá de sus nodos directos: cada salto se resuelve con la cuenta de ese tramo, y el resto de la ruta se reenvía tal cual.

## Si un nodo está caído

No rompe la vista de los demás: aparece marcado "Sin conexión" con el motivo (credenciales rechazadas, timeout, etc.), mientras el resto del árbol se sigue viendo con normalidad. "En línea" además distingue si el *panel* de SquidManager responde pero **Squid** (el proxy real) no -se marca "Squid caído" en ese caso, porque son dos cosas distintas que pueden fallar por separado.

## Sincronizar configuración a un nodo

Envía la configuración de **este servidor** (ACLs, reglas, usuarios, grupos, cuotas...) a un nodo remoto, **sobrescribiendo la suya** -mismo mecanismo que restaurar un archivo de backup, sin archivo intermedio. Requiere que la cuenta guardada para ese nodo tenga permisos de escritura ahí: una cuenta de solo lectura (la recomendada para monitorear) no alcanza, y se avisa con claridad en vez de fallar en silencio.

## Ejemplo

Una sucursal "Norte" con su propio SquidManager en \`https://10.0.0.5:8443\`. Se agrega acá con una cuenta \`monitor_viewer\` de rol "Solo lectura" creada en ese panel remoto solo para esto. A partir de ahí aparece en el árbol junto con este servidor, mostrando su tráfico y usuarios activos en tiempo real, y con un botón "Ver más" para el detalle (top usuarios, top dominios, últimas conexiones) sin salir de esta pantalla.
`.trim(),
  en: `
## What this is for

See the traffic, active users, CPU and memory of **this server and other SquidManager instances** ("nodes") on a single screen, without syncing anything between them. Useful when there are several branches or several proxies, each with its own SquidManager, and you want a centralized glance without setting up a separate monitoring system.

## Two kinds of node

- **SquidManager**: another instance of this same panel. Added with its panel's URL, a username and a password -the normal login of that remote panel, not a new token mechanism. **Recommended: a "Read-only" role account dedicated to this**, never a human admin's own account.
- **Basic Squid**: a Squid with no SquidManager in front of it, no account to create -its Cache Manager (\`squid-internal-mgr\`) is read directly. Gives less data (version and connected clients, not real-time traffic or active users), but is enough to keep an eye on a proxy that doesn't have the panel installed yet.

## "Enable" and "Monitor my own nodes"

These are two independent switches:

- **Enable**: turns on the entire *outgoing* side -being able to add, edit, test and sync your own nodes from here. Turned off, those actions aren't even available (the backend rejects them, it's not just hidden in the UI).
- **Monitor my own nodes**: decides whether this server lends its own configured nodes to **its parent** (another SquidManager that has this one added as a node). Turning it off doesn't disconnect you from your parent -that never depends on any local switch, it only requires that the account your parent saved is still valid here.

Whether **this server gets monitored** (another SquidManager has it added as a node) never depends on either switch: it only requires that the account saved there is still valid here, same as any other panel login.

## The tree is real, not just one level

If a remote node itself has its own configured nodes, they show up in the tree too (grandchildren, great-grandchildren...), without this server ever needing credentials beyond its direct nodes: each hop is resolved with that leg's own account, and the rest of the path is forwarded as-is.

## If a node is down

It doesn't break the view of the others: it shows as "Offline" with the reason (rejected credentials, timeout, etc.), while the rest of the tree keeps showing normally. "Online" also distinguishes whether the SquidManager *panel* responds but **Squid** (the actual proxy) doesn't -it's marked "Squid down" in that case, because those are two separate things that can fail independently.

## Syncing configuration to a node

Sends **this server's** configuration (ACLs, rules, users, groups, quotas...) to a remote node, **overwriting its own** -same mechanism as restoring a backup file, without an intermediate file. Requires that the account saved for that node has write permissions there: a read-only account (the recommended one for monitoring) isn't enough, and it's reported clearly instead of failing silently.

## Example

A "North" branch with its own SquidManager at \`https://10.0.0.5:8443\`. It's added here with a \`monitor_viewer\` account with the "Read-only" role, created on that remote panel just for this. From then on it shows up in the tree alongside this server, showing its real-time traffic and active users, with a "See more" button for details (top users, top domains, recent connections) without leaving this screen.
`.trim(),
  pt: `
## Para que serve

Ver o tráfego, usuários ativos, CPU e memória **deste servidor e de outras instâncias do SquidManager** ("nós") em uma única tela, sem sincronizar nada entre eles. Útil quando há várias filiais ou vários proxies, cada um com seu próprio SquidManager, e se quer uma visão centralizada sem montar um sistema de monitoramento à parte.

## Dois tipos de nó

- **SquidManager**: outra instância deste mesmo painel. Adicionado com a URL do seu painel, um usuário e uma senha -o login normal daquele painel remoto, não um mecanismo de token novo. **Recomendado: uma conta com papel "Somente leitura" dedicada a isso**, nunca a de um admin humano.
- **Squid básico**: um Squid sem SquidManager na frente, sem conta para criar -lê-se diretamente o seu Cache Manager (\`squid-internal-mgr\`). Dá menos dados (versão e clientes conectados, não tráfego em tempo real nem usuários ativos), mas serve para vigiar um proxy que ainda não tem o painel instalado.

## "Habilitar" e "Monitorar meus próprios nós"

São dois interruptores independentes:

- **Habilitar**: liga todo o lado *de saída* -poder adicionar, editar, testar e sincronizar nós próprios a partir daqui. Desligado, essas ações nem sequer ficam disponíveis (o backend as rejeita, não é só um ocultamento visual).
- **Monitorar meus próprios nós**: decide se este servidor empresta seus próprios nós configurados ao **seu pai** (outro SquidManager que o tenha como nó). Desligar isso não te desconecta do seu pai -isso nunca depende de nenhum interruptor local, basta que a conta que seu pai guardou continue válida aqui.

Que **este servidor seja monitorado** (que outro SquidManager o tenha adicionado como nó) nunca depende de nenhum dos dois interruptores: basta que a conta guardada lá seja válida aqui, igual a qualquer outro login no painel.

## A árvore é real, não é só um nível

Se um nó remoto tiver, por sua vez, seus próprios nós configurados, eles também aparecem na árvore (netos, bisnetos...), sem que este servidor precise nunca das credenciais de nada além dos seus nós diretos: cada salto é resolvido com a conta daquele trecho, e o resto do caminho é repassado como está.

## Se um nó está caído

Não quebra a visão dos demais: aparece marcado "Sem conexão" com o motivo (credenciais rejeitadas, timeout, etc.), enquanto o resto da árvore continua aparecendo normalmente. "Em linha" também distingue se o *painel* do SquidManager responde mas o **Squid** (o proxy de verdade) não -é marcado "Squid caído" nesse caso, porque são duas coisas distintas que podem falhar separadamente.

## Sincronizar configuração para um nó

Envia a configuração **deste servidor** (ACLs, regras, usuários, grupos, cotas...) para um nó remoto, **sobrescrevendo a dele** -mesmo mecanismo de restaurar um arquivo de backup, sem arquivo intermediário. Requer que a conta guardada para esse nó tenha permissões de escrita lá: uma conta somente leitura (a recomendada para monitorar) não é suficiente, e isso é avisado com clareza em vez de falhar silenciosamente.

## Exemplo

Uma filial "Norte" com seu próprio SquidManager em \`https://10.0.0.5:8443\`. É adicionada aqui com uma conta \`monitor_viewer\` de papel "Somente leitura" criada naquele painel remoto só para isso. A partir daí ela aparece na árvore junto com este servidor, mostrando seu tráfego e usuários ativos em tempo real, com um botão "Ver mais" para o detalhe (top usuários, top domínios, últimas conexões) sem sair desta tela.
`.trim(),
}
