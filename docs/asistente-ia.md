# Asistente de IA

Un buscador con lenguaje natural sobre la documentación del proyecto, no un
agente que actúa sobre el proxy. Responde preguntas de uso ("¿cómo habilito
Kerberos?", "¿qué pasa si bloqueo a un usuario?") citando de qué archivo y
sección sacó la respuesta.

Apagado por defecto, igual que LDAP/Kerberos/Syslog.

---

## Qué puede ver, y qué no

**Solo lee `README.md` y `docs/*.md` en español** — nunca la base de datos,
nunca el `squid.conf` real, nunca credenciales ni la configuración de tu
instalación. Las traducciones (`.en.md`, `.pt.md`) se excluyen a propósito:
indexar las tres versiones de cada página triplicaría el corpus sin agregar
información nueva, y mezclaría idiomas en la misma búsqueda sin necesidad.

Esto es deliberado, no una limitación temporal: la función es un buscador con
lenguaje natural encima de la documentación pública del proyecto, no un
asistente que sepa nada sobre tu red, tus usuarios o tus reglas.

## Lo que hay que saber antes de activarlo

**El contenido de la documentación y cada pregunta que se hace viajan a
servicios de terceros** — el proveedor de chat que elijas y, siempre, Jina AI
para la búsqueda semántica. No es información sensible (es la documentación
pública del propio proyecto, y las preguntas son sobre cómo usar el panel),
pero si tu política interna no permite mandar texto a APIs externas, esta
función no es para vos.

Hacen falta **dos API keys separadas**, de dos servicios distintos:

1. **Un proveedor de chat**, para generar la respuesta en lenguaje natural:
   `gemini`, `ollama_cloud`, `nvidia_nim` o `groq`.
2. **Jina AI**, siempre, para los embeddings (búsqueda semántica) — sin
   importar qué proveedor de chat elijas arriba. Se evaluaron Gemini, NVIDIA
   NIM, Cohere y Voyage AI antes de fijar este: Gemini tiene cuotas muy
   ajustadas para embeddings (503 "high demand" repetidos, visto en vivo),
   NVIDIA NIM y Voyage AI no pueden emitir vectores de 768 dimensiones sin
   truncar, y Cohere limita a 5 llamadas/min en su plan gratuito. Jina
   soporta la tarea asimétrica que hace falta (`retrieval.passage` al
   indexar, `retrieval.query` al buscar) con un límite más razonable
   (100 req/min).

Las dos tienen niveles gratuitos usables para este volumen (la documentación
del proyecto son unas pocas decenas de páginas). Ninguna key se muestra de
nuevo una vez guardada — el panel solo indica si hay una configurada.

## Requisito de infraestructura: `pgvector`

La búsqueda semántica guarda los embeddings en una columna vectorial de
Postgres, que exige la extensión `pgvector`:

- **Docker**: se crea sola en una instalación nueva; en una que ya existía
  antes de esta función, la migración correspondiente la crea igual si el
  usuario de la base es superusuario (el caso por defecto de la imagen
  oficial de Postgres) — ver [docs/actualizacion.md](actualizacion.md) si
  falla con `permission denied to create extension "vector"`.
- **Nativo**: `install-nativo.sh`/`upgrade-nativo.sh` instalan el paquete
  `postgresql-N-pgvector` (según la versión mayor de Postgres detectada) y
  crean la extensión, tanto en una instalación nueva como al actualizar una
  existente.

## Cómo se busca (búsqueda híbrida)

Cada pregunta combina dos búsquedas sobre los fragmentos indexados, sin
repetir resultados:

- **Semántica** (embedding, distancia coseno): encuentra fragmentos
  relacionados por significado aunque no compartan ni una palabra con la
  pregunta.
- **Literal** (texto completo de Postgres, `tsvector`/`websearch_to_tsquery`
  en español): encuentra coincidencias exactas — nombres de ajustes,
  comandos, rutas de archivo — que un embedding puede no priorizar.

Los fragmentos encontrados (hasta 5) se le pasan al modelo de chat como
contexto junto con la pregunta; la respuesta cita de qué archivo y sección
salió cada fragmento usado (`fuentes` en la respuesta de la API, ver
[api-reference.md](api-reference.md#asistente-de-ia)).

## Reindexar

La documentación **no se reindexa sola**. Hay que pulsar «Reindexar» en el
panel (o `POST /api/ai/reindexar`) después de:

- Activar el asistente por primera vez.
- Cualquier cambio en `README.md` o en `docs/*.md` — incluida una
  actualización de SquidManager a una versión con documentación nueva.

Es una reindexación completa, no incremental: borra todos los fragmentos
guardados y vuelve a generarlos desde cero. El corpus es chico (unas pocas
decenas de archivos), así que no hace falta rastrear qué cambió desde la
última vez — es más simple y no puede quedar a medio actualizar.

## Probar antes de guardar

El panel deja probar la API key del proveedor de chat (devuelve los modelos
disponibles reales, para elegir de una lista en vez de escribir un nombre a
mano) y la de Jina AI (pide un embedding mínimo) **sin guardar nada**, antes
de activar el asistente en serio.

## Quién puede preguntar

Cualquier administrador, **incluida una cuenta de solo lectura**: es una
consulta de lectura sobre documentación pública, no una acción sobre el
proxy — no compromete el principio de que un viewer no puede modificar nada.

## Límites

- Si la pregunta no tiene ningún fragmento relacionado en la documentación,
  lo dice explícitamente en vez de inventar una respuesta.
- No sabe nada de tu instalación en particular: no puede decirte por qué
  *tu* Squid no arranca, ni leer *tus* logs — para eso están las páginas de
  Registros y Auditoría del propio panel.
- Depende de la disponibilidad y las cuotas de los dos servicios externos
  elegidos; un error de esos servicios se traduce en un mensaje de error
  claro, no en una respuesta a medias.
