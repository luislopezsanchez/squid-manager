"""Sincronización automática de categorías desde una URL externa

Permite marcar una categoría de dominios (is_category=true) con una URL de
la que se refresca sola una vez al día -pensado para blocklists públicas
como las de HaGeZi (dns-blocklists). Nace en NULL para todas las ACLs
existentes: ninguna categoría creada antes de esto empieza a sincronizar
por su cuenta, sigue siendo 100% manual hasta que el admin la conecte a
una URL a propósito.

Revision ID: 0026
Revises: 0025
"""
from alembic import op
import sqlalchemy as sa

revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("acls", sa.Column("sync_url", sa.String(length=500), nullable=True))
    op.add_column("acls", sa.Column("last_synced_at", sa.DateTime(), nullable=True))
    op.add_column("acls", sa.Column("last_sync_status", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("acls", "last_sync_status")
    op.drop_column("acls", "last_synced_at")
    op.drop_column("acls", "sync_url")
