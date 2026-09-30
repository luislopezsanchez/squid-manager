"""Catálogo de proveedores de IA del Asistente.

El admin elige UNO (con su propia clave) de esta lista, o uno personalizado
compatible con la API de OpenAI (URL + clave). Nada más: la búsqueda en la
documentación ya no necesita un segundo servicio (ver ai_service.py).

`tipo` decide cómo se habla con el proveedor:
  - openai:    `POST {base}/chat/completions` (formato de OpenAI; lo usan casi todos).
  - anthropic: API nativa de Anthropic (`/v1/messages`).
  - gemini:    API nativa de Google.
  - ollama:    API nativa de Ollama Cloud (`/api/chat`).
"""

PROVEEDORES: dict[str, dict] = {
    "anthropic": {
        "nombre": "Anthropic (Claude)", "tipo": "anthropic", "url": "https://api.anthropic.com/v1",
        "modelo_ejemplo": "claude-haiku-4-5-20251001", "requiere_clave": True, "url_editable": False, "agentico": True,
        "ayuda": "Claude Haiku es rápido y barato: suficiente para responder sobre la plataforma.",
    },
    "openai": {
        "nombre": "OpenAI", "tipo": "openai", "url": "https://api.openai.com/v1",
        "modelo_ejemplo": "gpt-4o-mini", "requiere_clave": True, "url_editable": False, "agentico": True,
        "ayuda": "Los modelos «mini» son los más económicos.",
    },
    "gemini": {
        "nombre": "Gemini (Google)", "tipo": "gemini", "url": "https://generativelanguage.googleapis.com/v1beta",
        "modelo_ejemplo": "gemini-flash-latest", "requiere_clave": True, "url_editable": False, "agentico": True,
        "ayuda": "Tiene un nivel gratuito, con límites de uso ajustados.",
    },
    "groq": {
        "nombre": "Groq", "tipo": "openai", "url": "https://api.groq.com/openai/v1",
        "modelo_ejemplo": "openai/gpt-oss-20b", "requiere_clave": True, "url_editable": False, "agentico": True,
        "ayuda": "Muy rápido, con nivel gratuito.",
    },
    "openrouter": {
        "nombre": "OpenRouter", "tipo": "openai", "url": "https://openrouter.ai/api/v1",
        "modelo_ejemplo": "openai/gpt-4o-mini", "requiere_clave": True, "url_editable": False, "agentico": True,
        "ayuda": "Una sola clave para cientos de modelos de distintos fabricantes.",
    },
    "deepseek": {
        "nombre": "DeepSeek", "tipo": "openai", "url": "https://api.deepseek.com/v1",
        "modelo_ejemplo": "deepseek-chat", "requiere_clave": True, "url_editable": False, "agentico": True,
        "ayuda": "Precio muy bajo por token.",
    },
    "mistral": {
        "nombre": "Mistral AI", "tipo": "openai", "url": "https://api.mistral.ai/v1",
        "modelo_ejemplo": "mistral-small-latest", "requiere_clave": True, "url_editable": False, "agentico": True,
        "ayuda": "Proveedor europeo.",
    },
    "nvidia_nim": {
        "nombre": "NVIDIA NIM", "tipo": "openai", "url": "https://integrate.api.nvidia.com/v1",
        "modelo_ejemplo": "meta/llama-3.1-8b-instruct", "requiere_clave": True, "url_editable": False, "agentico": True,
        "ayuda": "",
    },
    "ollama_cloud": {
        "nombre": "Ollama Cloud", "tipo": "ollama", "url": "https://ollama.com",
        "modelo_ejemplo": "llama3.1", "requiere_clave": True, "url_editable": False, "agentico": False,
        "ayuda": "El modo agéntico no está disponible con este proveedor.",
    },
    "ollama_local": {
        "nombre": "Ollama (en tu red)", "tipo": "openai", "url": "http://localhost:11434/v1",
        "modelo_ejemplo": "llama3.1", "requiere_clave": False, "url_editable": True, "agentico": True,
        "ayuda": "Un modelo propio en tu red: nada sale a Internet. Indica la URL de tu servidor Ollama (termina en /v1).",
    },
    "personalizado": {
        "nombre": "Personalizado (compatible con OpenAI)", "tipo": "openai", "url": "",
        "modelo_ejemplo": "", "requiere_clave": False, "url_editable": True, "agentico": True,
        "ayuda": "Cualquier servicio con API compatible con OpenAI (vLLM, LM Studio, LiteLLM, Azure…): indica su URL base (termina en /v1) y, si la pide, su clave.",
    },
}


def obtener(provider: str) -> dict | None:
    return PROVEEDORES.get(provider)


def url_efectiva(provider: str, base_url: str | None) -> str:
    """La URL a usar: la que escribió el admin si el proveedor la admite, si no la del catálogo."""
    p = PROVEEDORES[provider]
    if p["url_editable"] and base_url:
        return base_url.strip().rstrip("/")
    return p["url"]


def catalogo_publico() -> list[dict]:
    return [
        {"id": k, "nombre": v["nombre"], "tipo": v["tipo"], "url_defecto": v["url"], "url_editable": v["url_editable"],
         "requiere_clave": v["requiere_clave"], "modelo_ejemplo": v["modelo_ejemplo"], "agentico": v["agentico"], "ayuda": v["ayuda"]}
        for k, v in PROVEEDORES.items()
    ]
