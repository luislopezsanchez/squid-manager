"""Asistente de IA: responde consultas sobre el uso del panel usando la
documentación del proyecto, y opcionalmente (modo agéntico, apagado por
defecto) consultando el estado real del servidor y proponiendo cambios de
configuración -ver ai_tools.py para el porqué eso es seguro: nunca escribe
nada por sí solo, solo arma propuestas que el administrador confirma a
mano.

Diseño deliberado, no accidental:
- Por defecto (modo agéntico apagado) solo lee `docs/*.md` y el `README.md`
  en español -nunca la base de datos, nunca el squid.conf real, nunca
  credenciales-. Es un buscador con lenguaje natural encima, no un agente.
  Con el modo agéntico activado, sí consulta ACLs/reglas/grupos/ajustes
  reales (nunca credenciales, nunca usuarios, nunca contenido de logs) para
  poder diagnosticar contra el estado real -ver ai_tools.py-.
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

import contextvars
import json
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
from app.services import ai_providers

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

# Idioma de la pregunta en curso (lo fija `preguntar`): las herramientas del modo agéntico
# buscan en la documentación sin saber el idioma, así que se lee de aquí.
_IDIOMA_ACTUAL: contextvars.ContextVar[str] = contextvars.ContextVar("ai_idioma", default="es")
_DICCIONARIO = {"es": "spanish", "en": "english", "pt": "portuguese"}


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


def _bearer(api_key: str | None) -> dict:
    """Cabecera de autorización; vacía si el proveedor no pide clave (Ollama en la red, servicios propios)."""
    return {"Authorization": f"Bearer {api_key}"} if api_key else {}


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
        r = _post_con_reintentos(_JINA_EMBED_URL, _bearer(api_key), body, timeout=30)
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
            _bearer(api_key),
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


_ANTHROPIC_VERSION = "2023-06-01"
_ANTHROPIC_MAX_TOKENS = 2048


def _anthropic_headers(api_key: str) -> dict:
    return {"x-api-key": api_key, "anthropic-version": _ANTHROPIC_VERSION}


def _anthropic_generar(system: str, prompt: str, api_key: str, model: str, interactivo: bool = False) -> str:
    body = {"model": model, "max_tokens": _ANTHROPIC_MAX_TOKENS, "system": system,
            "messages": [{"role": "user", "content": prompt}]}
    reintentos = _REINTENTOS_INTERACTIVO if interactivo else _REINTENTOS
    espera = _ESPERA_ENTRE_REINTENTOS_INTERACTIVO if interactivo else _ESPERA_ENTRE_REINTENTOS
    try:
        r = _post_con_reintentos(f"{ai_providers.PROVEEDORES['anthropic']['url']}/messages",
                                 _anthropic_headers(api_key), body, timeout=60, reintentos=reintentos, espera=espera)
    except httpx.HTTPStatusError as e:
        raise _error_proveedor("Anthropic", e)
    except httpx.HTTPError as e:
        raise AiServiceError(f"No se pudo conectar con Anthropic: {e}")
    texto = "".join(b.get("text", "") for b in (r.json().get("content") or []) if b.get("type") == "text").strip()
    if not texto:
        raise AiServiceError("Anthropic devolvió una respuesta vacía.")
    return texto


def _anthropic_generar_con_herramientas(messages: list[dict], tools: list[dict], api_key: str, model: str, system: str) -> dict:
    body = {
        "model": model, "max_tokens": _ANTHROPIC_MAX_TOKENS, "system": system, "messages": messages,
        "tools": [{"name": t["name"], "description": t["description"], "input_schema": t["parameters"]} for t in tools],
    }
    try:
        r = _post_con_reintentos(f"{ai_providers.PROVEEDORES['anthropic']['url']}/messages", _anthropic_headers(api_key), body,
                                 timeout=60, reintentos=_REINTENTOS_INTERACTIVO, espera=_ESPERA_ENTRE_REINTENTOS_INTERACTIVO)
    except httpx.HTTPStatusError as e:
        raise _error_proveedor("Anthropic", e)
    except httpx.HTTPError as e:
        raise AiServiceError(f"No se pudo conectar con Anthropic: {e}")
    bloques = r.json().get("content") or []
    usos = [b for b in bloques if b.get("type") == "tool_use"]
    if usos:
        return {"tipo": "tool_calls",
                "llamadas": [{"id": b.get("id"), "nombre": b.get("name"), "argumentos": b.get("input") or {}} for b in usos],
                "mensaje_bruto": {"role": "assistant", "content": bloques}}
    texto = "".join(b.get("text", "") for b in bloques if b.get("type") == "text").strip()
    if not texto:
        raise AiServiceError("Anthropic devolvió una respuesta vacía.")
    return {"tipo": "texto", "contenido": texto}


def _listar_modelos_anthropic(api_key: str) -> list[str]:
    try:
        r = httpx.get(f"{ai_providers.PROVEEDORES['anthropic']['url']}/models?limit=100", headers=_anthropic_headers(api_key), timeout=20)
        r.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise AiServiceError(f"Anthropic rechazó la petición: {e.response.text[:300]}")
    except httpx.HTTPError as e:
        raise AiServiceError(f"No se pudo conectar con Anthropic: {e}")
    return sorted(m["id"] for m in (r.json().get("data") or []) if m.get("id"))


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
            _bearer(api_key),
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


# --- Modo agéntico: generación con herramientas (tool calling) -------------
#
# Solo Gemini y los proveedores OpenAI-compatible (Groq, NVIDIA NIM): son los
# que se verificaron contra su documentación oficial antes de sumar esto (ver
# docs/project-log.md). Ollama Cloud queda fuera del modo agéntico -no se
# confirmó su soporte- pero sigue funcionando igual que siempre para el modo
# de solo documentación.

def _gemini_generar_con_herramientas(contents: list[dict], tools: list[dict], api_key: str, model: str, system: str) -> dict:
    url = _GEMINI_GENERATE_URL.format(model=model)
    body = {
        "contents": contents,
        "systemInstruction": {"parts": [{"text": system}]},
        "tools": [{"functionDeclarations": tools}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2048},
    }
    try:
        r = _post_con_reintentos(
            url, {"x-goog-api-key": api_key}, body, timeout=60,
            reintentos=_REINTENTOS_INTERACTIVO, espera=_ESPERA_ENTRE_REINTENTOS_INTERACTIVO,
        )
    except httpx.HTTPStatusError as e:
        raise _error_proveedor("Gemini", e)
    except httpx.HTTPError as e:
        raise AiServiceError(f"No se pudo conectar con Gemini: {e}")

    candidatos = r.json().get("candidates") or []
    if not candidatos:
        raise AiServiceError("Gemini no devolvió ninguna respuesta (puede haber bloqueado el contenido).")
    partes = candidatos[0].get("content", {}).get("parts") or []

    llamadas = []
    texto = ""
    for p in partes:
        if "functionCall" in p:
            fc = p["functionCall"]
            llamadas.append({"id": None, "nombre": fc.get("name"), "argumentos": fc.get("args") or {}})
        elif "text" in p:
            texto += p["text"]

    if llamadas:
        return {"tipo": "tool_calls", "llamadas": llamadas, "mensaje_bruto": {"role": "model", "parts": partes}}
    texto = texto.strip()
    if not texto:
        raise AiServiceError("Gemini devolvió una respuesta vacía.")
    return {"tipo": "texto", "contenido": texto}


def _openai_compatible_generar_con_herramientas(
    messages: list[dict], tools: list[dict], api_key: str, model: str, base_url: str, nombre: str,
) -> dict:
    body = {
        "model": model,
        "messages": messages,
        "tools": [{"type": "function", "function": t} for t in tools],
    }
    try:
        r = _post_con_reintentos(
            f"{base_url}/chat/completions",
            _bearer(api_key),
            body, timeout=60,
            reintentos=_REINTENTOS_INTERACTIVO, espera=_ESPERA_ENTRE_REINTENTOS_INTERACTIVO,
        )
    except httpx.HTTPStatusError as e:
        raise _error_proveedor(nombre, e)
    except httpx.HTTPError as e:
        raise AiServiceError(f"No se pudo conectar con {nombre}: {e}")

    choices = r.json().get("choices") or []
    if not choices:
        raise AiServiceError(f"{nombre} no devolvió ninguna respuesta.")
    mensaje = choices[0].get("message") or {}
    tool_calls = mensaje.get("tool_calls")

    if tool_calls:
        llamadas = []
        for tc in tool_calls:
            fn = tc.get("function", {})
            try:
                argumentos = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                argumentos = {}
            llamadas.append({"id": tc.get("id"), "nombre": fn.get("name"), "argumentos": argumentos})
        return {"tipo": "tool_calls", "llamadas": llamadas, "mensaje_bruto": mensaje}

    contenido = (mensaje.get("content") or "").strip()
    if not contenido:
        raise AiServiceError(f"{nombre} devolvió una respuesta vacía.")
    return {"tipo": "texto", "contenido": contenido}


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
        r = httpx.get(f"{base_url}/models", headers=_bearer(api_key), timeout=20)
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


def _datos_proveedor(provider: str, base_url: str | None) -> tuple[dict, str]:
    """(entrada del catálogo, URL efectiva). Falla con un mensaje claro si el proveedor no existe
    o si uno personalizado no trae su URL."""
    info = ai_providers.obtener(provider)
    if info is None:
        raise AiServiceError(f"Proveedor desconocido: {provider!r}")
    url = ai_providers.url_efectiva(provider, base_url)
    if info["tipo"] == "openai" and not url:
        raise AiServiceError("Falta la URL base del proveedor (por ejemplo https://mi-servidor/v1).")
    return info, url


def listar_modelos(provider: str, api_key: str | None, base_url: str | None = None) -> list[str]:
    """Modelos de chat disponibles para esa clave/URL: respalda «Probar conexión»
    (si no falla, la conexión funciona) y deja elegir el modelo de una lista real."""
    info, url = _datos_proveedor(provider, base_url)
    if info["requiere_clave"] and not api_key:
        raise AiServiceError("Falta la API key a probar.")
    if info["tipo"] == "gemini":
        return _listar_modelos_gemini(api_key)
    if info["tipo"] == "anthropic":
        return _listar_modelos_anthropic(api_key)
    if info["tipo"] == "ollama":
        return _listar_modelos_openai_compatible(_OLLAMA_CLOUD_BASE_URL, api_key, info["nombre"])
    return _listar_modelos_openai_compatible(url, api_key, info["nombre"])


def generar_respuesta(system: str, prompt: str, config: AiConfig, interactivo: bool = False) -> str:
    """Genera una respuesta con el proveedor configurado.

    `interactivo=True` es el camino de una pregunta del Asistente en vivo -el
    admin está esperando en pantalla, así que reintenta menos y más rápido
    (ver nota junto a `_REINTENTOS_INTERACTIVO`)-."""
    info, url = _datos_proveedor(config.provider, getattr(config, "base_url", None))
    if info["tipo"] == "gemini":
        return _gemini_generar(system, prompt, config.api_key, config.chat_model, interactivo=interactivo)
    if info["tipo"] == "anthropic":
        return _anthropic_generar(system, prompt, config.api_key, config.chat_model, interactivo=interactivo)
    if info["tipo"] == "ollama":
        return _ollama_cloud_generar(system, prompt, config.api_key, config.chat_model, interactivo=interactivo)
    return _openai_compatible_generar(system, prompt, config.api_key, config.chat_model, url, info["nombre"], interactivo=interactivo)


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


# Bitácoras de desarrollo: no son documentación de uso (y sus secciones enormes contienen
# casi todas las palabras posibles, ensuciando los resultados).
# Súbela cuando cambie QUÉ o CÓMO se indexa, para que el índice se reconstruya solo al actualizar.
_VERSION_INDICE = 2
_NO_INDEXAR = {"project-log.md"}
_SUFIJO_IDIOMA = {"es": None, "en": ".en.md", "pt": ".pt.md"}


def _archivos_a_indexar(idioma: str = "es") -> list[str]:
    """Rutas relativas al repo de los .md de un idioma: README + docs/*.md (en `es`, los que no
    llevan sufijo de idioma; en `en`/`pt`, los .en.md / .pt.md)."""
    raiz = _raiz_del_proyecto()
    sufijo = _SUFIJO_IDIOMA[idioma]
    readme = "README.md" if sufijo is None else f"README{sufijo}"
    archivos = [readme] if (raiz / readme).is_file() else []
    docs_dir = raiz / "docs"
    if docs_dir.is_dir():
        for p in sorted(docs_dir.glob("*.md")):
            if p.name in _NO_INDEXAR:
                continue
            es_traduccion = bool(re.search(r"\.(en|pt)\.md$", p.name))
            if sufijo is None and not es_traduccion:
                archivos.append(f"docs/{p.name}")
            elif sufijo is not None and p.name.endswith(sufijo):
                archivos.append(f"docs/{p.name}")
    return archivos


def _docs_del_panel() -> dict[str, dict[str, str]]:
    """Artículos de la Documentación del propio panel (frontend/src/content/docs*.ts):
    {titulo: {es, en, pt}}. Es la documentación más completa y actual de cada pantalla y viene en
    los tres idiomas. Se lee el texto de los archivos fuente del repo, sin ejecutar nada."""
    raiz = _raiz_del_proyecto()
    contenido_dir = raiz / "frontend" / "src" / "content"
    pagina = raiz / "frontend" / "src" / "pages" / "Documentacion.tsx"
    if not contenido_dir.is_dir():
        return {}
    titulos: dict[str, str] = {}
    if pagina.is_file():
        for m in re.finditer(r"titulo:\s*(?:traducir\('([^']+)'\)|'([^']+)')[^\n]*contenido:\s*(DOC_\w+)", pagina.read_text(encoding="utf-8")):
            titulos[m.group(3)] = m.group(1) or m.group(2)
    salida: dict[str, dict[str, str]] = {}
    for ts in sorted(contenido_dir.glob("docs*.ts")):
        texto = ts.read_text(encoding="utf-8")
        nombre = re.search(r"export const (DOC_\w+)", texto)
        if not nombre:
            continue
        idiomas = {}
        for idi in ("es", "en", "pt"):
            m = re.search(rf"\b{idi}:\s*`(.*?)`(?:\.trim\(\))?\s*,?\s*(?:\n\s*(?:en|pt):|\n\}})", texto, re.DOTALL)
            if m:
                idiomas[idi] = m.group(1).replace("\\`", "`").replace("\\${", "${").replace("\\\\", "\\")
        if idiomas:
            salida[titulos.get(nombre.group(1), ts.stem.removeprefix("docs"))] = idiomas
    return salida


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
    # Sin clave de embeddings (lo normal ahora) se indexa solo para texto completo:
    # instantáneo, local y sin segundo proveedor. Con una clave de Jina ya guardada
    # (instalaciones anteriores) se siguen calculando los vectores.
    key_embeddings = _key_embeddings(config) if config is not None else None

    if not _REINDEXANDO.acquire(blocking=False):
        raise AiServiceError(
            "Ya hay una reindexación en curso (puede haberla lanzado otra pestaña o otro "
            "administrador) — esperá a que termine antes de lanzar otra."
        )

    try:
        raiz = _raiz_del_proyecto()
        panel = _docs_del_panel()

        # Se borra y confirma aparte, antes de empezar: así, si la reindexación se corta enseguida,
        # esa eliminación por sí sola también se revierte -el índice viejo queda intacto-.
        db.query(DocChunk).delete()
        db.commit()

        total = 0
        archivos_total = 0
        saltados: list[str] = []

        def _guardar(idioma: str, fuente: str, titulo: str | None, contenido: str):
            nonlocal total
            embedding = None
            if key_embeddings and idioma == "es":
                try:
                    embedding = _jina_embed(contenido, key_embeddings, "retrieval.passage")
                except AiServiceError as e:
                    saltados.append(f"{fuente} ({titulo or 'sin título'}): {e}")
                    return
            chunk = DocChunk(source_file=fuente, idioma=idioma, heading=titulo, content=contenido, embedding=embedding)
            db.add(chunk)
            db.flush()  # necesario para poder calcular el tsvector por id
            # El título pesa más que el cuerpo (A > B): una sección cuyo encabezado coincide con la
            # pregunta es casi siempre la respuesta. Cada idioma usa su propio diccionario.
            db.execute(
                text(f"UPDATE doc_chunks SET tsv = setweight(to_tsvector('{_DICCIONARIO[idioma]}', coalesce(:titulo, '')), 'A') "
                     f"|| setweight(to_tsvector('{_DICCIONARIO[idioma]}', :contenido), 'B') WHERE id = :id"),
                {"titulo": titulo or "", "contenido": contenido, "id": chunk.id},
            )
            total += 1

        for idioma in ("es", "en", "pt"):
            for rel in _archivos_a_indexar(idioma):
                ruta = raiz / rel
                if not ruta.is_file():
                    continue
                try:
                    texto = ruta.read_text(encoding="utf-8")
                except OSError as e:
                    saltados.append(f"{rel}: {e}")
                    continue
                archivos_total += 1
                for titulo, contenido in _partir_en_fragmentos(texto, rel):
                    _guardar(idioma, rel, titulo, contenido)
                db.commit()  # por archivo: una reindexación interrumpida no pierde lo ya hecho

            # Documentación del panel, artículo por artículo, en ese idioma.
            for articulo, textos in panel.items():
                if idioma not in textos:
                    continue
                archivos_total += 1
                fuente = f"Documentación del panel › {articulo}"
                for titulo, contenido in _partir_en_fragmentos(textos[idioma], fuente):
                    _guardar(idioma, fuente, titulo, contenido)
            db.commit()

        db.commit()
        logger.info("Documentación reindexada: %d fragmentos de %d archivos", total, archivos_total)
        return {"fragmentos": total, "archivos": archivos_total, "saltados": saltados}
    finally:
        _REINDEXANDO.release()


# --- Búsqueda híbrida y respuesta ---------------------------------------------

_PALABRAS_VACIAS = {
    "como", "cómo", "que", "qué", "cual", "cuál", "cuales", "cuáles", "para", "por", "con", "sin", "una", "uno", "unos", "unas",
    "los", "las", "del", "que", "mas", "más", "muy", "esta", "este", "esto", "esa", "ese", "eso", "hay", "puedo", "puede",
    "hacer", "quiero", "necesito", "donde", "dónde", "cuando", "cuándo", "sobre", "desde", "hasta", "son", "ser", "esta", "estoy",
    "tiene", "tengo", "panel", "squidmanager", "squid", "favor", "gracias", "hola",
}


_VACIAS_EN = {"how", "what", "which", "where", "when", "can", "the", "and", "for", "with", "that", "this", "does", "are", "you", "your", "our", "from", "into", "have", "has", "not", "all", "any", "want", "need", "please", "panel", "squid", "squidmanager", "to", "do", "is", "it", "my", "of", "in", "on", "an", "a"}
_VACIAS_PT = {"como", "qual", "quais", "onde", "quando", "para", "por", "com", "sem", "uma", "uns", "umas", "dos", "das", "nos", "nas", "que", "mais", "muito", "esta", "este", "isso", "esse", "tem", "posso", "pode", "fazer", "quero", "preciso", "sobre", "desde", "até", "são", "ser", "estou", "favor", "obrigado", "olá", "panel", "painel", "squid", "squidmanager"}


def _consulta_or(pregunta: str, idioma: str = "es") -> str | None:
    """Palabras significativas de la pregunta unidas con OR para to_tsquery. Con AND (websearch)
    una pregunta en lenguaje natural casi nunca encuentra nada; con OR y ranking, sí."""
    palabras = []
    for w in re.findall(r"[a-záéíóúüñ0-9_]{3,}", pregunta.lower()):
        vacias = _PALABRAS_VACIAS if idioma == "es" else (_VACIAS_EN if idioma == "en" else _VACIAS_PT)
        if w not in vacias and w not in palabras:
            palabras.append(w)
    return " | ".join(palabras[:12]) or None


def _buscar_fragmentos(db: Session, config: AiConfig, pregunta: str, top_n: int = 5) -> list[DocChunk]:
    """Fragmentos de la documentación más relacionados con la pregunta.

    Por texto completo de PostgreSQL (palabras de la pregunta unidas con OR, título con más
    peso, ranking por cobertura): local, instantáneo y sin segundo proveedor. Si hay una clave de
    embeddings guardada (instalaciones anteriores con Jina AI) se suma la búsqueda por significado.
    """
    por_significado: list[DocChunk] = []
    key_embeddings = _key_embeddings(config) if config is not None else None
    if key_embeddings:
        try:
            embedding_pregunta = _jina_embed(pregunta, key_embeddings, "retrieval.query")
            por_significado = (
                db.query(DocChunk)
                .filter(DocChunk.embedding.isnot(None), DocChunk.idioma == "es")
                .order_by(DocChunk.embedding.cosine_distance(embedding_pregunta))
                .limit(top_n)
                .all()
            )
        except AiServiceError as e:
            logger.warning("Búsqueda semántica no disponible, se usa solo texto completo: %s", e)

    idioma = _IDIOMA_ACTUAL.get()

    def _por_texto(idi: str, limite: int) -> list[DocChunk]:
        consulta = _consulta_or(pregunta, idi)
        if not consulta:
            return []
        filas = db.execute(
            text(
                f"SELECT id FROM doc_chunks WHERE idioma = :idi AND tsv @@ to_tsquery('{_DICCIONARIO[idi]}', :q) "
                f"ORDER BY ts_rank_cd(tsv, to_tsquery('{_DICCIONARIO[idi]}', :q), 1) DESC, id LIMIT :n"
            ),
            {"q": consulta, "n": limite, "idi": idi},
        ).fetchall()
        ids = [r[0] for r in filas]
        por_id = {c.id: c for c in db.query(DocChunk).filter(DocChunk.id.in_(ids)).all()} if ids else {}
        return [por_id[i] for i in ids if i in por_id]   # conserva el orden del ranking

    por_texto = _por_texto(idioma, top_n)
    if idioma != "es" and len(por_texto) < 3:
        # Parte de la documentación (la técnica) solo existe en español: el modelo la usa y
        # responde en el idioma de la pregunta.
        por_texto += _por_texto("es", top_n - len(por_texto))

    vistos: set[int] = set()
    combinados: list[DocChunk] = []
    for chunk in por_texto + por_significado:
        if chunk.id not in vistos:
            vistos.add(chunk.id)
            combinados.append(chunk)
    return combinados[:top_n]


def _firma_documentacion() -> str:
    """Huella de todo lo indexable (ruta, tamaño, fecha): cambia cuando cambia la documentación."""
    import hashlib

    raiz = _raiz_del_proyecto()
    h = hashlib.sha256()
    h.update(f"indice-v{_VERSION_INDICE}".encode())
    rutas = {r for idi in ("es", "en", "pt") for r in _archivos_a_indexar(idi)}
    carpeta = raiz / "frontend" / "src" / "content"
    if carpeta.is_dir():
        rutas |= {str(p.relative_to(raiz)) for p in carpeta.glob("docs*.ts")}
    for rel in sorted(rutas):
        p = raiz / rel
        if p.is_file():
            st = p.stat()
            h.update(f"{rel}:{st.st_size}:{int(st.st_mtime)}".encode())
    return h.hexdigest()


def indexar_si_hace_falta() -> dict | None:
    """Mantiene el índice de la documentación al día SIN intervención del admin: si no hay
    fragmentos, o los archivos cambiaron desde la última indexación (por ejemplo tras una
    actualización), se vuelve a indexar. Es un proceso local de un par de segundos. Con una clave
    de embeddings guardada no se toca: reindexarla vaciaría los vectores ya calculados."""
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        config = db.query(AiConfig).first()
        if config is not None and config.embedding_api_key:
            return None
        firma = _firma_documentacion()
        guardada = db.execute(text("SELECT v FROM ru_state WHERE k = 'ai:docs_sig'")).scalar()
        if guardada == firma and db.query(DocChunk).count() > 0:
            return None
        resultado = reindexar_documentacion(db, config)
        db.execute(
            text("INSERT INTO ru_state (k, v) VALUES ('ai:docs_sig', :v) ON CONFLICT (k) DO UPDATE SET v = EXCLUDED.v"),
            {"v": firma},
        )
        db.commit()
        return resultado
    finally:
        db.close()


def start_doc_indexer() -> None:
    """Indexa la documentación en segundo plano al arrancar (no bloquea el arranque)."""
    def _run():
        try:
            r = indexar_si_hace_falta()
            if r:
                logger.info("Documentación del asistente indexada: %s fragmentos", r["fragmentos"])
        except Exception as e:
            logger.warning("No se pudo indexar la documentación del asistente: %s", e)

    threading.Thread(target=_run, name="ai-doc-indexer", daemon=True).start()


_SYSTEM_PROMPT = (
    "Sos el asistente de ayuda de SquidManager, un panel de administración de "
    "un proxy Squid. Respondé ÚNICAMENTE con la información de los fragmentos "
    "de documentación que se te dan a continuación. Si la respuesta no está "
    "en esos fragmentos, decí explícitamente que no encontraste eso en la "
    "documentación del proyecto — no inventes pasos, comandos, ni nombres de "
    "botones o ajustes que no aparezcan ahí. No tenés acceso a la "
    "configuración real de este servidor ni podés ejecutar ninguna acción: "
    "solo podés explicar cómo se usa el panel según su documentación. "
    "Respondé siempre en el MISMO idioma en que está escrita la pregunta (español, inglés o portugués), "
    "aunque los fragmentos estén en otro idioma."
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


_MAX_ITERACIONES_AGENTE = 4

_SYSTEM_PROMPT_AGENTICO = (
    "Sos el asistente de SquidManager, un panel de administración de un "
    "proxy Squid. Tenés herramientas para consultar el estado REAL de este "
    "servidor (ACLs, reglas de acceso, grupos, ajustes generales, si hay "
    "cambios sin aplicar) y para buscar en la documentación del proyecto. "
    "Usalas cuando necesites información real para responder, o para "
    "revisar la configuración en busca de errores, en vez de adivinar.\n\n"
    "Podés PROPONER cambios de configuración con las herramientas que "
    "empiezan con 'proponer_' (por ejemplo, crear una ACL nueva). Estas "
    "NUNCA se aplican solas: arman una propuesta que el administrador tiene "
    "que revisar y confirmar a mano en el panel, con el mismo botón que "
    "usaría sin vos de por medio. Usalas solo cuando el administrador pidió "
    "explícitamente crear o cambiar algo, nunca por iniciativa propia. No "
    "tenés acceso a archivos, a una terminal, ni al código fuente del "
    "proyecto, y nunca aplicás ningún cambio por tu cuenta.\n\n"
    "Respondé ÚNICAMENTE preguntas relacionadas con SquidManager, Squid y "
    "cómo administrar este panel. Si te preguntan algo sin relación con "
    "eso, decí con amabilidad que solo podés ayudar con SquidManager y no "
    "respondas esa otra pregunta. Respondé siempre en el mismo idioma en que está escrita la pregunta "
    "(español, inglés o portugués)."
)


def preguntar_agentico(db: Session, config: AiConfig, pregunta: str) -> dict:
    """Modo agéntico (fase 1): el modelo puede consultar el estado real del
    servidor y proponer cambios -nunca aplicarlos-, ver ai_tools.py."""
    from app.services.ai_tools import TOOL_DEFS, ejecutar_herramienta

    info, url = _datos_proveedor(config.provider, getattr(config, "base_url", None))
    if not info["agentico"]:
        raise AiServiceError(
            "El modo agéntico todavía no está disponible con este proveedor. "
            "Prueba con Anthropic, OpenAI, Gemini, Groq, OpenRouter u otro compatible con OpenAI."
        )
    es_gemini = info["tipo"] == "gemini"
    es_anthropic = info["tipo"] == "anthropic"

    herramientas_usadas: list[str] = []
    propuesta: dict | None = None

    def _registrar_resultado(nombre: str, argumentos: dict) -> dict:
        nonlocal propuesta
        herramientas_usadas.append(nombre)
        try:
            salida = ejecutar_herramienta(db, config, nombre, argumentos)
        except Exception as e:
            # No solo ValueError (nombre de herramienta desconocido): un
            # fallo real de una herramienta -Jina AI caído a mitad de
            # buscar_documentacion, un error de base de datos puntual- no
            # debe tirar abajo toda la conversación. Se le devuelve el
            # error al modelo como parte del resultado de ESA llamada, para
            # que pueda decidir cómo seguir (reintentar, avisar, usar otra
            # herramienta) en vez de que la pregunta entera termine en una
            # excepción sin ninguna respuesta.
            logger.warning(f"Herramienta '{nombre}' falló en modo agéntico: {e}")
            return {"error": str(e)}
        if salida.get("__propuesta__"):
            propuesta = {"accion": salida["accion"], "argumentos": salida["argumentos"]}
            return {"resultado": "Propuesta registrada: se le mostró al administrador para que la confirme."}
        return salida

    if es_gemini:
        contents = [{"role": "user", "parts": [{"text": pregunta}]}]
        for _ in range(_MAX_ITERACIONES_AGENTE):
            resultado = _gemini_generar_con_herramientas(
                contents, TOOL_DEFS, config.api_key, config.chat_model, _SYSTEM_PROMPT_AGENTICO,
            )
            if resultado["tipo"] == "texto":
                return {
                    "respuesta": resultado["contenido"], "fuentes": [],
                    "propuesta": propuesta, "herramientas_usadas": herramientas_usadas,
                }
            contents.append(resultado["mensaje_bruto"])
            partes = [
                {"functionResponse": {"name": ll["nombre"], "response": _registrar_resultado(ll["nombre"], ll["argumentos"])}}
                for ll in resultado["llamadas"]
            ]
            # Los modelos nuevos de Gemini rechazan el rol "function" (error 400
            # "Role 'function' is not supported"); "user" lo aceptan todos, y las
            # partes del modelo se reenvían tal cual (con su thoughtSignature).
            contents.append({"role": "user", "parts": partes})
    elif es_anthropic:
        messages = [{"role": "user", "content": pregunta}]
        for _ in range(_MAX_ITERACIONES_AGENTE):
            resultado = _anthropic_generar_con_herramientas(
                messages, TOOL_DEFS, config.api_key, config.chat_model, _SYSTEM_PROMPT_AGENTICO,
            )
            if resultado["tipo"] == "texto":
                return {
                    "respuesta": resultado["contenido"], "fuentes": [],
                    "propuesta": propuesta, "herramientas_usadas": herramientas_usadas,
                }
            messages.append(resultado["mensaje_bruto"])
            messages.append({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": ll["id"],
                 "content": json.dumps(_registrar_resultado(ll["nombre"], ll["argumentos"]), ensure_ascii=False)}
                for ll in resultado["llamadas"]
            ]})
    else:
        base_url, nombre_prov = url, info["nombre"]
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT_AGENTICO},
            {"role": "user", "content": pregunta},
        ]
        for _ in range(_MAX_ITERACIONES_AGENTE):
            resultado = _openai_compatible_generar_con_herramientas(
                messages, TOOL_DEFS, config.api_key, config.chat_model, base_url, nombre_prov,
            )
            if resultado["tipo"] == "texto":
                return {
                    "respuesta": resultado["contenido"], "fuentes": [],
                    "propuesta": propuesta, "herramientas_usadas": herramientas_usadas,
                }
            messages.append(resultado["mensaje_bruto"])
            for ll in resultado["llamadas"]:
                salida = _registrar_resultado(ll["nombre"], ll["argumentos"])
                messages.append({
                    "role": "tool", "tool_call_id": ll["id"],
                    "content": json.dumps(salida, ensure_ascii=False),
                })

    # Se agotaron las iteraciones sin que el modelo diera una respuesta de
    # texto final. Si ya había armado una propuesta en el camino, no
    # descartarla -sería tirar a la basura lo único útil que sí se logró-:
    # se devuelve igual, con una respuesta genérica en vez de la del modelo.
    if propuesta is not None:
        return {
            "respuesta": (
                "No pude terminar de redactar una respuesta, pero sí llegué a armar "
                "la propuesta de abajo -revisala antes de confirmarla."
            ),
            "fuentes": [], "propuesta": propuesta, "herramientas_usadas": herramientas_usadas,
        }

    raise AiServiceError(
        "El asistente no pudo terminar de responder tras varios pasos consultando "
        "el sistema. Probá reformular la pregunta."
    )


def preguntar(db: Session, config: AiConfig, pregunta: str, idioma: str = "es") -> dict:
    _IDIOMA_ACTUAL.set(idioma if idioma in _DICCIONARIO else "es")
    info = ai_providers.obtener(config.provider) or {}
    if not config.enabled or (info.get("requiere_clave", True) and not config.api_key):
        raise AiServiceError("El asistente de IA no está activado.")
    if not config.chat_model:
        raise AiServiceError("Falta configurar el modelo de respuesta en Ajustes del asistente.")

    if _SALUDOS.match(pregunta.strip()):
        return {"respuesta": _RESPUESTA_SALUDO, "fuentes": []}

    if config.agentic_enabled:
        return preguntar_agentico(db, config, pregunta)

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
