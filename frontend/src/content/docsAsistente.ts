// Contenido del artículo "Asistente AI" de la biblioteca de Documentación.
// Ver docsActividadRed.ts para la razón de que esto viva aparte de los
// diccionarios de i18n/*.json.
export const DOC_ASISTENTE: Record<'es' | 'en' | 'pt', string> = {
  es: `
## Para qué sirve

Un buscador con lenguaje natural sobre la documentación del proyecto (\`README.md\` y \`docs/*.md\`, en español) -no un agente que actúa sobre el proxy real. Responde preguntas de uso citando de qué archivo y sección salió la respuesta. Apagado por defecto, igual que LDAP/Kerberos/Syslog.

## Dos API keys, de dos servicios distintos

1. Un **proveedor de chat** (Gemini, Ollama Cloud, NVIDIA NIM o Groq) para generar la respuesta.
2. **Jina AI**, siempre, para la búsqueda semántica (embeddings) -sin importar qué proveedor de chat elijas. Las dos se pueden probar desde el panel antes de guardar, y ninguna se vuelve a mostrar una vez guardada.

## Qué ve, y qué no

Solo lee \`README.md\` y \`docs/*.md\` en español -nunca la base de datos, el \`squid.conf\` real ni credenciales. El contenido de la documentación y cada pregunta que se hace viajan a esos dos servicios externos.

## Reindexar

La documentación **no se reindexa sola**: hay que pulsar "Reindexar documentación" después de activar el asistente por primera vez, o de cualquier cambio en la documentación (incluida una actualización de SquidManager). Es una reindexación completa, no incremental -borra todo y vuelve a generarlo desde cero.

## Modo agéntico (fase 1)

Además de responder con la documentación, puede consultar ACLs, reglas, grupos y ajustes reales de este servidor para diagnosticar, y proponer cambios de configuración -nunca los aplica solo, siempre pide confirmación. No disponible con Ollama Cloud todavía -hace falta Gemini, Groq o NVIDIA NIM.

## Quién puede preguntar

Cualquier administrador, **incluida una cuenta de solo lectura**: es una consulta sobre documentación pública, no una acción sobre el proxy.

## Requisito: pgvector

La búsqueda semántica guarda los embeddings en una columna vectorial de Postgres. Se instala sola tanto en Docker como en instalación nativa, incluso al actualizar una instalación existente.
`.trim(),
  en: `
## What this is for

A natural-language search engine over the project's documentation (\`README.md\` and \`docs/*.md\`, in Spanish) -not an agent that acts on the real proxy. It answers usage questions citing which file and section the answer came from. Off by default, same as LDAP/Kerberos/Syslog.

## Two API keys, from two different services

1. A **chat provider** (Gemini, Ollama Cloud, NVIDIA NIM or Groq) to generate the answer.
2. **Jina AI**, always, for the semantic search (embeddings) -no matter which chat provider you pick. Both can be tested from the panel before saving, and neither is shown again once saved.

## What it can see, and what it can't

It only reads \`README.md\` and \`docs/*.md\` in Spanish -never the database, the real \`squid.conf\`, or credentials. The documentation content and every question asked travel to those two external services.

## Reindexing

The documentation **doesn't reindex itself**: press "Reindex documentation" after enabling the assistant for the first time, or after any change to the documentation (including a SquidManager update). It's a full reindex, not incremental -it erases everything and rebuilds from scratch.

## Agentic mode (phase 1)

Besides answering from the documentation, it can check real ACLs, rules, groups and settings on this server to diagnose issues, and propose configuration changes -it never applies them on its own, it always asks for confirmation. Not available with Ollama Cloud yet -use Gemini, Groq or NVIDIA NIM.

## Who can ask

Any administrator, **including a read-only account**: it's a query over public documentation, not an action on the proxy.

## Requirement: pgvector

Semantic search stores the embeddings in a Postgres vector column. It installs itself both in Docker and in a native install, even when updating an existing installation.
`.trim(),
  pt: `
## Para que serve

Um buscador com linguagem natural sobre a documentação do projeto (\`README.md\` e \`docs/*.md\`, em espanhol) -não um agente que age sobre o proxy real. Responde perguntas de uso citando de qual arquivo e seção veio a resposta. Desativado por padrão, assim como LDAP/Kerberos/Syslog.

## Duas chaves de API, de dois serviços diferentes

1. Um **provedor de chat** (Gemini, Ollama Cloud, NVIDIA NIM ou Groq) para gerar a resposta.
2. **Jina AI**, sempre, para a busca semântica (embeddings) -não importa qual provedor de chat você escolher. As duas podem ser testadas no painel antes de salvar, e nenhuma é mostrada de novo depois de salva.

## O que ele vê, e o que não vê

Só lê \`README.md\` e \`docs/*.md\` em espanhol -nunca o banco de dados, o \`squid.conf\` real nem credenciais. O conteúdo da documentação e cada pergunta feita viajam para esses dois serviços externos.

## Reindexar

A documentação **não se reindexa sozinha**: é preciso clicar em "Reindexar documentação" depois de ativar o assistente pela primeira vez, ou depois de qualquer mudança na documentação (inclusive uma atualização do SquidManager). É uma reindexação completa, não incremental -apaga tudo e reconstrói do zero.

## Modo agêntico (fase 1)

Além de responder com base na documentação, pode consultar ACLs, regras, grupos e ajustes reais deste servidor para diagnosticar, e propor mudanças de configuração -nunca as aplica sozinho, sempre pede confirmação. Ainda não disponível com o Ollama Cloud -use Gemini, Groq ou NVIDIA NIM.

## Quem pode perguntar

Qualquer administrador, **incluindo uma conta somente leitura**: é uma consulta sobre documentação pública, não uma ação sobre o proxy.

## Requisito: pgvector

A busca semântica guarda os embeddings numa coluna vetorial do Postgres. Ele se instala sozinho tanto no Docker quanto numa instalação nativa, mesmo ao atualizar uma instalação existente.
`.trim(),
}
