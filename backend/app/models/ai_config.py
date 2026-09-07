"""Modelo AiConfig: asistente de IA que responde consultas sobre el uso del
panel, usando la documentación del proyecto como única fuente.

Apagado por defecto, como LDAP/Kerberos/Syslog: sin API key configurada, este
canal no hace nada -ni un byte sale del servidor hacia ningun proveedor-.
"""

from app.utils import utcnow
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.database import Base


class AiConfig(Base):
    __tablename__ = "ai_config"

    id = Column(Integer, primary_key=True, default=1)
    enabled = Column(Boolean, default=False, nullable=False)
    # gemini | ollama_cloud. Cada proveedor tiene su propio adaptador en
    # ai_service.py; agregar uno nuevo no toca esta tabla.
    provider = Column(String(30), default="gemini", nullable=False)
    api_key = Column(String(500), nullable=True)
    # Los embeddings (búsqueda semántica) siempre son de Jina AI, sea cual
    # sea el proveedor elegido para responder -ver la nota al principio de
    # ai_service.py sobre por qué Jina y no el `provider` de arriba-, así
    # que siempre necesitan su propia key, independiente de `api_key`.
    embedding_api_key = Column(String(500), nullable=True)
    # Modelo de generacion (responde la pregunta) y de embeddings (para la
    # busqueda semantica al indexar/consultar la documentacion) -son
    # necesidades distintas y no todos los proveedores usan el mismo modelo
    # para las dos cosas-.
    chat_model = Column(String(100), nullable=True)
    embedding_model = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
