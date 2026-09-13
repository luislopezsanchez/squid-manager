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

## O que esperar com uma lista muito grande (centenas de milhares ou milhões de domínios)

- **Carregar o arquivo** é rápido (segundos, mesmo com vários milhões de linhas): cada linha é validada e ele é gravado uma única vez.
- **Reenviar o mesmo arquivo sem mudanças** não reescreve nada -é detectado como idêntico.
- **"Aplicar alterações"**, porém, vai demorar -às vezes vários minutos- enquanto essa ACL existir e estiver em uso em alguma regra, não importa quão simples seja o resto da mudança (um IP de DNS, um horário). Isso não é uma demora do SquidManager: é o próprio Squid recarregando essa lista inteira na sua própria memória toda vez que recarrega sua configuração, algo que nenhum proxy evita totalmente. A barra de progresso abaixo de "Aplicar alterações" mostra em qual etapa está enquanto você espera.
`.trim(),
}
