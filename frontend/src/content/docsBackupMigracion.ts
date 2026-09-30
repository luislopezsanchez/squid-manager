// Contenido del artículo "Backup y migración" de la biblioteca de
// Documentación. Ver docsActividadRed.ts para la razón de que esto viva
// aparte de los diccionarios de i18n/*.json.
export const DOC_BACKUP_MIGRACION: Record<'es' | 'en' | 'pt', string> = {
  es: `
## Para qué sirve

Tres operaciones distintas, agrupadas acá porque todas mueven configuración hacia adentro o hacia afuera del panel.

## Backup y restauración

**Exportar** descarga un JSON con toda la configuración: ajustes, ACLs, reglas, usuarios (sin contraseñas), delay pools, grupos, usuarios LDAP. **Restaurar** sube ese mismo archivo y aplica su contenido -pensado para mudar de servidor, o para volver a un estado conocido.

Una ACL de archivo (una carga masiva de dominios, ver esa sección) no incluye su contenido en el backup -solo cuántos dominios tenía-, porque podría pesar cientos de MB. Al restaurar, esa ACL se recrea vacía y el aviso lo deja explícito: hay que volver a cargar esa lista desde **ACLs > Cargar dominios**.

## Descargar squid.conf

Un botón aparte para bajar el \`squid.conf\` tal como está generado ahora mismo -para inspeccionarlo, o para tenerlo a mano si hace falta depurar algo fuera del panel.

## Importar un squid.conf tradicional

Para migrar un Squid configurado a mano hacia SquidManager: se sube el \`squid.conf\` (y los archivos que incluya con \`include\`, si los usa) y el panel arma un **informe de qué se puede importar, sin aplicar nada todavía**. Recién en un segundo paso, ya revisado el informe, se decide aplicar.

Qué se importa y qué no:
- ACLs, reglas de acceso, delay pools con formato estándar, y un proxy padre simple -este último se importa **desactivado**, para probarlo antes de activarlo.
- Los usuarios (htpasswd) **no** se importan -hay que crearlos a mano después.
- NTLM/AD, grupos externos, squidGuard y otras directivas sin equivalente en el panel se listan en el informe como no soportadas, nunca se importan en silencio.

## Formatos aceptados al migrar

Al importar desde otro Squid puedes subir la carpeta de configuración comprimida en **.zip, .tar.gz, .rar o .7z** (sin contraseña) o sus archivos sueltos. Para \`.rar\` y \`.7z\` el servidor necesita el paquete \`libarchive-tools\`, que el instalador ya incluye.

## DNS del Squid de origen

Si el Squid de origen usaba servidores DNS que **no responden desde este servidor** (típico al cambiar de red), el informe lo avisa antes de importar y, por defecto, **no los importa**: con un DNS inalcanzable, Squid no podría resolver nombres y «Aplicar cambios» se negaría a propósito. Puedes marcar la casilla si aun así quieres importarlos.
`.trim(),
  en: `
## What this is for

Three distinct operations, grouped here because all of them move configuration in or out of the panel.

## Backup and restore

**Export** downloads a JSON with the whole configuration: settings, ACLs, rules, users (without passwords), delay pools, groups, LDAP users. **Restore** uploads that same file and applies its content -meant for moving to a new server, or going back to a known state.

A file-backed ACL (a bulk domain upload, see that section) doesn't include its content in the backup -only how many domains it had-, because it could weigh hundreds of MB. When restoring, that ACL is recreated empty and the warning says so explicitly: that list needs to be re-uploaded from **ACLs > Upload domains**.

## Download squid.conf

A separate button to download the \`squid.conf\` exactly as it's generated right now -to inspect it, or to have it on hand if something needs debugging outside the panel.

## Importing a traditional squid.conf

To migrate a hand-configured Squid into SquidManager: the \`squid.conf\` is uploaded (and any files it includes via \`include\`, if used) and the panel builds a **report of what can be imported, without applying anything yet**. Only in a second step, once the report is reviewed, is it applied.

What's imported and what isn't:
- ACLs, access rules, delay pools in the standard format, and a simple parent proxy -the latter is imported **disabled**, to test it before turning it on.
- Users (htpasswd) are **not** imported -they need to be created by hand afterward.
- NTLM/AD, external groups, squidGuard and other directives with no equivalent in the panel are listed in the report as unsupported, never imported silently.

## Accepted formats when migrating

When importing from another Squid you can upload the configuration folder compressed as **.zip, .tar.gz, .rar or .7z** (no password) or its loose files. For \`.rar\` and \`.7z\` the server needs the \`libarchive-tools\` package, which the installer already includes.

## DNS of the source Squid

If the source Squid used DNS servers that **do not respond from this server** (typical when changing networks), the report warns you before importing and, by default, **does not import them**: with an unreachable DNS Squid could not resolve names and "Apply changes" would refuse on purpose. You can tick the box if you still want them.
`.trim(),
  pt: `
## Para que serve

Três operações distintas, agrupadas aqui porque todas movimentam configuração para dentro ou para fora do painel.

## Backup e restauração

**Exportar** baixa um JSON com toda a configuração: ajustes, ACLs, regras, usuários (sem senhas), delay pools, grupos, usuários LDAP. **Restaurar** envia esse mesmo arquivo e aplica seu conteúdo -pensado para trocar de servidor, ou para voltar a um estado conhecido.

Uma ACL de arquivo (um upload em massa de domínios, ver essa seção) não inclui seu conteúdo no backup -só quantos domínios ela tinha-, porque poderia pesar centenas de MB. Ao restaurar, essa ACL é recriada vazia e o aviso deixa isso explícito: essa lista precisa ser reenviada em **ACLs > Carregar domínios**.

## Baixar squid.conf

Um botão separado para baixar o \`squid.conf\` exatamente como está gerado agora -para inspecioná-lo, ou para tê-lo em mãos caso seja preciso depurar algo fora do painel.

## Importar um squid.conf tradicional

Para migrar um Squid configurado manualmente para o SquidManager: envia-se o \`squid.conf\` (e os arquivos que ele inclua via \`include\`, se usar) e o painel monta um **relatório do que pode ser importado, sem aplicar nada ainda**. Só em uma segunda etapa, já revisado o relatório, decide-se aplicar.

O que é importado e o que não é:
- ACLs, regras de acesso, delay pools no formato padrão, e um proxy pai simples -este último é importado **desativado**, para testá-lo antes de ativar.
- Os usuários (htpasswd) **não** são importados -precisam ser criados manualmente depois.
- NTLM/AD, grupos externos, squidGuard e outras diretivas sem equivalente no painel são listadas no relatório como não suportadas, nunca importadas silenciosamente.

## Formatos aceitos ao migrar

Ao importar de outro Squid você pode enviar a pasta de configuração compactada em **.zip, .tar.gz, .rar ou .7z** (sem senha) ou seus arquivos soltos. Para \`.rar\` e \`.7z\` o servidor precisa do pacote \`libarchive-tools\`, que o instalador já inclui.

## DNS do Squid de origem

Se o Squid de origem usava servidores DNS que **não respondem a partir deste servidor** (típico ao mudar de rede), o relatório avisa antes de importar e, por padrão, **não os importa**: com um DNS inalcançável o Squid não resolveria nomes e «Aplicar alterações» se recusaria de propósito. Você pode marcar a caixa se ainda assim quiser importá-los.
`.trim(),
}
