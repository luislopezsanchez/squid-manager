"""Asistente de IA: modo agéntico (fase 1 -diagnóstico y propuestas, nunca
aplica nada solo)

Revision ID: 0033
Revises: 0032
"""
from alembic import op
import sqlalchemy as sa

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ai_config", sa.Column(
        "agentic_enabled", sa.Boolean(), nullable=False, server_default=sa.false(),
    ))


def downgrade() -> None:
    op.drop_column("ai_config", "agentic_enabled")
