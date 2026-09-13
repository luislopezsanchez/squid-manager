// Contenido del artículo "ACLs" de la biblioteca de Documentación.
// Ver docsActividadRed.ts para la razón de que esto viva aparte de los
// diccionarios de i18n/*.json.
export const DOC_ACLS: Record<'es' | 'en' | 'pt', string> = {
  es: `
## Para qué sirve

Una ACL (Access Control List) es una condición con nombre -un rango de IPs, una lista de dominios, un horario, un usuario autenticado- que después se usa en **Reglas de acceso** para permitir o denegar tráfico. Una ACL sola no bloquea nada: hasta que una regla la referencia, es solo una definición sin efecto.

## Dos formas de cargar una ACL

**A mano** ("Nueva ACL"): se escribe el valor directamente (por ejemplo, \`.facebook.com .instagram.com\`). Pensado para listas cortas -unas pocas decenas de valores- que se editan de vez en cuando desde el propio panel.

**Cargar dominios**: se sube un archivo de texto (un dominio por línea). Pensado para blocklists grandes -de cientos a millones de dominios-, típicamente descargadas de un proveedor externo. Por debajo de 200 dominios, la carga se guarda igual que una ACL normal; por encima, se guarda como **ACL de archivo**: el contenido no vive en la base de datos, vive en un archivo en el servidor, y Squid lo lee directamente de ahí. Una ACL de archivo no se edita a mano -tiene sentido volver a subir el archivo actualizado con el mismo nombre para reemplazarla, no editar dominio por dominio.

El modo **"Agregar a lo que ya había"** suma los dominios nuevos a los que ya tenía esa ACL, sin duplicar; **"Reemplazar toda la lista"** descarta lo anterior.

## Tipos de ACL disponibles, con ejemplo

- **IP de origen (src)** — de dónde viene el cliente. Ej: \`192.168.1.0/24\`.
- **IP de destino (dst)** — a qué IP se dirige la petición. Ej: \`10.0.0.0/8\`.
- **Dominio de destino (dstdomain)** — a qué dominio. El punto inicial incluye subdominios. Ej: \`.facebook.com\` (coincide con facebook.com, www.facebook.com, m.facebook.com...).
- **Regex de dominio (dstdom_regex)** — para patrones que una lista de dominios sueltos no puede expresar. Ej: \`\\.social\\.\` (cualquier dominio que tenga ".social." en el medio).
- **Regex de URL (url_regex)** — sobre la URL completa, no solo el dominio. Ej: \`\\.mp4$\` (cualquier URL que termine en .mp4, sin importar el dominio).
- **Regex de path URL (urlpath_regex)** — como el anterior, pero ignorando el dominio y los parámetros de query. Ej: \`/download/\`.
- **Puerto destino (port)** — uno o varios puertos, separados por espacio. Ej: \`443 80\`.
- **Protocolo (proto)** — Ej: \`HTTP FTP\`.
- **Método HTTP (method)** — Ej: \`GET POST\` (para permitir solo lectura, por ejemplo, se excluiría POST/PUT/DELETE).
- **Horario (time)** — día(s) y rango horario. Ej: \`M-F 09:00-17:00\` (lunes a viernes, horario laboral).
- **Usuario autenticado (proxy_auth)** — Ej: \`REQUIRED\` (cualquier usuario autenticado, sin importar cuál) o una lista de usuarios puntuales.
- **Conexiones máximas (maxconn)** — tope de conexiones simultáneas por cliente. Ej: \`10\`.
- **User-Agent (browser)** — según lo que declara el navegador/app. Ej: \`Chrome\` (poco confiable como control de seguridad: cualquiera puede falsificar su User-Agent, útil más bien para reportes).
- **MIME type de respuesta (rep_mime_type)** — según el tipo de contenido que devuelve el servidor. Ej: \`video/\` (cualquier respuesta cuyo tipo empiece con "video/").

## Qué esperar con una lista muy grande (cientos de miles o millones de dominios)

- **Cargar el archivo** es rápido (segundos, incluso con varios millones de líneas): se valida cada línea y se escribe una sola vez.
- **Volver a subir el mismo archivo sin cambios** no reescribe nada -se detecta que es idéntico.
- **"Aplicar cambios"**, en cambio, va a tardar -a veces varios minutos- mientras esa ACL exista y esté en uso en alguna regla, sin importar lo simple que sea el resto del cambio (una IP de DNS, un horario). Esto no es una demora de SquidManager: es Squid mismo releyendo esa lista completa en su propia memoria cada vez que recarga su configuración, algo que ningún proxy evita del todo. La barra de progreso bajo "Aplicar cambios" muestra en qué paso va mientras se espera.
`.trim(),
  en: `
## What this is for

An ACL (Access Control List) is a named condition -an IP range, a list of domains, a time window, an authenticated user- later used in **Access rules** to allow or deny traffic. An ACL on its own blocks nothing: until some rule references it, it's just a definition with no effect.

## Two ways to load an ACL

**By hand** ("New ACL"): the value is typed directly (for example, \`.facebook.com .instagram.com\`). Meant for short lists -a few dozen values- edited occasionally from the panel itself.

**Upload domains**: a text file is uploaded (one domain per line). Meant for large blocklists -from hundreds to millions of domains- typically downloaded from an external provider. Below 200 domains, the upload is stored just like a normal ACL; above that, it's stored as a **file-backed ACL**: its content doesn't live in the database, it lives in a file on the server, and Squid reads it directly from there. A file-backed ACL isn't edited by hand -it makes sense to re-upload the updated file under the same name to replace it, not edit domains one by one.

**"Add to what was already there"** merges the new domains into the ones the ACL already had, without duplicating; **"Replace the whole list"** discards the previous content.

## Available ACL types, with an example

- **Source IP (src)** — where the client connects from. E.g.: \`192.168.1.0/24\`.
- **Destination IP (dst)** — which IP the request targets. E.g.: \`10.0.0.0/8\`.
- **Destination domain (dstdomain)** — which domain. The leading dot includes subdomains. E.g.: \`.facebook.com\` (matches facebook.com, www.facebook.com, m.facebook.com...).
- **Domain regex (dstdom_regex)** — for patterns a plain domain list can't express. E.g.: \`\\.social\\.\` (any domain with ".social." in the middle).
- **URL regex (url_regex)** — against the full URL, not just the domain. E.g.: \`\\.mp4$\` (any URL ending in .mp4, regardless of domain).
- **URL path regex (urlpath_regex)** — like the above, but ignoring the domain and query parameters. E.g.: \`/download/\`.
- **Destination port (port)** — one or more ports, space-separated. E.g.: \`443 80\`.
- **Protocol (proto)** — E.g.: \`HTTP FTP\`.
- **HTTP method (method)** — E.g.: \`GET POST\` (to allow read-only, for instance, POST/PUT/DELETE would be excluded).
- **Time window (time)** — day(s) and time range. E.g.: \`M-F 09:00-17:00\` (Monday to Friday, business hours).
- **Authenticated user (proxy_auth)** — E.g.: \`REQUIRED\` (any authenticated user, whoever it is) or a list of specific usernames.
- **Max connections (maxconn)** — cap on simultaneous connections per client. E.g.: \`10\`.
- **User-Agent (browser)** — based on what the browser/app declares. E.g.: \`Chrome\` (not reliable as a security control: anyone can spoof their User-Agent, more useful for reporting).
- **Response MIME type (rep_mime_type)** — based on the content type the server returns. E.g.: \`video/\` (any response whose type starts with "video/").

## What to expect with a very large list (hundreds of thousands or millions of domains)

- **Uploading the file** is fast (seconds, even with several million lines): each line is validated and it's written once.
- **Re-uploading the exact same file** doesn't rewrite anything -it's detected as identical.
- **"Apply changes"**, however, will take a while -sometimes several minutes- for as long as that ACL exists and is used in some rule, no matter how simple the rest of the change is (a DNS IP, a schedule). This isn't a SquidManager delay: it's Squid itself reloading that entire list into its own memory every time it reloads its configuration, something no proxy fully avoids. The progress bar under "Apply changes" shows which step it's on while you wait.
`.trim(),
  pt: `
## Para que serve

Uma ACL (Access Control List) é uma condição com nome -uma faixa de IPs, uma lista de domínios, um horário, um usuário autenticado- usada depois em **Regras de acesso** para permitir ou negar tráfego. Uma ACL sozinha não bloqueia nada: até que alguma regra a referencie, é só uma definição sem efeito.

## Duas formas de carregar uma ACL

**Manualmente** ("Nova ACL"): o valor é digitado diretamente (por exemplo, \`.facebook.com .instagram.com\`). Pensado para listas curtas -algumas dezenas de valores- editadas de vez em quando pelo próprio painel.

**Carregar domínios**: um arquivo de texto é enviado (um domínio por linha). Pensado para blocklists grandes -de centenas a milhões de domínios- tipicamente baixadas de um provedor externo. Abaixo de 200 domínios, o upload é salvo como uma ACL normal; acima disso, é salvo como **ACL de arquivo**: o conteúdo não vive no banco de dados, vive em um arquivo no servidor, e o Squid o lê diretamente de lá. Uma ACL de arquivo não se edita manualmente -faz sentido reenviar o arquivo atualizado com o mesmo nome para substituí-la, não editar domínio por domínio.

O modo **"Adicionar ao que já havia"** soma os domínios novos aos que a ACL já tinha, sem duplicar; **"Substituir toda a lista"** descarta o conteúdo anterior.

## Tipos de ACL disponíveis, com exemplo

- **IP de origem (src)** — de onde vem o cliente. Ex: \`192.168.1.0/24\`.
- **IP de destino (dst)** — para qual IP vai a requisição. Ex: \`10.0.0.0/8\`.
- **Domínio de destino (dstdomain)** — para qual domínio. O ponto inicial inclui subdomínios. Ex: \`.facebook.com\` (corresponde a facebook.com, www.facebook.com, m.facebook.com...).
- **Regex de domínio (dstdom_regex)** — para padrões que uma lista de domínios simples não consegue expressar. Ex: \`\\.social\\.\` (qualquer domínio que tenha ".social." no meio).
- **Regex de URL (url_regex)** — sobre a URL completa, não só o domínio. Ex: \`\\.mp4$\` (qualquer URL que termine em .mp4, não importa o domínio).
- **Regex de path da URL (urlpath_regex)** — como o anterior, mas ignorando o domínio e os parâmetros de query. Ex: \`/download/\`.
- **Porta de destino (port)** — uma ou várias portas, separadas por espaço. Ex: \`443 80\`.
- **Protocolo (proto)** — Ex: \`HTTP FTP\`.
- **Método HTTP (method)** — Ex: \`GET POST\` (para permitir só leitura, por exemplo, excluiria POST/PUT/DELETE).
- **Horário (time)** — dia(s) e faixa de horário. Ex: \`M-F 09:00-17:00\` (segunda a sexta, horário comercial).
- **Usuário autenticado (proxy_auth)** — Ex: \`REQUIRED\` (qualquer usuário autenticado, não importa qual) ou uma lista de usuários específicos.
- **Conexões máximas (maxconn)** — teto de conexões simultâneas por cliente. Ex: \`10\`.
- **User-Agent (browser)** — conforme o que o navegador/app declara. Ex: \`Chrome\` (pouco confiável como controle de segurança: qualquer um pode falsificar seu User-Agent, mais útil para relatórios).
- **Tipo MIME de resposta (rep_mime_type)** — conforme o tipo de conteúdo que o servidor devolve. Ex: \`video/\` (qualquer resposta cujo tipo comece com "video/").

## O que esperar com uma lista muito grande (centenas de milhares ou milhões de domínios)

- **Carregar o arquivo** é rápido (segundos, mesmo com vários milhões de linhas): cada linha é validada e ele é gravado uma única vez.
- **Reenviar o mesmo arquivo sem mudanças** não reescreve nada -é detectado como idêntico.
- **"Aplicar alterações"**, porém, vai demorar -às vezes vários minutos- enquanto essa ACL existir e estiver em uso em alguma regra, não importa quão simples seja o resto da mudança (um IP de DNS, um horário). Isso não é uma demora do SquidManager: é o próprio Squid recarregando essa lista inteira na sua própria memória toda vez que recarrega sua configuração, algo que nenhum proxy evita totalmente. A barra de progresso abaixo de "Aplicar alterações" mostra em qual etapa está enquanto você espera.
`.trim(),
}
