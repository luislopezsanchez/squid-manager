"""Monitoreo centralizado: segundo interruptor para monitorizar (o no) los nodos propios

Revision ID: 0035
Revises: 0034
"""
from alembic import op
import sqlalchemy as sa

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "central_monitor_config",
        sa.Column("monitorizar_hijos", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("central_monitor_config", "monitorizar_hijos")
