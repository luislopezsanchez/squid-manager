"""Usuarios LDAP: marca de «ya no está en el directorio»

Revision ID: 0048
Revises: 0047
"""
from alembic import op
import sqlalchemy as sa

revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ldap_users", sa.Column("en_directorio", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    op.drop_column("ldap_users", "en_directorio")
