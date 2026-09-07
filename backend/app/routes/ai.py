"""Rutas del asistente de IA: responde consultas sobre el uso del panel

usando la documentación del proyecto como única fuente. Apagado por defecto,
igual que LDAP/Kerberos/Syslog.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.admin import Admin
from app.models.ai_config import AiConfig
from app.models.doc_chunk import DocChunk
from app.services.auth_service import get_current_admin, require_writer
from app.services.ai_service import (
    AiServiceError,
    listar_modelos,
    preguntar,
    probar_jina,
    reindexar_documentacion,
)

router = APIRouter()

_PROVEEDORES_VALIDOS = ("gemini", "ollama_cloud", "nvidia_nim", "groq")


class AiConfigIn(BaseModel):
    enabled: bool = False
    provider: str = "gemini"
    api_key: str | None = None
    # La key de Jina AI para embeddings (búsqueda semántica): siempre
    # separada de la del proveedor de chat -ver ai_service.py-.
    embedding_api_key: str | None = None
    chat_model: str | None = None
    embedding_model: str | None = None


class PreguntaIn(BaseModel):
    pregunta: str


class ProbarProveedorIn(BaseModel):
    provider: str
    api_key: str


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


@router.get("/config")
async def get_config(
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
        "embedding_model": config.embedding_model or "",
        "fragmentos_indexados": total_fragmentos,
    }


@router.put("/config")
async def update_config(
    data: AiConfigIn,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
):
    if data.provider not in _PROVEEDORES_VALIDOS:
        raise HTTPException(400, detail=f"provider debe ser uno de: {', '.join(_PROVEEDORES_VALIDOS)}")

    config = _obtener_o_crear(db)
    config.enabled = data.enabled
    config.provider = data.provider
    if data.api_key and data.api_key != "***":
        config.api_key = data.api_key
    if data.embedding_api_key and data.embedding_api_key != "***":
        config.embedding_api_key = data.embedding_api_key
    config.chat_model = data.chat_model
    config.embedding_model = data.embedding_model

    if config.enabled and not config.api_key:
        raise HTTPException(400, detail="Hace falta una API key para habilitar el asistente")
    if config.enabled and not config.embedding_api_key:
        raise HTTPException(
            400,
            detail="Hace falta la API key de Jina AI para poder buscar en la documentación.",
        )

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
    if not data.api_key or data.api_key == "***":
        raise HTTPException(400, detail="Falta la API key a probar")

    try:
        modelos = await run_in_threadpool(listar_modelos, data.provider, data.api_key)
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
    data: PreguntaIn,
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Cualquier admin puede preguntar (incluido un viewer): es una consulta

    de solo lectura sobre documentación, no una acción sobre el proxy.
    """
    if not data.pregunta.strip():
        raise HTTPException(400, detail="La pregunta no puede estar vacía")

    config = db.query(AiConfig).first()
    if not config or not config.enabled:
        raise HTTPException(400, detail="El asistente de IA no está activado")

    try:
        resultado = await run_in_threadpool(preguntar, db, config, data.pregunta.strip())
    except AiServiceError as e:
        raise HTTPException(400, detail=str(e))
    return resultado
