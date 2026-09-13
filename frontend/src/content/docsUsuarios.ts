// Contenido del artículo "Usuarios" de la biblioteca de Documentación.
// Ver docsActividadRed.ts para la razón de que esto viva aparte de los
// diccionarios de i18n/*.json.
export const DOC_USUARIOS: Record<'es' | 'en' | 'pt', string> = {
  es: `
## Para qué sirve

Administra quién puede autenticarse contra el proxy -no quién tiene acceso al panel de administración (eso son los **Administradores**, en Sistema), sino las credenciales que un navegador o una app le presenta a Squid para poder navegar cuando la autenticación está activada.

## Dos orígenes, una sola pantalla

- **Locales**: creados acá directamente, con su propia contraseña.
- **LDAP**: sincronizados desde un directorio (Active Directory / LDAP, ver esa sección en Integraciones). No se crean ni se les cambia la contraseña desde este panel -eso lo maneja el directorio-, pero sí se pueden habilitar o deshabilitar.

Ambos orígenes se ven en la misma tabla, con filtro por origen y por estado.

## Bloquear acceso vs. eliminar

**Bloquear acceso** deshabilita al usuario: no puede navegar hasta que se lo vuelva a habilitar, pero queda el registro (útil para una baja temporal, una licencia, una investigación). Eliminar borra la cuenta por completo.

## Contraseña de un usuario local

Se puede generar una automáticamente o establecer una propia. Una vez generada, **hay que guardarla en ese momento**: no se puede volver a consultar después de cerrar esa ventana -solo queda el hash, como corresponde a cualquier sistema de autenticación serio.

## Vencimiento

Un usuario local puede tener fecha de vencimiento: pasada esa fecha, deja de poder autenticarse aunque siga marcado como habilitado -pensado para accesos temporales (un contratista, un invitado) sin tener que acordarse de deshabilitarlo a mano.
`.trim(),
  en: `
## What this is for

Manages who can authenticate against the proxy -not who has access to the admin panel (that's **Administrators**, under System), but the credentials a browser or an app presents to Squid to be allowed to browse when authentication is turned on.

## Two sources, one screen

- **Local**: created here directly, with their own password.
- **LDAP**: synced from a directory (Active Directory / LDAP, see that section under Integrations). They're not created nor have their password changed from this panel -the directory handles that-, but they can be enabled or disabled.

Both sources show up in the same table, with a filter by source and by status.

## Block access vs. delete

**Block access** disables the user: they can't browse until re-enabled, but the record stays (useful for a temporary leave, a license, an investigation). Delete removes the account entirely.

## A local user's password

It can be generated automatically or set manually. Once generated, **it has to be saved right then**: it can't be looked up again after closing that window -only the hash remains, as with any serious authentication system.

## Expiration

A local user can have an expiration date: past that date, they stop being able to authenticate even if still marked as enabled -meant for temporary access (a contractor, a guest) without having to remember to disable it by hand.
`.trim(),
  pt: `
## Para que serve

Administra quem pode se autenticar no proxy -não quem tem acesso ao painel de administração (isso são os **Administradores**, em Sistema), mas as credenciais que um navegador ou um app apresenta ao Squid para poder navegar quando a autenticação está ativada.

## Duas origens, uma só tela

- **Locais**: criados aqui diretamente, com sua própria senha.
- **LDAP**: sincronizados de um diretório (Active Directory / LDAP, ver essa seção em Integrações). Não são criados nem têm a senha alterada por este painel -isso é gerenciado pelo diretório-, mas podem ser habilitados ou desabilitados.

As duas origens aparecem na mesma tabela, com filtro por origem e por status.

## Bloquear acesso vs. excluir

**Bloquear acesso** desabilita o usuário: ele não navega até ser habilitado de novo, mas o registro permanece (útil para um afastamento temporário, uma licença, uma investigação). Excluir apaga a conta por completo.

## Senha de um usuário local

Pode ser gerada automaticamente ou definida manualmente. Uma vez gerada, **precisa ser salva naquele momento**: não pode ser consultada de novo depois de fechar aquela janela -só fica o hash, como em qualquer sistema de autenticação sério.

## Vencimento

Um usuário local pode ter data de vencimento: passada essa data, ele deixa de conseguir se autenticar mesmo continuando marcado como habilitado -pensado para acessos temporários (um prestador, um convidado) sem precisar lembrar de desabilitá-lo manualmente.
`.trim(),
}
