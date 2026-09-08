"""Modelo DocChunk: fragmentos indexados de la documentación del proyecto,
para que el asistente de IA busque en ellos antes de responder.

Búsqueda híbrida, no solo semántica: `tsv` (texto completo de Postgres, ya
incluido de fábrica, sin extensión aparte) encuentra coincidencias literales
-nombres de ajustes, comandos exactos-; `embedding` (pgvector) encuentra
fragmentos relacionados por significado aunque no compartan palabras. Se
combinan las dos búsquedas al consultar, en vez de depender de una sola.
"""

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, Integer, String, Text, DateTime, Index
from sqlalchemy.dialects.postgresql import TSVECTOR

from app.utils import utcnow
from app.database import Base

# Dimensión fija para poder indexar de verdad con pgvector. Si se cambia de
# proveedor o de modelo de embeddings a uno con otra dimensión, hace falta
# reindexar todo -no es un ajuste que se pueda cambiar a mitad de camino sin
# rehacer los vectores existentes, y "Reindexar" ya vacía la tabla antes de
# volver a llenarla-.
EMBEDDING_DIM = 768


class DocChunk(Base):
    __tablename__ = "doc_chunks"

    id = Column(Integer, primary_key=True)
    # Ruta relativa dentro del repo (docs/kerberos.md, README.md...), para
    # poder decir de dónde salió la respuesta y para poder borrar/reemplazar
    # los fragmentos de un archivo cuando se reindexa.
    source_file = Column(String(255), nullable=False, index=True)
    heading = Column(String(500), nullable=True)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(EMBEDDING_DIM), nullable=True)
    tsv = Column(TSVECTOR, nullable=True)
    created_at = Column(DateTime, default=utcnow)


Index("ix_doc_chunks_tsv", DocChunk.tsv, postgresql_using="gin")

# Sin índice aproximado (ivfflat/hnsw) sobre `embedding` a propósito: esa
# clase de índice solo vale la pena a partir de miles de filas, y hasta ahí
# introduce error de aproximación sin necesidad. La documentación entera son
# unos pocos cientos de fragmentos como mucho -un escaneo exacto por
# distancia coseno (`ORDER BY embedding <=> :consulta`) tarda milisegundos y
# da el resultado real, no uno aproximado-.
