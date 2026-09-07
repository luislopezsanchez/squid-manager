"""Asistente de IA: responde consultas sobre el uso del panel usando la
documentacion del proyecto como unica fuente.

Apagado por defecto (enabled=False), igual que Kerberos/LDAP/Syslog: sin una
API key configurada no sale ni un byte hacia ningun proveedor.

Requiere la extension `pgvector` de Postgres, ya creada de antemano -esta
migracion NO la crea ella misma-: el rol con el que corre la app no es
superusuario (a proposito) y CREATE EXTENSION exige serlo. La crea el
instalador nativo como usuario `postgres` al preparar la base de datos
(install-nativo.sh), y en Docker la trae ya integrada la imagen
`pgvector/pgvector` (ver docker-compose.yml). Una instalacion nativa
existente que actualice a esta version necesita el mismo paso a mano una vez
-ver docs/actualizacion.md-.

Revision ID: 0014
Revises: 0013
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import TSVECTOR

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

EMBEDDING_DIM = 768


def upgrade() -> None:
    op.create_table(
        "ai_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("provider", sa.String(length=30), nullable=False, server_default="gemini"),
        sa.Column("api_key", sa.String(length=500), nullable=True),
        sa.Column("chat_model", sa.String(length=100), nullable=True),
        sa.Column("embedding_model", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "doc_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_file", sa.String(length=255), nullable=False),
        sa.Column("heading", sa.String(length=500), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        sa.Column("tsv", TSVECTOR(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_doc_chunks_source_file", "doc_chunks", ["source_file"])
    op.execute(
        "CREATE INDEX ix_doc_chunks_tsv ON doc_chunks USING gin (tsv)"
    )
    # Sin indice aproximado (ivfflat/hnsw) sobre embedding: la documentacion
    # entera son a lo sumo unos pocos cientos de fragmentos, y un escaneo
    # exacto por distancia coseno tarda milisegundos a ese tamano -no hace
    # falta pagar el costo de aproximacion de un indice pensado para miles de
    # filas-.


def downgrade() -> None:
    op.drop_table("doc_chunks")
    op.drop_table("ai_config")
