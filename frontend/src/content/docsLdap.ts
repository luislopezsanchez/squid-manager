// Contenido del artículo "LDAP" de la biblioteca de Documentación. Ver
// docsActividadRed.ts para la razón de que esto viva aparte de los
// diccionarios de i18n/*.json.
export const DOC_LDAP: Record<'es' | 'en' | 'pt', string> = {
  es: `
## Para qué sirve

Conecta SquidManager a un directorio (Active Directory u OpenLDAP) para que los usuarios del proxy no haya que crearlos uno por uno a mano -se sincronizan desde ahí, con la misma cuenta y contraseña que ya usan para todo lo demás.

## Configuración

Servidor, DN de bind (la cuenta de servicio que hace las búsquedas), base de búsqueda, y dos filtros LDAP: uno para autenticar un login puntual (\`user_filter\`, con \`%s\` como marcador del nombre de usuario) y otro para la sincronización masiva (\`sync_filter\`, qué objetos del directorio cuentan como "usuario"). Hay valores de partida según el tipo de directorio (AD, OpenLDAP, inetOrgPerson), pero son solo un punto de partida -los campos son texto libre por si el esquema real es distinto.

## Probar antes de sincronizar

Con un usuario y contraseña reales del directorio, el botón de prueba confirma que el bind funciona, que el filtro de login encuentra a ese usuario, y que la contraseña es correcta -sin esto, un error de configuración (una base de búsqueda mal escrita, por ejemplo) recién se notaría cuando un usuario real no pudiera navegar.

## Sincronizar

Trae del directorio a todos los usuarios que cumplen \`sync_filter\` y los deja visibles en **Usuarios** (Gestión), marcados como origen LDAP. No crea contraseñas locales: la autenticación real, cuando un usuario navega, sigue yendo contra el directorio. Desde Usuarios se pueden habilitar o deshabilitar, pero no editar su contraseña -eso lo sigue manejando el directorio.
`.trim(),
  en: `
## What this is for

Connects SquidManager to a directory (Active Directory or OpenLDAP) so proxy users don't have to be created one by one by hand -they're synced from there, with the same account and password they already use for everything else.

## Configuration

Server, bind DN (the service account that does the lookups), search base, and two LDAP filters: one for authenticating a single login (\`user_filter\`, with \`%s\` as the username placeholder) and another for the bulk sync (\`sync_filter\`, which directory objects count as a "user"). There are starting presets by directory type (AD, OpenLDAP, inetOrgPerson), but they're just a starting point -the fields are free text in case the real schema is different.

## Test before syncing

With a real username and password from the directory, the test button confirms the bind works, the login filter finds that user, and the password is correct -without this, a configuration error (a mistyped search base, for example) would only show up when a real user couldn't browse.

## Sync

Pulls in every user from the directory that matches \`sync_filter\` and makes them visible in **Users** (Management), marked as LDAP-sourced. It doesn't create local passwords: real authentication, when a user browses, still goes against the directory. From Users they can be enabled or disabled, but not have their password edited -the directory still handles that.
`.trim(),
  pt: `
## Para que serve

Conecta o SquidManager a um diretório (Active Directory ou OpenLDAP) para que os usuários do proxy não precisem ser criados um a um manualmente -são sincronizados de lá, com a mesma conta e senha que já usam para tudo o mais.

## Configuração

Servidor, DN de bind (a conta de serviço que faz as buscas), base de busca, e dois filtros LDAP: um para autenticar um login pontual (\`user_filter\`, com \`%s\` como marcador do nome de usuário) e outro para a sincronização em massa (\`sync_filter\`, quais objetos do diretório contam como "usuário"). Há valores de partida conforme o tipo de diretório (AD, OpenLDAP, inetOrgPerson), mas são só um ponto de partida -os campos são texto livre caso o esquema real seja diferente.

## Testar antes de sincronizar

Com um usuário e senha reais do diretório, o botão de teste confirma que o bind funciona, que o filtro de login encontra esse usuário, e que a senha está correta -sem isso, um erro de configuração (uma base de busca escrita errada, por exemplo) só seria percebido quando um usuário real não conseguisse navegar.

## Sincronizar

Traz do diretório todos os usuários que atendem \`sync_filter\` e os deixa visíveis em **Usuários** (Gestão), marcados como origem LDAP. Não cria senhas locais: a autenticação real, quando um usuário navega, continua indo contra o diretório. Em Usuários eles podem ser habilitados ou desabilitados, mas não ter a senha editada -isso continua sendo gerenciado pelo diretório.
`.trim(),
}
