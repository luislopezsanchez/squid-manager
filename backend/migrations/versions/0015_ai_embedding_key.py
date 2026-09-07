"""Key de embeddings separada de la key del proveedor de chat

Los embeddings (búsqueda semántica sobre la documentación) siempre son de
Gemini, sea cual sea el proveedor elegido para responder la pregunta -es el
único de los soportados con un endpoint de embeddings documentado y
estable-. Guardar una sola `api_key` compartida rompía en cuanto se elegía
un proveedor de chat distinto de Gemini: los embeddings intentaban usar la
key de ese otro proveedor. Encontrado probando con Groq configurado.

Revision ID: 0015
Revises: 0014
"""
from alembic import op
import sqlalchemy as sa

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ai_config", sa.Column("embedding_api_key", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_config", "embedding_api_key")
