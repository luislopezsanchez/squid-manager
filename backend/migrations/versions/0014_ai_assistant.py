"""Asistente de IA: responde consultas sobre el uso del panel usando la
documentacion del proyecto como unica fuente.

Apagado por defecto (enabled=False), igual que Kerberos/LDAP/Syslog: sin una
API key configurada no sale ni un byte hacia ningun proveedor.

Requiere la extension `pgvector` de Postgres (paquete
`postgresql-<version>-pgvector` en Debian/Ubuntu, disponible en los repos
oficiales -no hace falta un repositorio de terceros-). Se crea con
IF NOT EXISTS: si ya estaba (por ejemplo, alguien la habilito a mano antes),
no falla.

CREATE EXTENSION exige ser superusuario de Postgres (o dueño de una
extension marcada "trusted", que `vector` no lo es). El usuario de BD de la
aplicacion (`squid` en una instalacion nativa) NO lo es a proposito -menor
privilegio-, asi que esta migracion FALLA con "permission denied to create
extension" en cualquier actualizacion nativa que llegue hasta aca sin que
alguien haya creado la extension antes como `postgres`. Confirmado en vivo:
`install-nativo.sh` lo resuelve en una instalacion NUEVA (crea la extension
el mismo, antes de que el backend corra ninguna migracion), pero una
actualizacion no vuelve a correr el instalador -ver el paso manual en
docs/actualizacion.md, seccion "Instalacion nativa"-. En Docker no pasa
porque el usuario de BD ahi (`POSTGRES_USER`) es superusuario por como
inicializa la imagen oficial de Postgres, no por diseno de este proyecto.

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
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

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