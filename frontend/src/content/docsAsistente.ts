// Contenido del artículo "Asistente AI" de la biblioteca de Documentación.
// Ver docsActividadRed.ts para la razón de que esto viva aparte de los
// diccionarios de i18n/*.json.
export const DOC_ASISTENTE: Record<'es' | 'en' | 'pt', string> = {
  es: `
## Para qué sirve

Un asistente al que se le pregunta en lenguaje natural cómo usar el panel («¿cómo bloqueo un sitio solo en horario de oficina?», «¿qué es un delay pool?») y responde **citando de qué archivo y sección de la documentación sale la respuesta**. Opcionalmente, en **modo agéntico**, también consulta la configuración real de este servidor para diagnosticar y propone ACLs que tú confirmas. Apagado por defecto, igual que LDAP/Kerberos/Syslog.

## Proveedor de IA: tú eliges

Se elige **uno** de una lista: Anthropic (Claude), OpenAI, Gemini, Groq, OpenRouter, DeepSeek, Mistral, NVIDIA NIM, Ollama Cloud, **Ollama en tu red** (los datos no salen de tu red) o **Personalizado** (cualquier servicio compatible con OpenAI: vLLM, LM Studio, LiteLLM, Azure…, con su URL y su clave). La clave es opcional en Ollama en tu red y en los servicios propios que no la piden. «Probar conexión» lista los modelos reales del proveedor elegido, y la clave no se vuelve a mostrar una vez guardada.

## La búsqueda en la documentación es local

No hace falta ningún segundo servicio ni clave: la búsqueda se hace dentro de tu propio servidor (texto completo de PostgreSQL), en el idioma del panel (español, inglés o portugués) y sin enviar la documentación a nadie. La documentación se **indexa sola** al arrancar y cada vez que cambia (por ejemplo, tras actualizar), e incluye la ayuda de cada pantalla del panel. El botón «Reindexar documentación» queda para forzarlo a mano.

## Qué ve, y qué no

Por defecto solo lee la documentación del proyecto -nunca la base de datos, el \`squid.conf\` real, usuarios ni credenciales. Lo que viaja al proveedor de IA es la pregunta, los fragmentos de documentación relevantes y, en modo agéntico, los datos que el asistente consulta (ver abajo).

## Modo agéntico

Con el modo agéntico activado, el asistente puede consultar **ACLs, reglas de acceso, grupos, ajustes de Squid y el estado de «Aplicar cambios»** de este servidor para diagnosticar contra tu configuración real (por ejemplo, «¿por qué no puede entrar el grupo X a este sitio?»). Lo que consulta es estructural -nombres, tipos y cantidades-: nunca el contenido de las listas de archivo, ni usuarios, ni líneas de registro. Puede **proponer crear una ACL**, pero **nunca la crea ni la aplica solo**: aparece como propuesta y la creas tú con el mismo botón de siempre. No disponible con Ollama Cloud.

## Quién puede preguntar

Cualquier administrador, **incluida una cuenta de solo lectura**: es una consulta, no una acción sobre el proxy.

## Requisito: pgvector

La base de datos usa la extensión pgvector. Se instala sola tanto en Docker como en instalación nativa, incluso al actualizar una instalación existente.
`.trim(),
  en: `
## What this is for

An assistant you ask in natural language how to use the panel ("how do I block a site only during office hours?", "what is a delay pool?"), and it answers **citing which file and section of the documentation the answer comes from**. Optionally, in **agentic mode**, it also reads this server's real configuration to diagnose issues and proposes ACLs that you confirm. Off by default, like LDAP/Kerberos/Syslog.

## AI provider: your choice

You pick **one** from a list: Anthropic (Claude), OpenAI, Gemini, Groq, OpenRouter, DeepSeek, Mistral, NVIDIA NIM, Ollama Cloud, **Ollama on your network** (data never leaves your network) or **Custom** (any OpenAI-compatible service: vLLM, LM Studio, LiteLLM, Azure…, with its own URL and key). The key is optional for Ollama on your network and for self-hosted services that don't ask for one. "Test connection" lists the provider's real models, and the key is never shown again once saved.

## The documentation search is local

No second service or key is needed: the search runs inside your own server (PostgreSQL full-text search), in the panel's language (Spanish, English or Portuguese), and the documentation is not sent to anyone. The documentation **indexes itself** at startup and whenever it changes (for example, after an update), and it includes the help for every screen of the panel. The "Reindex documentation" button is there to force it by hand.

## What it can see, and what it can't

By default it only reads the project's documentation -never the database, the real \`squid.conf\`, users or credentials. What travels to the AI provider is the question, the relevant documentation fragments and, in agentic mode, the data the assistant queries (see below).

## Agentic mode

With agentic mode on, the assistant can read this server's **ACLs, access rules, groups, Squid settings and the "Apply changes" state** to diagnose against your real configuration (for example, "why can't group X reach this site?"). What it reads is structural -names, types and counts-: never the contents of file-based lists, users or log lines. It can **propose creating an ACL**, but **it never creates or applies anything on its own**: it shows up as a proposal and you create it with the usual button. Not available with Ollama Cloud.

## Who can ask

Any administrator, **including a read-only account**: it's a query, not an action on the proxy.

## Requirement: pgvector

The database uses the pgvector extension. It installs itself both in Docker and in a native install, even when updating an existing installation.
`.trim(),
  pt: `
## Para que serve

Um assistente ao qual você pergunta em linguagem natural como usar o painel («como bloqueio um site só no horário comercial?», «o que é um delay pool?») e que responde **citando de qual arquivo e seção da documentação sai a resposta**. Opcionalmente, no **modo agêntico**, também consulta a configuração real deste servidor para diagnosticar e propõe ACLs que você confirma. Desligado por padrão, como LDAP/Kerberos/Syslog.

## Provedor de IA: você escolhe

Escolhe-se **um** de uma lista: Anthropic (Claude), OpenAI, Gemini, Groq, OpenRouter, DeepSeek, Mistral, NVIDIA NIM, Ollama Cloud, **Ollama na sua rede** (os dados não saem da sua rede) ou **Personalizado** (qualquer serviço compatível com OpenAI: vLLM, LM Studio, LiteLLM, Azure…, com sua URL e chave). A chave é opcional no Ollama na sua rede e nos serviços próprios que não a pedem. «Testar conexão» lista os modelos reais do provedor escolhido, e a chave não é mostrada novamente depois de salva.

## A busca na documentação é local

Não é preciso nenhum segundo serviço nem chave: a busca é feita dentro do seu próprio servidor (texto completo do PostgreSQL), no idioma do painel (espanhol, inglês ou português) e sem enviar a documentação a ninguém. A documentação é **indexada sozinha** ao iniciar e sempre que muda (por exemplo, após atualizar), e inclui a ajuda de cada tela do painel. O botão «Reindexar documentação» fica para forçar à mão.

## O que vê, e o que não vê

Por padrão só lê a documentação do projeto -nunca o banco de dados, o \`squid.conf\` real, usuários nem credenciais. O que viaja ao provedor de IA é a pergunta, os trechos de documentação relevantes e, no modo agêntico, os dados que o assistente consulta (veja abaixo).

## Modo agêntico

Com o modo agêntico ativado, o assistente pode consultar **ACLs, regras de acesso, grupos, ajustes do Squid e o estado de «Aplicar alterações»** deste servidor para diagnosticar com base na sua configuração real (por exemplo, «por que o grupo X não consegue acessar este site?»). O que consulta é estrutural -nomes, tipos e quantidades-: nunca o conteúdo das listas de arquivo, nem usuários, nem linhas de registro. Pode **propor criar uma ACL**, mas **nunca a cria nem a aplica sozinho**: aparece como proposta e você a cria com o mesmo botão de sempre. Não disponível com Ollama Cloud.

## Quem pode perguntar

Qualquer administrador, **inclusive uma conta somente leitura**: é uma consulta, não uma ação sobre o proxy.

## Requisito: pgvector

O banco de dados usa a extensão pgvector. Ela se instala sozinha tanto no Docker quanto na instalação nativa, inclusive ao atualizar uma instalação existente.
`.trim(),
}
