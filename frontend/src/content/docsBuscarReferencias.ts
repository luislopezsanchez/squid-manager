// Contenido del artículo "Buscar referencias" de la biblioteca de
// Documentación. Ver docsActividadRed.ts para la razón de que esto viva
// aparte de los diccionarios de i18n/*.json.
export const DOC_BUSCAR_REFERENCIAS: Record<'es' | 'en' | 'pt', string> = {
  es: `
## Para qué sirve

Responde a preguntas del tipo "¿por qué está bloqueado facebook.com?" o "¿puedo borrar esta ACL sin romper nada?" sin tener que abrir página por página a buscar a mano. Un único cuadro de búsqueda cruza el término contra **ACLs y categorías, Reglas de acceso, Grupos y Delay pools** a la vez.

## Qué campos mira

- **ACLs y categorías**: nombre, valor (los dominios/IPs que contiene) y descripción.
- **Reglas de acceso**: las ACLs que usa la regla y su descripción.
- **Grupos**: nombre, descripción y **miembros** -buscar un nombre de usuario muestra en qué grupos está, marcando cuál es el miembro que hizo coincidir el grupo-.
- **Delay pools**: descripción y la ACL asociada.

Cada resultado es un enlace directo a la página correspondiente, ya filtrado en el contexto de ese resultado.

## Qué NO busca

No mira **dentro** del contenido de una categoría cargada como archivo (puede tener millones de líneas): ahí la búsqueda es solo por nombre, descripción o metadatos, igual que en el resto del panel. Encontrar un dominio puntual dentro de esas listas queda fuera de esta herramienta.

## Ejemplo

Buscar \`jgarcia\` puede devolver: el usuario en **Grupos** (si pertenece a alguno), y cualquier ACL, regla o delay pool cuya descripción lo mencione. Buscar \`facebook\` típicamente devuelve la categoría o ACL de dominio que lo contiene, y las reglas que la usan para bloquearlo o permitirlo.
`.trim(),
  en: `
## What this is for

Answers questions like "why is facebook.com blocked?" or "can I delete this ACL without breaking anything?" without having to open page after page and search by hand. A single search box cross-checks the term against **ACLs and categories, Access rules, Groups and Delay pools** all at once.

## What it looks at

- **ACLs and categories**: name, value (the domains/IPs it contains) and description.
- **Access rules**: the ACLs the rule uses and its description.
- **Groups**: name, description and **members** -searching a username shows which groups it's in, marking which member matched-.
- **Delay pools**: description and the associated ACL.

Each result is a direct link to the corresponding page, already filtered to that result's context.

## What it does NOT search

It does not look **inside** the contents of a file-backed category (it can have millions of lines): there, the search is only by name, description or metadata, same as the rest of the panel. Finding a specific domain inside those lists is outside the scope of this tool.

## Example

Searching \`jgarcia\` might return: the user in **Groups** (if they belong to one), and any ACL, rule or delay pool whose description mentions them. Searching \`facebook\` typically returns the category or domain ACL that contains it, and the rules that use it to block or allow it.
`.trim(),
  pt: `
## Para que serve

Responde a perguntas do tipo "por que o facebook.com está bloqueado?" ou "posso apagar essa ACL sem quebrar nada?" sem precisar abrir página por página para procurar à mão. Um único campo de busca cruza o termo com **ACLs e categorias, Regras de acesso, Grupos e Delay pools** ao mesmo tempo.

## Quais campos ele verifica

- **ACLs e categorias**: nome, valor (os domínios/IPs que contém) e descrição.
- **Regras de acesso**: as ACLs que a regra usa e sua descrição.
- **Grupos**: nome, descrição e **membros** -buscar um nome de usuário mostra em quais grupos ele está, marcando qual foi o membro que fez o grupo coincidir-.
- **Delay pools**: descrição e a ACL associada.

Cada resultado é um link direto para a página correspondente, já filtrado no contexto daquele resultado.

## O que ele NÃO busca

Não olha **dentro** do conteúdo de uma categoria carregada como arquivo (pode ter milhões de linhas): ali a busca é só por nome, descrição ou metadados, igual ao resto do painel. Encontrar um domínio específico dentro dessas listas fica fora do escopo dessa ferramenta.

## Exemplo

Buscar \`jgarcia\` pode retornar: o usuário em **Grupos** (se pertencer a algum), e qualquer ACL, regra ou delay pool cuja descrição o mencione. Buscar \`facebook\` normalmente retorna a categoria ou ACL de domínio que o contém, e as regras que a usam para bloqueá-lo ou permiti-lo.
`.trim(),
}
