"""Correo electrónico opcional de un usuario local del proxy

Igual que ldap_users.email (que ya sincroniza el directorio): un dato
opcional para identificar a la persona y, más adelante, avisarle (por
ejemplo, al agotar su cuota). Vacío si el admin no lo escribe.

Revision ID: 0041
Revises: 0040
"""
from alembic import op
import sqlalchemy as sa

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("proxy_users", sa.Column("email", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("proxy_users", "email")
