// Contenido del artículo "Auditoría" de la biblioteca de Documentación.
// Ver docsActividadRed.ts para la razón de que esto viva aparte de los
// diccionarios de i18n/*.json.
export const DOC_AUDITORIA: Record<'es' | 'en' | 'pt', string> = {
  es: `
## Para qué sirve

Responde "¿quién cambió qué, y cuándo?" -no sobre el tráfico de los usuarios (eso es Registros/Actividad de red), sino sobre las acciones de los propios administradores del panel: crear o borrar una ACL, cambiar una regla, resetear una contraseña, iniciar sesión (con éxito o sin él).

## Qué se muestra

Cada evento trae quién lo hizo, la acción (crear, actualizar, eliminar, iniciar sesión...), sobre qué tipo de entidad (ACL, regla de acceso, usuario del proxy, grupo, administrador...) y, cuando aplica, el valor anterior y el nuevo -para poder ver exactamente qué cambió, no solo que algo cambió. Se filtra por tipo de entidad y por acción.

Arriba, un resumen: total de eventos, inicios de sesión fallidos, y cambios de configuración -un pico de inicios fallidos suele ser la primera señal de un intento de acceso indebido.

## Por qué importa

Es el rastro que permite responder, meses después, "¿quién desactivó esta regla y cuándo" sin depender de que alguien se acuerde. No se puede editar ni borrar desde el panel: es un registro de solo lectura.
`.trim(),
  en: `
## What this is for

Answers "who changed what, and when?" -not about user traffic (that's Logs/Network Activity), but about the panel administrators' own actions: creating or deleting an ACL, changing a rule, resetting a password, logging in (successfully or not).

## What you see

Each event shows who did it, the action (create, update, delete, log in...), what kind of entity it affected (ACL, access rule, proxy user, group, admin...) and, when it applies, the old and new value -so you can see exactly what changed, not just that something did. It's filtered by entity type and by action.

Above it, a summary: total events, failed logins, and configuration changes -a spike in failed logins is usually the first sign of an unauthorized access attempt.

## Why it matters

It's the trail that lets you answer, months later, "who disabled this rule and when" without depending on anyone remembering. It can't be edited or deleted from the panel: it's a read-only record.
`.trim(),
  pt: `
## Para que serve

Responde "quem mudou o quê, e quando?" -não sobre o tráfego dos usuários (isso é Registros/Atividade de rede), mas sobre as ações dos próprios administradores do painel: criar ou excluir uma ACL, mudar uma regra, redefinir uma senha, fazer login (com sucesso ou não).

## O que é mostrado

Cada evento traz quem fez, a ação (criar, atualizar, excluir, fazer login...), sobre qual tipo de entidade (ACL, regra de acesso, usuário do proxy, grupo, administrador...) e, quando se aplica, o valor anterior e o novo -para poder ver exatamente o que mudou, não só que algo mudou. É filtrado por tipo de entidade e por ação.

Acima, um resumo: total de eventos, logins malsucedidos, e mudanças de configuração -um pico de logins malsucedidos costuma ser o primeiro sinal de uma tentativa de acesso indevido.

## Por que importa

É o rastro que permite responder, meses depois, "quem desativou essa regra e quando" sem depender de alguém se lembrar. Não pode ser editado nem excluído pelo painel: é um registro somente leitura.
`.trim(),
}
