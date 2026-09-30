"""URL base del proveedor de IA (proveedor personalizado / Ollama en la red)

Revision ID: 0044
Revises: 0043
"""
from alembic import op
import sqlalchemy as sa

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ai_config", sa.Column("base_url", sa.String(length=300), nullable=True))


def downgrade() -> None:
    op.drop_column("ai_config", "base_url")
