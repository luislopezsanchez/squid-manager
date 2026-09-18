"""Categorias de dominios: marcar ACLs de dominio como reutilizables

Una categoria (ej. "Redes sociales") es, para Squid, una ACL de dominios
como cualquier otra -mismo mecanismo de carga de archivo, misma generacion
de squid.conf. Este flag es solo una capa de identidad para que el panel
las muestre en su propia pantalla ("Categorias de dominios") y las
distinga de las ACLs tecnicas de siempre (src, port, time, proxy_auth...),
sin duplicar nada del mecanismo existente.

Nace en false para todas las ACLs existentes: no cambia el comportamiento
de ninguna ACL ya creada al actualizar.

Revision ID: 0025
Revises: 0024
"""
from alembic import op
import sqlalchemy as sa

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("acls", sa.Column("is_category", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("acls", "is_category")
