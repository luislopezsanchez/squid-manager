// Contenido del artículo "Administradores" de la biblioteca de
// Documentación. Ver docsActividadRed.ts para la razón de que esto viva
// aparte de los diccionarios de i18n/*.json.
export const DOC_ADMINISTRADORES: Record<'es' | 'en' | 'pt', string> = {
  es: `
## Para qué sirve

Quién puede entrar **al panel** de SquidManager -no confundir con **Usuarios** (Gestión), que son las credenciales que un cliente le presenta a Squid para navegar. Son dos sistemas de acceso completamente separados.

## Roles

- **Administrador**: gestiona el proxy -crea/edita ACLs, reglas, usuarios, aplica cambios, todo lo que ofrece el panel.
- **Solo lectura**: puede consultar cualquier pantalla, pero no modificar ni aplicar nada. Pensado para auditoría o soporte sin riesgo de un cambio accidental.
- **Superadministrador**: reservado para la primera cuenta (la que se crea al instalar). No se puede asignar este rol a otra cuenta desde el panel.

## Qué pasa al crear uno

Se define usuario, contraseña, email opcional y rol. A diferencia de un usuario del proxy, acá no hay generación automática de contraseña con "guardala ahora" -la define quien crea la cuenta.
`.trim(),
  en: `
## What this is for

Who can log into the SquidManager **panel** -not to be confused with **Users** (Management), which are the credentials a client presents to Squid in order to browse. These are two completely separate access systems.

## Roles

- **Administrator**: manages the proxy -creates/edits ACLs, rules, users, applies changes, everything the panel offers.
- **Read only**: can view any screen, but can't modify or apply anything. Meant for audit or support without the risk of an accidental change.
- **Superadministrator**: reserved for the first account (the one created during installation). This role can't be assigned to another account from the panel.

## What happens when creating one

Username, password, optional email and role are set. Unlike a proxy user, there's no auto-generated password with a "save it now" step here -whoever creates the account sets it.
`.trim(),
  pt: `
## Para que serve

Quem pode entrar **no painel** do SquidManager -não confundir com **Usuários** (Gestão), que são as credenciais que um cliente apresenta ao Squid para navegar. São dois sistemas de acesso completamente separados.

## Papéis

- **Administrador**: gerencia o proxy -cria/edita ACLs, regras, usuários, aplica alterações, tudo que o painel oferece.
- **Somente leitura**: pode consultar qualquer tela, mas não modificar nem aplicar nada. Pensado para auditoria ou suporte sem risco de uma mudança acidental.
- **Superadministrador**: reservado para a primeira conta (a criada na instalação). Esse papel não pode ser atribuído a outra conta pelo painel.

## O que acontece ao criar um

Define-se usuário, senha, e-mail opcional e papel. Diferente de um usuário do proxy, aqui não há geração automática de senha com um passo de "salve agora" -quem cria a conta a define.
`.trim(),
}
