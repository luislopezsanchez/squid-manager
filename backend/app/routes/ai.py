"""Rutas del asistente de IA: responde consultas sobre el uso del panel

usando la documentación del proyecto como única fuente. Apagado por defecto,
igual que LDAP/Kerberos/Syslog.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.i18n import idioma_de_cabecera
from app.models.admin import Admin
from app.models.audit_log import AuditLog
from app.models.ai_config import AiConfig
from app.models.doc_chunk import DocChunk
from app.services import ai_providers
from app.services.auth_service import get_current_admin, require_writer
from app.services.ai_service import (
    AiServiceError,
    listar_modelos,
    preguntar,
    probar_jina,
    reindexar_documentacion,
)

router = APIRouter()

_PROVEEDORES_VALIDOS = tuple(ai_providers.PROVEEDORES)


class AiConfigIn(BaseModel):
    enabled: bool = False
    provider: str = "gemini"
    api_key: str | None = None
    # La key de Jina AI para embeddings (búsqueda semántica): siempre
    # separada de la del proveedor de chat -ver ai_service.py-.
    embedding_api_key: str | None = None
    chat_model: str | None = None
    base_url: str | None = None
    embedding_model: str | None = None
    # Fase 1 del asistente agéntico: consulta el estado real del servidor y
    # puede proponer cambios -nunca aplicarlos solo-, ver ai_tools.py.
    agentic_enabled: bool = False


class PreguntaIn(BaseModel):
    pregunta: str


class ProbarProveedorIn(BaseModel):
    provider: str
    api_key: str | None = None
    base_url: str | None = None


class ProbarEmbeddingsIn(BaseModel):
    api_key: str


def _obtener_o_crear(db: Session) -> AiConfig:
    config = db.query(AiConfig).first()
    if not config:
        config = AiConfig(id=1)
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


def _validar_url_base(provider: str, base_url: str | None) -> str | None:
    """URL base de un proveedor con URL editable: http(s) y sin credenciales embebidas."""
    info = ai_providers.obtener(provider)
    if not info or not info["url_editable"]:
        return None
    url = (base_url or "").strip().rstrip("/")
    if not url:
        raise HTTPException(400, detail="Indica la URL base del proveedor (por ejemplo https://mi-servidor/v1).")
    import re
    if not re.match(r"^https?://[^\s/@]+(:\d+)?(/\S*)?$", url):
        raise HTTPException(400, detail="La URL base debe empezar por http:// o https:// y no puede llevar usuario ni contraseña.")
    return url


@router.get("/proveedores")
def proveedores(_: Admin = Depends(get_current_admin)):
    """Catálogo de proveedores de IA que se pueden elegir (más uno personalizado compatible con OpenAI)."""
    return ai_providers.catalogo_publico()


@router.get("/config")
def get_config(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    config = _obtener_o_crear(db)
    total_fragmentos = db.query(DocChunk).count()
    return {
        "enabled": config.enabled,
        "provider": config.provider,
        # Nunca se devuelve la key real, igual que el bind de LDAP y la
        # contraseña de bind del proxy padre: si ya hay una guardada, el
        # panel solo necesita saber que existe, no verla.
        "api_key": "***" if config.api_key else "",
        "embedding_api_key": "***" if config.embedding_api_key else "",
        "chat_model": config.chat_model or "",
        "base_url": config.base_url or "",
        "embedding_model": config.embedding_model or "",
        "fragmentos_indexados": total_fragmentos,
        "agentic_enabled": config.agentic_enabled,
    }


@router.put("/config")
def update_config(
    data: AiConfigIn,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
):
    if data.provider not in _PROVEEDORES_VALIDOS:
        raise HTTPException(400, detail=f"provider debe ser uno de: {', '.join(_PROVEEDORES_VALIDOS)}")

    info = ai_providers.obtener(data.provider)
    url_base = _validar_url_base(data.provider, data.base_url)
    config = _obtener_o_crear(db)
    api_key_cambio = bool(data.api_key and data.api_key != "***")
    embedding_key_cambio = bool(data.embedding_api_key and data.embedding_api_key != "***")
    config.enabled = data.enabled
    config.provider = data.provider
    config.base_url = url_base
    if api_key_cambio:
        config.api_key = data.api_key
    elif data.api_key == "":
        config.api_key = None
    if embedding_key_cambio:
        config.embedding_api_key = data.embedding_api_key
    config.chat_model = data.chat_model
    config.embedding_model = data.embedding_model
    config.agentic_enabled = data.agentic_enabled

    if config.enabled and info["requiere_clave"] and not config.api_key:
        raise HTTPException(400, detail="Hace falta una API key para habilitar el asistente")
    if config.enabled and not config.chat_model:
        raise HTTPException(400, detail="Elige el modelo con el que responderá el asistente (usa «Probar conexión» para ver los disponibles).")
    if config.agentic_enabled and not info["agentico"]:
        raise HTTPException(400, detail="El modo agéntico no está disponible con este proveedor todavía.")

    # Nunca las API keys, solo si cambiaron.
    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="update", entity="ai_config", entity_id=config.id,
        new_value=(
            f"enabled={config.enabled} provider={config.provider} chat_model={config.chat_model} "
            f"agentic_enabled={config.agentic_enabled} "
            f"api_key={'(cambiada)' if api_key_cambio else '(sin cambios)'} "
            f"embedding_api_key={'(cambiada)' if embedding_key_cambio else '(sin cambios)'}"
        ),
    ))
    db.commit()
    return {"status": "ok", "message": "Configuración del asistente guardada"}


@router.post("/probar-proveedor")
async def probar_proveedor(
    data: ProbarProveedorIn,
    _: Admin = Depends(require_writer),
):
    """Prueba una API key contra el proveedor de chat elegido y devuelve los

    modelos disponibles -así se elige de una lista real en vez de escribir
    un nombre a mano y enterarse recién al preguntar si existe o no. No
    toca la configuración guardada: es solo una prueba antes de guardar.
    """
    if data.provider not in _PROVEEDORES_VALIDOS:
        raise HTTPException(400, detail=f"provider debe ser uno de: {', '.join(_PROVEEDORES_VALIDOS)}")
    info = ai_providers.obtener(data.provider)
    if info["requiere_clave"] and (not data.api_key or data.api_key == "***"):
        raise HTTPException(400, detail="Falta la API key a probar")
    url_base = _validar_url_base(data.provider, data.base_url)

    try:
        modelos = await run_in_threadpool(listar_modelos, data.provider, None if data.api_key == "***" else data.api_key, url_base)
    except AiServiceError as e:
        raise HTTPException(400, detail=str(e))
    return {"status": "ok", "modelos": modelos}


@router.post("/probar-embeddings")
async def probar_embeddings(
    data: ProbarEmbeddingsIn,
    _: Admin = Depends(require_writer),
):
    """Prueba la key de Jina AI pidiendo un embedding mínimo, sin guardar nada."""
    if not data.api_key or data.api_key == "***":
        raise HTTPException(400, detail="Falta la API key de Jina a probar")

    try:
        dimensiones = await run_in_threadpool(probar_jina, data.api_key)
    except AiServiceError as e:
        raise HTTPException(400, detail=str(e))
    return {"status": "ok", "dimensiones": dimensiones}


@router.post("/reindexar")
async def reindexar(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
):
    """Vuelve a indexar toda la documentación desde cero.

    Bloqueante (una llamada de red por fragmento) — se delega al threadpool
    para no congelar el event loop mientras dura, mismo motivo que ya llevó
    a envolver /squid/apply.
    """
    config = _obtener_o_crear(db)
    try:
        resultado = await run_in_threadpool(reindexar_documentacion, db, config)
    except AiServiceError as e:
        raise HTTPException(400, detail=str(e))
    return {"status": "ok", **resultado}


@router.post("/preguntar")
async def responder_pregunta(
    request: Request,
    data: PreguntaIn,
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Cualquier admin puede preguntar (incluido un viewer): en modo normal es

    una consulta de solo lectura sobre documentación; en modo agéntico
    también puede leer el estado real (mismos datos a los que un viewer ya
    tiene acceso por otras páginas del panel) y proponer cambios -nunca
    aplicarlos, ver ai_tools.py-, así que tampoco requiere permisos de
    escritura.
    """
    if not data.pregunta.strip():
        raise HTTPException(400, detail="La pregunta no puede estar vacía")

    config = db.query(AiConfig).first()
    if not config or not config.enabled:
        raise HTTPException(400, detail="El asistente de IA no está activado")

    try:
        idioma = idioma_de_cabecera(request.headers.get("accept-language"))
        resultado = await run_in_threadpool(preguntar, db, config, data.pregunta.strip(), idioma)
    except AiServiceError as e:
        raise HTTPException(400, detail=str(e))
    return resultado
