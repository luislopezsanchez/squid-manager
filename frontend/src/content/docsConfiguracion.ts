// Contenido del artículo "Configuración" de la biblioteca de
// Documentación. Ver docsActividadRed.ts para la razón de que esto viva
// aparte de los diccionarios de i18n/*.json.
export const DOC_CONFIGURACION: Record<'es' | 'en' | 'pt', string> = {
  es: `
## Para qué sirve

Ajustes generales de Squid que no encajan en una sección propia -organizados por categoría (Red, Caché, Seguridad, Registros, General) para no tener que buscar entre todos a la vez.

## Cuándo tienen efecto

Ningún ajuste de esta página cambia nada en Squid hasta que se pulsa **Aplicar cambios** (el botón de la barra lateral) -guardar acá solo deja el valor listo para la próxima aplicación.

## Red

- **http_port** — puerto donde Squid escucha las conexiones de los clientes. Ejemplo: \`3128\` (el estándar de facto para proxies HTTP; también se usa mucho \`8080\`).
- **dns_nameservers** — IPs de los servidores DNS a los que Squid pregunta, separadas por espacios. Ejemplo: \`172.27.0.1 1.1.1.1\` (un DNS interno primero, uno público de respaldo). Vacío = usa la resolución del sistema operativo. Solo IPs, nunca nombres. Importante: Squid reparte las consultas entre todos los que pongas -si el objetivo es que **todo** pase por un filtro DNS, dejá uno solo en la lista, no varios.

## Caché

- **cache_mem** — cuánta RAM usa Squid para los objetos más pedidos. Ejemplo: \`128 MB\` o \`512 MB\` en un servidor con más memoria disponible.
- **cache_dir** — dónde y cuánto cachea en disco. Formato: \`ufs /var/spool/squid <tamaño_MB> <niveles_L1> <niveles_L2>\`. Ejemplo: \`ufs /var/spool/squid 100 16 256\` (100 GB de caché en disco, con 16 y 256 subdirectorios para no saturar un único directorio con archivos).
- **maximum_object_size** — el objeto más grande que Squid guarda en caché; algo más grande que esto siempre se vuelve a descargar. Ejemplo: \`4 MB\` (subirlo cachea archivos más pesados, pero ocupa más espacio por cada uno).
- **refresh_pattern** — cuánto tiempo Squid considera "fresco" un objeto sin volver a preguntarle al servidor original. Formato: \`patrón min porcentaje% max\`. Ejemplo: \`. 0 20% 4320\` (para cualquier URL, sin mínimo garantizado, refrescar según el 20% de su antigüedad, con un máximo de 4320 minutos = 3 días).

## Seguridad

- **auth_children** — cuántos procesos ayudantes de autenticación corren en paralelo. Ejemplo: \`5\` (subirlo ayuda si hay muchos usuarios autenticándose a la vez y se nota lentitud en el primer acceso).
- **auth_realm** — el nombre que ve el usuario en el cartel de "usuario y contraseña" del navegador. Ejemplo: \`SquidManager Proxy\` o el nombre de tu organización.
- **credentialsttl** — cuánto tiempo Squid recuerda una credencial válida antes de volver a pedirla al helper de autenticación. Ejemplo: \`2 hours\`.
- **proxy_auth_scheme** — \`basic\` (usuario y contraseña en claro, cifrado solo si hay HTTPS/SSL Bump), \`digest\` (el navegador nunca manda la contraseña, solo un hash; no sirve para usuarios LDAP) o \`none\` (sin autenticación local, para un proxy hijo con proxy padre).
- **ssl_bump_enabled** — \`true\` para interceptar HTTPS y poder filtrar por dominio, \`false\` para solo tunelizar sin mirar adentro. Ponelo en \`false\` si salís por otro proxy que ya intercepta.
- **ssl_bump_exclude** — dominios que NO se descifran aunque SSL Bump esté activo, uno por línea o separados por espacios. Ejemplo: \`.bancoejemplo.com .saludejemplo.com\` (banca y salud son los casos típicos: descifrarlos no aporta nada y algunas apps rechazan el certificado propio por pinning).
- **auth_exempt_domains** — dominios que no piden autenticación sin importar quién los pida. Ejemplo: \`windowsupdate.microsoft.com .office.com\` (servicios que no saben presentar credenciales de proxy).
- **trusted_sources** — IPs o redes que navegan sin autenticarse. Ejemplo: \`203.0.113.10\` o \`203.0.113.0/24\`. Pensado para un proxy hijo que ya autenticó a sus usuarios -indicá el origen concreto, nunca un rango amplio como \`0.0.0.0/0\`.

## Registros

- **access_log** — ruta del archivo donde Squid escribe cada petición. Ejemplo: \`/var/log/squid/access.log\`.
- **cache_log** — ruta del log interno de diagnóstico de Squid (errores, arranque, warnings). Ejemplo: \`/var/log/squid/cache.log\`.

## General

- **visible_hostname** — el nombre con el que este proxy se identifica ante otros. Tiene que ser distinto en cada proxy de una cadena: Squid rechaza como bucle de reenvío cualquier petición cuya cabecera \`Via\` ya lleve su propio nombre. Ejemplo: \`squidmanager-suc-norte\`.
- **error_language** — idioma de las páginas de error que Squid muestra al usuario (por ejemplo, "Acceso denegado"). Ejemplo: \`es\`, \`en\`, \`pt\`.
`.trim(),
  en: `
## What this is for

General Squid settings that don't fit in a section of their own -organized by category (Network, Cache, Security, Logging, General) so there's no need to search through all of them at once.

## When they take effect

No setting on this page changes anything in Squid until **Apply changes** (the sidebar button) is clicked -saving here only leaves the value ready for the next apply.

## Network

- **http_port** — the port where Squid listens for client connections. Example: \`3128\` (the de facto standard for HTTP proxies; \`8080\` is also common).
- **dns_nameservers** — IPs of the DNS servers Squid queries, space-separated. Example: \`172.27.0.1 1.1.1.1\` (an internal DNS first, a public one as backup). Empty = use the operating system's resolution. IPs only, never names. Important: Squid distributes queries across everything you list -if the goal is for **all** DNS to go through a filter, leave only one in the list, not several.

## Cache

- **cache_mem** — how much RAM Squid uses for the most requested objects. Example: \`128 MB\` or \`512 MB\` on a server with more memory available.
- **cache_dir** — where and how much it caches on disk. Format: \`ufs /var/spool/squid <size_MB> <L1_levels> <L2_levels>\`. Example: \`ufs /var/spool/squid 100 16 256\` (100 GB of disk cache, with 16 and 256 subdirectories so a single directory doesn't get overloaded with files).
- **maximum_object_size** — the largest object Squid stores in cache; anything bigger is always re-downloaded. Example: \`4 MB\` (raising it caches heavier files, but uses more space per one).
- **refresh_pattern** — how long Squid considers an object "fresh" without asking the origin server again. Format: \`pattern min percent% max\`. Example: \`. 0 20% 4320\` (for any URL, no guaranteed minimum, refresh based on 20% of its age, capped at 4320 minutes = 3 days).

## Security

- **auth_children** — how many authentication helper processes run in parallel. Example: \`5\` (raising it helps if many users authenticate at once and the first login feels slow).
- **auth_realm** — the name the user sees in the browser's "username and password" prompt. Example: \`SquidManager Proxy\` or your organization's name.
- **credentialsttl** — how long Squid remembers a valid credential before asking the auth helper again. Example: \`2 hours\`.
- **proxy_auth_scheme** — \`basic\` (username and password in the clear, encrypted only if HTTPS/SSL Bump is on), \`digest\` (the browser never sends the password, only a hash; doesn't work for LDAP users) or \`none\` (no local authentication, for a child proxy with a parent proxy).
- **ssl_bump_enabled** — \`true\` to intercept HTTPS and filter by domain, \`false\` to just tunnel without looking inside. Set it to \`false\` if you go out through another proxy that already intercepts.
- **ssl_bump_exclude** — domains that are NOT decrypted even with SSL Bump on, one per line or space-separated. Example: \`.examplebank.com .examplehealth.com\` (banking and healthcare are the typical cases: decrypting them adds nothing and some apps reject the proxy's own certificate due to pinning).
- **auth_exempt_domains** — domains that don't require authentication no matter who requests them. Example: \`windowsupdate.microsoft.com .office.com\` (services that can't present proxy credentials).
- **trusted_sources** — IPs or networks that browse without authenticating. Example: \`203.0.113.10\` or \`203.0.113.0/24\`. Meant for a child proxy that already authenticated its users -specify the exact source, never a broad range like \`0.0.0.0/0\`.

## Logging

- **access_log** — path of the file where Squid writes every request. Example: \`/var/log/squid/access.log\`.
- **cache_log** — path of Squid's internal diagnostic log (errors, startup, warnings). Example: \`/var/log/squid/cache.log\`.

## General

- **visible_hostname** — the name this proxy identifies itself with to others. It has to be different on every proxy in a chain: Squid rejects as a forwarding loop any request whose \`Via\` header already carries its own name. Example: \`squidmanager-north-branch\`.
- **error_language** — language of the error pages Squid shows the user (for example, "Access denied"). Example: \`es\`, \`en\`, \`pt\`.
`.trim(),
  pt: `
## Para que serve

Ajustes gerais do Squid que não se encaixam em uma seção própria -organizados por categoria (Rede, Cache, Segurança, Registros, Geral) para não precisar procurar entre todos de uma vez.

## Quando têm efeito

Nenhum ajuste desta página muda nada no Squid até que se clique em **Aplicar alterações** (o botão da barra lateral) -salvar aqui só deixa o valor pronto para a próxima aplicação.

## Rede

- **http_port** — porta onde o Squid escuta as conexões dos clientes. Exemplo: \`3128\` (o padrão de fato para proxies HTTP; \`8080\` também é muito usado).
- **dns_nameservers** — IPs dos servidores DNS que o Squid consulta, separados por espaços. Exemplo: \`172.27.0.1 1.1.1.1\` (um DNS interno primeiro, um público como reserva). Vazio = usa a resolução do sistema operacional. Só IPs, nunca nomes. Importante: o Squid distribui as consultas entre todos os que você colocar -se o objetivo é que **tudo** passe por um filtro DNS, deixe só um na lista, não vários.

## Cache

- **cache_mem** — quanta RAM o Squid usa para os objetos mais pedidos. Exemplo: \`128 MB\` ou \`512 MB\` em um servidor com mais memória disponível.
- **cache_dir** — onde e quanto cacheia em disco. Formato: \`ufs /var/spool/squid <tamanho_MB> <níveis_L1> <níveis_L2>\`. Exemplo: \`ufs /var/spool/squid 100 16 256\` (100 GB de cache em disco, com 16 e 256 subdiretórios para não sobrecarregar um único diretório com arquivos).
- **maximum_object_size** — o maior objeto que o Squid guarda em cache; algo maior que isso sempre é baixado de novo. Exemplo: \`4 MB\` (aumentar cacheia arquivos mais pesados, mas ocupa mais espaço por cada um).
- **refresh_pattern** — quanto tempo o Squid considera "fresco" um objeto sem perguntar de novo ao servidor original. Formato: \`padrão min porcentagem% max\`. Exemplo: \`. 0 20% 4320\` (para qualquer URL, sem mínimo garantido, atualizar conforme 20% da sua idade, com máximo de 4320 minutos = 3 dias).

## Segurança

- **auth_children** — quantos processos auxiliares de autenticação rodam em paralelo. Exemplo: \`5\` (aumentar ajuda se muitos usuários se autenticam ao mesmo tempo e o primeiro acesso fica lento).
- **auth_realm** — o nome que o usuário vê na caixa de "usuário e senha" do navegador. Exemplo: \`SquidManager Proxy\` ou o nome da sua organização.
- **credentialsttl** — quanto tempo o Squid lembra uma credencial válida antes de perguntar de novo ao helper de autenticação. Exemplo: \`2 hours\`.
- **proxy_auth_scheme** — \`basic\` (usuário e senha em texto claro, criptografado só se houver HTTPS/SSL Bump), \`digest\` (o navegador nunca envia a senha, só um hash; não funciona para usuários LDAP) ou \`none\` (sem autenticação local, para um proxy filho com proxy pai).
- **ssl_bump_enabled** — \`true\` para interceptar HTTPS e poder filtrar por domínio, \`false\` para só tunelar sem olhar dentro. Coloque em \`false\` se você sai por outro proxy que já intercepta.
- **ssl_bump_exclude** — domínios que NÃO são descriptografados mesmo com SSL Bump ativo, um por linha ou separados por espaços. Exemplo: \`.bancoexemplo.com .saudeexemplo.com\` (banco e saúde são os casos típicos: descriptografá-los não agrega nada e alguns apps rejeitam o certificado próprio por pinning).
- **auth_exempt_domains** — domínios que não pedem autenticação não importa quem os solicite. Exemplo: \`windowsupdate.microsoft.com .office.com\` (serviços que não sabem apresentar credenciais de proxy).
- **trusted_sources** — IPs ou redes que navegam sem se autenticar. Exemplo: \`203.0.113.10\` ou \`203.0.113.0/24\`. Pensado para um proxy filho que já autenticou seus usuários -indique a origem específica, nunca uma faixa ampla como \`0.0.0.0/0\`.

## Registros

- **access_log** — caminho do arquivo onde o Squid grava cada requisição. Exemplo: \`/var/log/squid/access.log\`.
- **cache_log** — caminho do log interno de diagnóstico do Squid (erros, inicialização, avisos). Exemplo: \`/var/log/squid/cache.log\`.

## Geral

- **visible_hostname** — o nome com o qual este proxy se identifica para outros. Precisa ser diferente em cada proxy de uma cadeia: o Squid rejeita como loop de encaminhamento qualquer requisição cujo cabeçalho \`Via\` já carregue seu próprio nome. Exemplo: \`squidmanager-filial-norte\`.
- **error_language** — idioma das páginas de erro que o Squid mostra ao usuário (por exemplo, "Acesso negado"). Exemplo: \`es\`, \`en\`, \`pt\`.
`.trim(),
}
