"""Usuarios del proxy: nombre para mostrar (mismo campo que LdapUser)

Revision ID: 0038
Revises: 0037
"""
from alembic import op
import sqlalchemy as sa

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "proxy_users",
        sa.Column("display_name", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("proxy_users", "display_name")
