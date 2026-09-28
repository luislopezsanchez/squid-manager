// Contenido del artículo "Categorías de dominios" de la biblioteca de
// Documentación. Ver docsActividadRed.ts para la razón de que esto viva
// aparte de los diccionarios de i18n/*.json.
export const DOC_CATEGORIAS: Record<'es' | 'en' | 'pt', string> = {
  es: `
## Para qué sirve

Una categoría es, para Squid, una lista de dominios como cualquier otra ACL de tipo \`dstdomain\` -solo se muestra acá aparte, con un nombre más fácil de reconocer (ej. "Redes sociales" en vez de \`red_sociales_v2\`), en lugar de mezclada con las ACLs técnicas de la página **ACLs**. Se usan igual que cualquier ACL al armar una **Regla de acceso** o un **Delay pool**.

## Tres formas de cargar dominios

- **A mano**: escribiendo la lista, uno por línea, en el formulario de creación/edición.
- **Desde archivo**: para listas grandes. Por debajo de 200 dominios la categoría queda "inline" (se edita como cualquier otra); por encima pasa a "archivo" -un archivo aparte que Squid lee directo-, y para actualizarla hay que volver a subir un archivo (ya no se edita el texto a mano).
- **Categorías predefinidas (HaGeZi)**: un botón carga 9 listas públicas ya armadas (apuestas, contenido adulto, piratería, redes sociales, sitios falsos, evasión del proxy, pop-ups, amenazas de seguridad, acortadores de URL), con nombre técnico \`hagezi_*\`.

## Sincronización automática

Una categoría puede tener una **URL de sincronización** (siempre \`https://\`): un proceso en segundo plano la refresca sola una vez al día, sumando dominios nuevos de la fuente **sin borrar** los que el admin haya agregado a mano encima. Las categorías HaGeZi ya vienen con esto configurado. También se puede forzar "Sincronizar ahora" sin esperar al refresco diario, o desconectar la sincronización y dejarla en modo manual.

## Ejemplo

Categoría \`redes_sociales\`, nombre para mostrar "Redes sociales", con \`.facebook.com\`, \`.instagram.com\`, \`.tiktok.com\`. Después, en **Reglas de acceso**, una regla \`deny redes_sociales\` la bloquea para todos, o \`allow redes_sociales\` antes de esa regla la exime para un grupo puntual.
`.trim(),
  en: `
## What this is for

For Squid, a category is a list of domains just like any other \`dstdomain\` ACL -it's only shown separately here, under a more recognizable name (e.g. "Social media" instead of \`social_media_v2\`), instead of mixed in with the technical ACLs on the **ACLs** page. They're used the same as any ACL when building an **Access rule** or a **Delay pool**.

## Three ways to load domains

- **By hand**: typing the list, one per line, in the create/edit form.
- **From a file**: for large lists. Below 200 domains the category stays "inline" (edited like any other); above that it becomes "file-backed" -a separate file Squid reads directly-, and updating it means uploading a file again (the text can no longer be edited by hand).
- **Predefined categories (HaGeZi)**: a button loads 9 ready-made public lists (gambling, adult content, piracy, social media, fake sites, proxy evasion, pop-ups, security threats, URL shorteners), with the technical name \`hagezi_*\`.

## Automatic synchronization

A category can have a **sync URL** (always \`https://\`): a background process refreshes it on its own once a day, adding new domains from the source **without deleting** any the admin added by hand on top. HaGeZi categories already come with this configured. You can also force "Sync now" without waiting for the daily refresh, or disconnect the sync and leave it in manual mode.

## Example

Category \`social_media\`, display name "Social media", with \`.facebook.com\`, \`.instagram.com\`, \`.tiktok.com\`. Then, in **Access rules**, a \`deny social_media\` rule blocks it for everyone, or an \`allow social_media\` rule before that one exempts a specific group.
`.trim(),
  pt: `
## Para que serve

Para o Squid, uma categoria é uma lista de domínios como qualquer outra ACL do tipo \`dstdomain\` -só é mostrada aqui separadamente, com um nome mais fácil de reconhecer (ex. "Redes sociais" em vez de \`redes_sociais_v2\`), em vez de misturada com as ACLs técnicas da página **ACLs**. São usadas do mesmo jeito que qualquer ACL ao montar uma **Regra de acesso** ou um **Delay pool**.

## Três formas de carregar domínios

- **À mão**: digitando a lista, um por linha, no formulário de criação/edição.
- **A partir de arquivo**: para listas grandes. Abaixo de 200 domínios a categoria fica "inline" (é editada como qualquer outra); acima disso passa a "arquivo" -um arquivo separado que o Squid lê diretamente-, e para atualizá-la é preciso enviar um novo arquivo (o texto não é mais editado à mão).
- **Categorias predefinidas (HaGeZi)**: um botão carrega 9 listas públicas já prontas (apostas, conteúdo adulto, pirataria, redes sociais, sites falsos, evasão de proxy, pop-ups, ameaças de segurança, encurtadores de URL), com nome técnico \`hagezi_*\`.

## Sincronização automática

Uma categoria pode ter uma **URL de sincronização** (sempre \`https://\`): um processo em segundo plano a atualiza sozinha uma vez por dia, somando domínios novos da fonte **sem apagar** os que o admin tenha adicionado à mão por cima. As categorias HaGeZi já vêm com isso configurado. Também é possível forçar "Sincronizar agora" sem esperar a atualização diária, ou desconectar a sincronização e deixar em modo manual.

## Exemplo

Categoria \`redes_sociais\`, nome para exibição "Redes sociais", com \`.facebook.com\`, \`.instagram.com\`, \`.tiktok.com\`. Depois, em **Regras de acesso**, uma regra \`deny redes_sociais\` a bloqueia para todos, ou \`allow redes_sociais\` antes dessa regra isenta um grupo específico.
`.trim(),
}
