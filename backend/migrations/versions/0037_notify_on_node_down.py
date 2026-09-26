"""Notificaciones: nuevo evento "nodo caído" (Monitoreo Centralizado)

Revision ID: 0037
Revises: 0036
"""
from alembic import op
import sqlalchemy as sa

revision = "0037"
down_revision = "0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "notification_config",
        sa.Column("notify_on_node_down", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("notification_config", "notify_on_node_down")
