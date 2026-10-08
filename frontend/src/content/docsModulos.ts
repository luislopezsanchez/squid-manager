// Contenido del artículo "Módulos" de la biblioteca de Documentación.
export const DOC_MODULOS: Record<'es' | 'en' | 'pt', string> = {
  es: `
## Para qué sirve

No todas las instalaciones usan todo. **Módulos** te deja encender o apagar las partes opcionales del panel (Asistente de IA, Panel central, análisis avanzados…) para que el menú solo muestre lo que realmente usas y se deje de trabajar en segundo plano en lo que no.

## Cómo se usa

1. Abre **Sistema → Módulos**.
2. Activa o desactiva el interruptor del módulo.
3. El cambio se aplica al instante: el menú se actualiza y, si alguien entra por enlace directo a un módulo apagado, verá un aviso con el botón para activarlo (solo administradores).

## Valores por defecto

Todos los módulos vienen **activos**, salvo **Panel central** (se habilita a mano porque solo tiene sentido cuando vas a vigilar varios servidores desde uno) y **Portal de autoservicio de usuarios** (también apagado: ver la ayuda de Usuarios).

## Ejemplo

Una sucursal con un solo Squid y sin cuenta de IA: apaga **Asistente** y deja Panel central apagado. El menú queda más corto y no se indexa la documentación para el asistente.

## Qué no hace

Apagar un módulo **no borra** sus datos ni su configuración: al volver a encenderlo, todo sigue donde estaba. Los módulos forman parte del backup.
`.trim(),
  en: `
## What this is for

Not every installation uses everything. **Modules** lets you switch the optional parts of the panel on or off (AI Assistant, Central panel, advanced analytics…) so the menu only shows what you really use and nothing runs in the background for what you don't.

## How to use it

1. Open **System → Modules**.
2. Toggle the module switch.
3. The change applies instantly: the menu updates and, if someone opens a disabled module through a direct link, they get a notice with a button to enable it (administrators only).

## Defaults

All modules ship **enabled**, except **Central panel**, which you enable manually because it only makes sense when you monitor several servers from one.

## Example

A branch office with a single Squid and no AI account: turn off **Assistant** and leave Central panel off. The menu gets shorter and the docs are not indexed for the assistant.

## What it does not do

Turning a module off **does not delete** its data or settings: turn it back on and everything is where you left it. Modules are included in backups.
`.trim(),
  pt: `
## Para que serve

Nem toda instalação usa tudo. **Módulos** permite ligar ou desligar as partes opcionais do painel (Assistente de IA, Painel central, análises avançadas…) para que o menu mostre só o que você realmente usa e nada rode em segundo plano para o que não usa.

## Como usar

1. Abra **Sistema → Módulos**.
2. Ative ou desative o interruptor do módulo.
3. A mudança vale na hora: o menu é atualizado e, se alguém abrir um módulo desligado por link direto, verá um aviso com o botão para ativá-lo (somente administradores).

## Valores padrão

Todos os módulos vêm **ativos**, exceto o **Painel central**, que se habilita manualmente porque só faz sentido quando você vigia vários servidores a partir de um.

## Exemplo

Uma filial com um único Squid e sem conta de IA: desligue o **Assistente** e deixe o Painel central desligado. O menu fica mais curto e a documentação não é indexada para o assistente.

## O que não faz

Desligar um módulo **não apaga** seus dados nem sua configuração: ao religá-lo, tudo continua onde estava. Os módulos fazem parte do backup.
`.trim(),
}
