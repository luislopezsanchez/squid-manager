"""Idioma de cada fragmento indexado de la documentación del asistente

El índice deja de ser solo español: se indexan también las versiones en inglés
y portugués (README, instalación y la documentación del panel), cada una con
su propio diccionario de texto completo, y se busca en el idioma del panel.

Revision ID: 0045
Revises: 0044
"""
from alembic import op
import sqlalchemy as sa

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("doc_chunks", sa.Column("idioma", sa.String(length=2), nullable=False, server_default="es"))
    op.create_index("ix_doc_chunks_idioma", "doc_chunks", ["idioma"])


def downgrade() -> None:
    op.drop_index("ix_doc_chunks_idioma", table_name="doc_chunks")
    op.drop_column("doc_chunks", "idioma")
