"""Asistente de IA: responde consultas sobre el uso del panel usando la
documentación del proyecto como única fuente.

Diseño deliberado, no accidental:
- Solo lee `docs/*.md` y el `README.md` en español -nunca la base de datos,
  nunca el squid.conf real, nunca credenciales-. Esta función es un buscador
  con lenguaje natural encima, no un agente que actúa sobre el proxy.
- Los embeddings son siempre de Jina AI (`jina-embeddings-v3`, con
  `dimensions=768` para calzar con la columna de la tabla): se investigó
  Gemini, NVIDIA NIM, Cohere y Voyage AI antes de elegir -Gemini tiene
  límites de cuota muy ajustados (se vieron 503 "high demand" en vivo,
  varias veces seguidas), NVIDIA NIM y Voyage AI no pueden emitir vectores
  de 768 dimensiones sin truncar, y Cohere limita a 5 llamadas/min en su
  key gratis. Jina soporta la misma tarea asimétrica (`retrieval.passage`
  al indexar, `retrieval.query` al buscar) con 100 req/min de límite. Así
  la búsqueda no depende de qué proveedor de chat se haya elegido arriba.
- Llamadas REST directas con `httpx` (ya es dependencia del proyecto): sin
  SDK de por medio, sin traer un framework de RAG que resuelve un problema
  mucho más general del que hace falta acá.
"""

import logging
import re
import threading
import time
from pathlib import Path

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.ai_config import AiConfig
from app.models.doc_chunk import DocChunk, EMBEDDING_DIM

logger = logging.getLogger(__name__)

# Candado para que dos reindexaciones no corran a la vez. Encontrado en vivo:
# cada reindexación empieza borrando TODA la tabla antes de reconstruirla, así
# que dos corriendo en paralelo (dos pestañas, o un click doble) se pisan
# entre sí -una borra lo que la otra ya había confirmado- y el resultado
# final queda con archivos de punta a la mitad, sin ningún error visible. Un
# `threading.Lock` alcanza porque el backend corre en un único proceso (sin
# `--workers`, ver el ExecStart de systemd) -no hace falta coordinación entre
# procesos ni un lock a nivel de base de datos-.
_REINDEXANDO = threading.Lock()


def _raiz_del_proyecto() -> Path | None:
    """Directorio raíz del repo (donde viven `docs/` y `README.md`).

    Mismo patrón que ya usa `backend/tests/test_logrotate.py`: en modo nativo
    el backend corre desde `<raiz>/backend`, así que alcanza con subir
    directorios buscando `README.md`. En Docker el código de la app no vive
    bajo la misma jerarquía que el repo completo -solo `backend/` se copia a
    la imagen-, así que ahí hace falta el volumen que monta el proyecto
    entero (`PROJECT_DIR`, ya resuelto en `docker_runtime.project_dir()`
    para el mismo propósito).
    """
    for base in Path(__file__).resolve().parents:
        if (base / "README.md").is_file() and (base / "docs").is_dir():
            return base

    from app.services.runtime.docker_runtime import project_dir

    return project_dir()


_GEMINI_GENERATE_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
_GEMINI_MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"

_JINA_EMBED_URL = "https://api.jina.ai/v1/embeddings"
_JINA_EMBED_MODEL = "jina-embeddings-v3"

# Archivos que se indexan: la documentación en español, la fuente canónica.
# Las traducciones (.en.md, .pt.md) se excluyen a propósito -indexar las tres
# versiones de cada página triplicaría el corpus sin agregar información
# nueva, y mezclaría idiomas en la misma búsqueda semántica sin necesidad-.
_ARCHIVOS_A_INDEXAR = ["README.md"]  # + todo docs/*.md, agregado al listar

# Fragmentos de más de esto se dividen por párrafo antes de pedir el
# embedding: los modelos de embeddings tienen un límite de tokens de entrada
# (unos 2048 para gemini-embedding-001), y una sección de varios KB se pasa
# de eso sin avisar -mejor partirla acá que depender de que la API trunque
# en silencio o rechace la petición-.
_MAX_CHARS_POR_FRAGMENTO = 3000


class AiServiceError(Exception):
    """Error de configuración o de la API del proveedor, para mostrar al admin."""


# 503 ("high demand") y 429 (límite de cuota) son transitorios por
# naturaleza, no un error de la petición en sí -visto en vivo con
# gemini-3.6-flash, consistente varias veces seguidas en cuestión de
# segundos-. Reintentar unas pocas veces con una espera corta es lo que
# haría cualquiera a mano; no hace falta que el admin lo haga él mismo cada
# vez que pregunta algo.
_CODIGOS_REINTENTABLES = (429, 503)
_REINTENTOS = 3
_ESPERA_ENTRE_REINTENTOS = 3.0

# El reindexado (proceso de fondo, nadie mirando la pantalla) puede permitirse
# insistir varias veces. Una pregunta en vivo del Asistente no: el admin está
# esperando la respuesta en pantalla, y con 3 reintentos de hasta 60s cada uno
# la espera real llega a ~3 minutos antes de mostrar cualquier error -se sintió
# "colgado" en vivo con Gemini devolviendo 503 "high demand"-. Para ese camino
# interactivo alcanza con un solo reintento corto: si el proveedor sigue
# fallando después de eso, mejor avisar ya que seguir insistiendo en silencio.
_REINTENTOS_INTERACTIVO = 1
_ESPERA_ENTRE_REINTENTOS_INTERACTIVO = 2.0


def _post_con_reintentos(
    url: str,
    headers: dict,
    body: dict,
    timeout: float,
    reintentos: int = _REINTENTOS,
    espera: float = _ESPERA_ENTRE_REINTENTOS,
) -> httpx.Response:
    ultimo_error: Exception | None = None
    for intento in range(1, reintentos + 1):
        try:
            r = httpx.post(url, headers=headers, json=body, timeout=timeout)
            if r.status_code in _CODIGOS_REINTENTABLES and intento < reintentos:
                logger.warning(
                    "Proveedor de IA devolvió %d (intento %d/%d), reintentando...",
                    r.status_code, intento, reintentos,
                )
                time.sleep(espera)
                continue
            r.raise_for_status()
            return r
        except httpx.HTTPStatusError:
            raise
        except httpx.HTTPError as e:
            ultimo_error = e
            if intento < reintentos:
                time.sleep(espera)
                continue
            raise
    raise ultimo_error  # pragma: no cover - inalcanzable, el bucle siempre retorna o lanza


# --- Embeddings (siempre Jina AI, ver nota al principio del archivo) --------

def _jina_embed(texto: str, api_key: str, task: str) -> list[float]:
    """Pide un embedding a Jina AI, con la dimensión fija del proyecto.

    `task` distingue indexar documentos (`retrieval.passage`) de buscar con
    una pregunta (`retrieval.query`): son embeddings asimétricos a propósito
    -Jina entrena un adaptador LoRA distinto según el rol-, y usar el mismo
    para los dos lados empeora la búsqueda.
    """
    body = {
        "model": _JINA_EMBED_MODEL,
        "task": task,
        "dimensions": EMBEDDING_DIM,
        "input": [texto],
    }
    try:
        r = _post_con_reintentos(_JINA_EMBED_URL, {"Authorization": f"Bearer {api_key}"}, body, timeout=30)
    except httpx.HTTPStatusError as e:
        raise AiServiceError(f"Jina AI rechazó la petición de embedding: {e.response.text[:300]}")
    except httpx.HTTPError as e:
        raise AiServiceError(f"No se pudo conectar con Jina AI: {e}")

    datos = r.json().get("data") or []
    valores = datos[0].get("embedding") if datos else None
    if not valores:
        raise AiServiceError("Jina AI no devolvió un embedding válido.")
    return valores


def probar_jina(api_key: str) -> int:
    """Prueba la key de Jina pidiendo un embedding de una palabra corta.

    Devuelve la dimensión obtenida -confirma que la key funciona y que
    coincide con lo que espera la tabla (768), sin gastar más que una
    llamada mínima.
    """
    vector = _jina_embed("prueba de conexión", api_key, "retrieval.passage")
    return len(vector)


def _error_proveedor(nombre: str, e: httpx.HTTPStatusError) -> AiServiceError:
    """Traduce un error HTTP del proveedor a un mensaje claro para el usuario.

    429/503 son los casos que motivaron esto -límite de cuota agotado o el
    proveedor saturado-, y son justo los que un admin necesita distinguir de
    "la pregunta está mal" o "hay un bug": acá no hay nada que arreglar del
    lado de SquidManager, hay que esperar o cambiar de proveedor/modelo en
    Configuración.
    """
    if e.response.status_code == 429:
        return AiServiceError(
            f"{nombre} rechazó la petición: se agotó el límite de uso de la API key "
            "(código 429). Esperá a que se renueve la cuota o cambiá de proveedor/"
            "modelo en Configuración."
        )
    if e.response.status_code == 503:
        return AiServiceError(
            f"{nombre} no está disponible en este momento (alta demanda, código 503). "
            "Probá de nuevo en un momento."
        )
    return AiServiceError(f"{nombre} rechazó la petición: {e.response.text[:300]}")


# --- Proveedores: generación de la respuesta (Gemini u Ollama Cloud) --------

def _gemini_generar(system: str, prompt: str, api_key: str, model: str, interactivo: bool = False) -> str:
    url = _GEMINI_GENERATE_URL.format(model=model)
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "systemInstruction": {"parts": [{"text": system}]},
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2048},
    }
    reintentos = _REINTENTOS_INTERACTIVO if interactivo else _REINTENTOS
    espera = _ESPERA_ENTRE_REINTENTOS_INTERACTIVO if interactivo else _ESPERA_ENTRE_REINTENTOS
    try:
        # 60s, no 30: a diferencia de un embedding (rápido, texto corto), una
        # respuesta generada puede tardar bastante más bajo demanda alta -se
        # vio en vivo: un 503 "high demand" seguido de un timeout a 30s en el
        # reintento con el mismo modelo-.
        r = _post_con_reintentos(
            url, {"x-goog-api-key": api_key}, body, timeout=60,
            reintentos=reintentos, espera=espera,
        )
    except httpx.HTTPStatusError as e:
        raise _error_proveedor("Gemini", e)
    except httpx.HTTPError as e:
        raise AiServiceError(f"No se pudo conectar con Gemini: {e}")

    candidatos = r.json().get("candidates") or []
    if not candidatos:
        raise AiServiceError("Gemini no devolvió ninguna respuesta (puede haber bloqueado el contenido).")
    if candidatos[0].get("finishReason") == "MAX_TOKENS":
        # Se corta la respuesta a mitad de frase sin ningún aviso salvo este
        # campo -visto en vivo con maxOutputTokens=800-. Mejor decirlo claro
        # que entregar una respuesta que parece completa y no lo está.
        logger.warning("Respuesta de Gemini cortada por MAX_TOKENS")
    partes = candidatos[0].get("content", {}).get("parts") or []
    texto = "".join(p.get("text", "") for p in partes).strip()
    if not texto:
        raise AiServiceError("Gemini devolvió una respuesta vacía.")
    return texto


def _ollama_cloud_generar(system: str, prompt: str, api_key: str, model: str, interactivo: bool = False) -> str:
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
    }
    reintentos = _REINTENTOS_INTERACTIVO if interactivo else _REINTENTOS
    espera = _ESPERA_ENTRE_REINTENTOS_INTERACTIVO if interactivo else _ESPERA_ENTRE_REINTENTOS
    try:
        r = _post_con_reintentos(
            "https://ollama.com/api/chat",
            {"Authorization": f"Bearer {api_key}"},
            body,
            timeout=60,
            reintentos=reintentos,
            espera=espera,
        )
    except httpx.HTTPStatusError as e:
        raise _error_proveedor("Ollama Cloud", e)
    except httpx.HTTPError as e:
        raise AiServiceError(f"No se pudo conectar con Ollama Cloud: {e}")

    contenido = (r.json().get("message") or {}).get("content", "").strip()
    if not contenido:
        raise AiServiceError("Ollama Cloud devolvió una respuesta vacía.")
    return contenido


# Proveedores que exponen el formato estándar de OpenAI
# (`POST {base_url}/chat/completions`, `choices[0].message.content`) — la
# gran mayoría de los que ofrecen un nivel gratis generoso lo hacen, así que
# sumar uno nuevo es agregar una fila acá, no escribir un adaptador nuevo.
# Verificado en la documentación oficial de cada uno antes de sumarlo, no
# asumido por parecido de nombre.
_PROVEEDORES_OPENAI_COMPATIBLE = {
    "nvidia_nim": ("https://integrate.api.nvidia.com/v1", "NVIDIA NIM"),
    "groq": ("https://api.groq.com/openai/v1", "Groq"),
}


def _openai_compatible_generar(
    system: str, prompt: str, api_key: str, model: str, base_url: str, nombre: str,
    interactivo: bool = False,
) -> str:
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    }
    reintentos = _REINTENTOS_INTERACTIVO if interactivo else _REINTENTOS
    espera = _ESPERA_ENTRE_REINTENTOS_INTERACTIVO if interactivo else _ESPERA_ENTRE_REINTENTOS
    try:
        r = _post_con_reintentos(
            f"{base_url}/chat/completions",
            {"Authorization": f"Bearer {api_key}"},
            body,
            timeout=60,
            reintentos=reintentos,
            espera=espera,
        )
    except httpx.HTTPStatusError as e:
        raise _error_proveedor(nombre, e)
    except httpx.HTTPError as e:
        raise AiServiceError(f"No se pudo conectar con {nombre}: {e}")

    choices = r.json().get("choices") or []
    if not choices:
        raise AiServiceError(f"{nombre} no devolvió ninguna respuesta.")
    contenido = (choices[0].get("message") or {}).get("content", "").strip()
    if not contenido:
        raise AiServiceError(f"{nombre} devolvió una respuesta vacía.")
    return contenido


# --- Listado de modelos disponibles (para probar la key antes de guardar) ---

def _listar_modelos_gemini(api_key: str) -> list[str]:
    try:
        r = httpx.get(_GEMINI_MODELS_URL, headers={"x-goog-api-key": api_key}, timeout=20)
        r.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise AiServiceError(f"Gemini rechazó la petición: {e.response.text[:300]}")
    except httpx.HTTPError as e:
        raise AiServiceError(f"No se pudo conectar con Gemini: {e}")

    modelos = r.json().get("models") or []
    return sorted(
        m["name"].removeprefix("models/")
        for m in modelos
        if "generateContent" in (m.get("supportedGenerationMethods") or []) and m.get("name")
    )


def _listar_modelos_openai_compatible(base_url: str, api_key: str, nombre: str) -> list[str]:
    try:
        r = httpx.get(f"{base_url}/models", headers={"Authorization": f"Bearer {api_key}"}, timeout=20)
        r.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise AiServiceError(f"{nombre} rechazó la petición: {e.response.text[:300]}")
    except httpx.HTTPError as e:
        raise AiServiceError(f"No se pudo conectar con {nombre}: {e}")

    datos = r.json().get("data") or []
    return sorted(m["id"] for m in datos if m.get("id"))


# Ollama Cloud expone chat en `/api/chat` (ver _ollama_cloud_generar), pero
# para *listar* modelos sí ofrece el endpoint OpenAI-compatible estándar
# -no hace falta un formato aparte solo para esto-.
_OLLAMA_CLOUD_BASE_URL = "https://ollama.com/v1"


def listar_modelos(provider: str, api_key: str) -> list[str]:
    """Modelos de chat disponibles para la key dada, según el proveedor.

    Es lo que respalda el botón "Probar conexión": si esto no falla, la key
    funciona, y de paso deja elegir el modelo de una lista real en vez de
    escribirlo a mano y confiar en que el nombre exista.
    """
    if provider == "gemini":
        return _listar_modelos_gemini(api_key)
    if provider == "ollama_cloud":
        return _listar_modelos_openai_compatible(_OLLAMA_CLOUD_BASE_URL, api_key, "Ollama Cloud")
    if provider in _PROVEEDORES_OPENAI_COMPATIBLE:
        base_url, nombre = _PROVEEDORES_OPENAI_COMPATIBLE[provider]
        return _listar_modelos_openai_compatible(base_url, api_key, nombre)
    raise AiServiceError(f"Proveedor desconocido: {provider!r}")


def generar_respuesta(system: str, prompt: str, config: AiConfig, interactivo: bool = False) -> str:
    """Genera una respuesta con el proveedor configurado.

    `interactivo=True` es el camino de una pregunta del Asistente en vivo -el
    admin está esperando en pantalla, así que reintenta menos y más rápido
    (ver nota junto a `_REINTENTOS_INTERACTIVO`)-. Queda en False por defecto
    para cualquier otro uso futuro de este generador que no tenga a nadie
    esperando en pantalla.
    """
    if config.provider == "gemini":
        return _gemini_generar(system, prompt, config.api_key, config.chat_model, interactivo=interactivo)
    if config.provider == "ollama_cloud":
        return _ollama_cloud_generar(system, prompt, config.api_key, config.chat_model, interactivo=interactivo)
    if config.provider in _PROVEEDORES_OPENAI_COMPATIBLE:
        base_url, nombre = _PROVEEDORES_OPENAI_COMPATIBLE[config.provider]
        return _openai_compatible_generar(
            system, prompt, config.api_key, config.chat_model, base_url, nombre, interactivo=interactivo,
        )
    raise AiServiceError(f"Proveedor desconocido: {config.provider!r}")


def _key_embeddings(config: AiConfig) -> str | None:
    """La key de Jina AI, siempre separada de la del proveedor de chat -ver

    la nota al principio del archivo sobre por qué Jina y no el proveedor
    de chat elegido-.
    """
    return config.embedding_api_key


# --- Indexación de la documentación ------------------------------------------

def _partir_en_fragmentos(texto: str, archivo: str) -> list[tuple[str | None, str]]:
    """Divide un .md en (encabezado, contenido) por cada sección de nivel 2

    (`## Título`). Lo anterior al primer `##` (título del documento, aviso de
    idioma) queda como un fragmento sin encabezado. Las secciones muy largas
    se dividen además por párrafo, para no pasar el límite de tokens del
    modelo de embeddings.
    """
    lineas = texto.splitlines()
    secciones: list[tuple[str | None, list[str]]] = []
    actual_titulo: str | None = None
    actual_cuerpo: list[str] = []

    for linea in lineas:
        if linea.startswith("## "):
            if actual_cuerpo:
                secciones.append((actual_titulo, actual_cuerpo))
            actual_titulo = linea[3:].strip()
            actual_cuerpo = []
        else:
            actual_cuerpo.append(linea)
    if actual_cuerpo:
        secciones.append((actual_titulo, actual_cuerpo))

    fragmentos: list[tuple[str | None, str]] = []
    for titulo, cuerpo in secciones:
        contenido = "\n".join(cuerpo).strip()
        if not contenido or len(contenido) < 20:
            continue  # separadores ("---") o secciones vacías: nada que buscar ahí
        if len(contenido) <= _MAX_CHARS_POR_FRAGMENTO:
            fragmentos.append((titulo, contenido))
            continue
        # Partir por párrafo, agrupando de a varios hasta acercarse al tope,
        # en vez de un corte fijo a mitad de una frase.
        parrafos = [p for p in contenido.split("\n\n") if p.strip()]
        bloque: list[str] = []
        largo = 0
        for parrafo in parrafos:
            if largo + len(parrafo) > _MAX_CHARS_POR_FRAGMENTO and bloque:
                fragmentos.append((titulo, "\n\n".join(bloque)))
                bloque, largo = [], 0
            bloque.append(parrafo)
            largo += len(parrafo)
        if bloque:
            fragmentos.append((titulo, "\n\n".join(bloque)))

    return fragmentos


def _archivos_a_indexar() -> list[str]:
    """Rutas relativas al repo: README.md + todo docs/*.md (no las
    traducciones .en.md/.pt.md: ver nota al principio del archivo)."""
    raiz = _raiz_del_proyecto()
    archivos = list(_ARCHIVOS_A_INDEXAR)
    docs_dir = raiz / "docs"
    if docs_dir.is_dir():
        for p in sorted(docs_dir.glob("*.md")):
            if re.search(r"\.(en|pt)\.md$", p.name):
                continue
            archivos.append(f"docs/{p.name}")
    return archivos


def reindexar_documentacion(db: Session, config: AiConfig) -> dict:
    """Vuelve a indexar toda la documentación desde cero.

    Se hace completo, no incremental en el sentido de "solo lo que cambió"
    -el corpus es chico (unas pocas decenas de archivos) y así no hay que
    rastrear qué cambió desde la última vez-, pero SÍ confirma (commit) por
    archivo, no todo en una sola transacción al final. Encontrado en vivo:
    con el corpus ya creciendo (17+ archivos, ~200 fragmentos) la reindexación
    completa puede tardar más que el `proxy_read_timeout` de nginx (120 s por
    defecto) -sobre todo si Jina devuelve algún 429/503 y entran los
    reintentos-. Con todo en una única transacción, una conexión cortada a
    mitad de camino perdía TODO el progreso sin ningún error visible (la
    petición del navegador simplemente se cortaba): quedaba viéndose "no
    pasó nada" con el conteo de fragmentos intacto, cuando en realidad se
    habían gastado minutos de llamadas reales a Jina. Confirmando por
    archivo, una reindexación interrumpida deja indexados los archivos ya
    procesados en vez de perderlos todos -y volver a pulsar "Reindexar" solo
    tiene que rehacer lo que falta, no todo de nuevo-.
    """
    key_embeddings = _key_embeddings(config)
    if not key_embeddings:
        raise AiServiceError(
            "Falta configurar la API key de Jina AI para poder buscar en la documentación."
        )

    if not _REINDEXANDO.acquire(blocking=False):
        raise AiServiceError(
            "Ya hay una reindexación en curso (puede haberla lanzado otra pestaña o otro "
            "administrador) — esperá a que termine antes de lanzar otra."
        )

    try:
        raiz = _raiz_del_proyecto()
        archivos = _archivos_a_indexar()

        # Se borra y confirma aparte, antes de empezar: así, si la
        # reindexación se corta enseguida (antes de terminar ni un solo
        # archivo), esa eliminación por sí sola también se revierte -el
        # índice viejo queda intacto en vez de vaciarse sin nada nuevo que
        # lo reemplace-.
        db.query(DocChunk).delete()
        db.commit()

        total = 0
        saltados: list[str] = []
        for rel in archivos:
            ruta = raiz / rel
            if not ruta.is_file():
                continue
            try:
                texto = ruta.read_text(encoding="utf-8")
            except OSError as e:
                saltados.append(f"{rel}: {e}")
                continue

            for titulo, contenido in _partir_en_fragmentos(texto, rel):
                try:
                    embedding = _jina_embed(contenido, key_embeddings, "retrieval.passage")
                except AiServiceError as e:
                    saltados.append(f"{rel} ({titulo or 'sin título'}): {e}")
                    continue

                chunk = DocChunk(source_file=rel, heading=titulo, content=contenido, embedding=embedding)
                db.add(chunk)
                db.flush()  # necesario para poder calcular el tsvector por id, mas abajo
                db.execute(
                    text("UPDATE doc_chunks SET tsv = to_tsvector('spanish', :contenido) WHERE id = :id"),
                    {"contenido": contenido, "id": chunk.id},
                )
                total += 1

            # Confirmado al cerrar cada archivo, no al final de todos: ver la
            # nota de diseño de esta función.
            db.commit()

        db.commit()
        logger.info("Documentación reindexada: %d fragmentos de %d archivos", total, len(archivos))
        return {"fragmentos": total, "archivos": len(archivos), "saltados": saltados}
    finally:
        _REINDEXANDO.release()


# --- Búsqueda híbrida y respuesta ---------------------------------------------

def _buscar_fragmentos(db: Session, config: AiConfig, pregunta: str, top_n: int = 5) -> list[DocChunk]:
    """Combina búsqueda semántica (embedding) y literal (texto completo de

    Postgres) — la primera encuentra fragmentos relacionados por significado
    aunque no compartan palabras con la pregunta; la segunda encuentra
    coincidencias exactas (nombres de ajustes, comandos) que un embedding
    puede no priorizar. Se juntan los resultados de las dos, sin repetir.
    """
    key_embeddings = _key_embeddings(config)
    if not key_embeddings:
        raise AiServiceError(
            "Falta configurar la API key de Jina AI para poder buscar en la documentación."
        )
    embedding_pregunta = _jina_embed(pregunta, key_embeddings, "retrieval.query")

    por_significado = (
        db.query(DocChunk)
        .order_by(DocChunk.embedding.cosine_distance(embedding_pregunta))
        .limit(top_n)
        .all()
    )

    por_texto = db.execute(
        text(
            "SELECT id FROM doc_chunks "
            "WHERE tsv @@ websearch_to_tsquery('spanish', :q) "
            "ORDER BY ts_rank(tsv, websearch_to_tsquery('spanish', :q)) DESC "
            "LIMIT :n"
        ),
        {"q": pregunta, "n": top_n},
    ).fetchall()
    ids_texto = [row[0] for row in por_texto]
    por_texto_objs = db.query(DocChunk).filter(DocChunk.id.in_(ids_texto)).all() if ids_texto else []

    vistos: set[int] = set()
    combinados: list[DocChunk] = []
    for chunk in por_significado + por_texto_objs:
        if chunk.id not in vistos:
            vistos.add(chunk.id)
            combinados.append(chunk)
    return combinados[:top_n]


_SYSTEM_PROMPT = (
    "Sos el asistente de ayuda de SquidManager, un panel de administración de "
    "un proxy Squid. Respondé ÚNICAMENTE con la información de los fragmentos "
    "de documentación que se te dan a continuación. Si la respuesta no está "
    "en esos fragmentos, decí explícitamente que no encontraste eso en la "
    "documentación del proyecto — no inventes pasos, comandos, ni nombres de "
    "botones o ajustes que no aparezcan ahí. No tenés acceso a la "
    "configuración real de este servidor ni podés ejecutar ninguna acción: "
    "solo podés explicar cómo se usa el panel según su documentación."
)

# Saludos y frases sueltas sin pregunta real: sin esto, cada "hola" gasta una
# llamada de embedding + búsqueda + LLM para terminar diciendo "no encontré
# esa información", y además muestra fuentes que no vienen a cuento (el
# fragmento "más parecido" a un saludo es ruido, no una fuente real). Se
# responde acá mismo, sin tocar ningún proveedor.
_SALUDOS = re.compile(
    r"^(hola+|buenas|buenos\s+d[ií]as|buenas\s+tardes|buenas\s+noches|hey|hi|hello|"
    r"qu[ée]\s+tal|c[oó]mo\s+andas?|c[oó]mo\s+va|gracias|muchas\s+gracias|"
    r"chau|adi[oó]s|ok|okay|listo|buen[oa]s?)[\s!.,¿?]*$",
    re.IGNORECASE,
)

_RESPUESTA_SALUDO = (
    "¡Hola! Puedo responder preguntas sobre cómo usar SquidManager "
    "(usuarios, ACLs, reglas de acceso, LDAP, certificados, etc.) según la "
    "documentación del proyecto. ¿Qué necesitás saber?"
)


def preguntar(db: Session, config: AiConfig, pregunta: str) -> dict:
    if not config.enabled or not config.api_key:
        raise AiServiceError("El asistente de IA no está activado.")
    if not config.chat_model:
        raise AiServiceError("Falta configurar el modelo de respuesta en Ajustes del asistente.")

    if _SALUDOS.match(pregunta.strip()):
        return {"respuesta": _RESPUESTA_SALUDO, "fuentes": []}

    fragmentos = _buscar_fragmentos(db, config, pregunta)
    if not fragmentos:
        return {
            "respuesta": "No encontré nada relacionado con esa pregunta en la documentación del proyecto.",
            "fuentes": [],
        }

    contexto = "\n\n---\n\n".join(
        f"[{c.source_file}{' — ' + c.heading if c.heading else ''}]\n{c.content}"
        for c in fragmentos
    )
    prompt = f"Documentación relevante:\n\n{contexto}\n\nPregunta del usuario: {pregunta}"

    respuesta = generar_respuesta(_SYSTEM_PROMPT, prompt, config, interactivo=True)
    fuentes = [
        {"archivo": c.source_file, "seccion": c.heading} for c in fragmentos
    ]
    return {"respuesta": respuesta, "fuentes": fuentes}
