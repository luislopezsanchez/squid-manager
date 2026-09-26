"""Monitoreo centralizado: soporte para nodos "Squid básico" (sin SquidManager)

Revision ID: 0036
Revises: 0035
"""
from alembic import op
import sqlalchemy as sa

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "monitored_nodes",
        sa.Column("tipo", sa.String(length=20), nullable=False, server_default="squidmanager"),
    )
    # Un nodo "squid_basico" no tiene cuenta que validar (se consulta el
    # Cache Manager de Squid en HTTP plano, sin login) -ver
    # central_monitor_service.consultar_nodo_basico.
    op.alter_column("monitored_nodes", "username", existing_type=sa.String(length=100), nullable=True)
    op.alter_column("monitored_nodes", "password", existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    op.alter_column("monitored_nodes", "password", existing_type=sa.Text(), nullable=False)
    op.alter_column("monitored_nodes", "username", existing_type=sa.String(length=100), nullable=False)
    op.drop_column("monitored_nodes", "tipo")
