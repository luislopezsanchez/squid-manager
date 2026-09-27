"""Cuota de navegación compartida por un grupo entero (pool compartido)

Nueva tabla, igual patrón que navigation_quotas (0030) pero por nombre de
grupo -solo grupos locales, ver el docstring de GroupQuota-. delay_pools
suma group_quota_id, simétrico a quota_id, para el pool que gestiona
quota_service.py cuando la acción es "limitar velocidad".

Revision ID: 0039
Revises: 0038
"""
from alembic import op
import sqlalchemy as sa

revision = "0039"
down_revision = "0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "group_quotas",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("group_name", sa.String(length=100), nullable=False, unique=True, index=True),
        sa.Column("quota_bytes", sa.BigInteger(), nullable=False),
        sa.Column("quota_period", sa.String(length=10), nullable=False),
        sa.Column("quota_action", sa.String(length=10), nullable=False, server_default="cut"),
        sa.Column("quota_throttle_bytes_per_sec", sa.Integer(), nullable=True),
        sa.Column("quota_bytes_used", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("quota_period_started_at", sa.DateTime(), nullable=True),
        sa.Column("quota_action_applied", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.add_column("delay_pools", sa.Column(
        "group_quota_id", sa.Integer(),
        sa.ForeignKey("group_quotas.id", ondelete="CASCADE"),
        nullable=True, unique=True,
    ))


def downgrade() -> None:
    op.drop_column("delay_pools", "group_quota_id")
    op.drop_table("group_quotas")
