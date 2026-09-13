// Contenido del artículo "Configuración" de la biblioteca de
// Documentación. Ver docsActividadRed.ts para la razón de que esto viva
// aparte de los diccionarios de i18n/*.json.
export const DOC_CONFIGURACION: Record<'es' | 'en' | 'pt', string> = {
  es: `
## Para qué sirve

Ajustes generales de Squid que no encajan en una sección propia -organizados por categoría (Red, Caché, Seguridad, Registros, General) para no tener que buscar entre todos a la vez.

## Ajustes con opciones fijas, no texto libre

Dos ajustes especialmente sensibles a un error de tipeo se muestran como lista desplegable en vez de campo de texto:

- **SSL Bump** (¿interceptar HTTPS para filtrar por dominio, o solo tunelizar sin mirar adentro?): un typo como "flase" en un campo de texto libre se interpretaría como "true" por defecto, activando la interceptación sin que nadie lo pidiera.
- **Método de autenticación** (Basic, Digest, o sin autenticación local): cada uno tiene implicaciones distintas -Digest, por ejemplo, solo sirve para usuarios locales, no LDAP.

## Servidores DNS propios

Si se configuran, hay un botón para probarlos **antes** de guardar -un DNS que no responde no rompe una sola web, deja de resolver todas a la vez, así que conviene confirmarlo antes de aplicar, no después.

## Cuándo tienen efecto

Ningún ajuste de esta página cambia nada en Squid hasta que se pulsa **Aplicar cambios** -guardar acá solo deja el valor listo para la próxima aplicación.
`.trim(),
  en: `
## What this is for

General Squid settings that don't fit in a section of their own -organized by category (Network, Cache, Security, Logging, General) so there's no need to search through all of them at once.

## Settings with fixed options, not free text

Two settings especially sensitive to a typo are shown as a dropdown instead of a text field:

- **SSL Bump** (intercept HTTPS to filter by domain, or just tunnel without looking inside?): a typo like "flase" in a free-text field would be read as "true" by default, turning on interception without anyone asking for it.
- **Authentication method** (Basic, Digest, or no local authentication): each has different implications -Digest, for example, only works for local users, not LDAP.

## Custom DNS servers

If configured, there's a button to test them **before** saving -a DNS server that doesn't respond doesn't break a single website, it stops resolving all of them at once, so it's worth confirming beforehand, not after applying.

## When they take effect

No setting on this page changes anything in Squid until **Apply changes** is clicked -saving here only leaves the value ready for the next apply.
`.trim(),
  pt: `
## Para que serve

Ajustes gerais do Squid que não se encaixam em uma seção própria -organizados por categoria (Rede, Cache, Segurança, Registros, Geral) para não precisar procurar entre todos de uma vez.

## Ajustes com opções fixas, não texto livre

Dois ajustes especialmente sensíveis a um erro de digitação são mostrados como lista suspensa em vez de campo de texto:

- **SSL Bump** (interceptar HTTPS para filtrar por domínio, ou só tunelar sem olhar dentro?): um erro de digitação como "flase" em um campo de texto livre seria interpretado como "true" por padrão, ativando a interceptação sem que ninguém tivesse pedido.
- **Método de autenticação** (Basic, Digest, ou sem autenticação local): cada um tem implicações diferentes -Digest, por exemplo, só funciona para usuários locais, não LDAP.

## Servidores DNS próprios

Se configurados, há um botão para testá-los **antes** de salvar -um DNS que não responde não quebra um único site, ele para de resolver todos de uma vez, então vale confirmar antes, não depois de aplicar.

## Quando têm efeito

Nenhum ajuste desta página muda nada no Squid até que se clique em **Aplicar alterações** -salvar aqui só deixa o valor pronto para a próxima aplicação.
`.trim(),
}
