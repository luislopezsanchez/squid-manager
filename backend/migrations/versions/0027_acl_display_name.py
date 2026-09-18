"""Nombre amigable para categorías de dominio, separado del técnico

Las categorías predefinidas de HaGeZi (migración 0026) quedan con un nombre
técnico con prefijo (ej. "hagezi_gambling") para que se note de dónde
vienen -sigue siendo el identificador real que usa Squid-, pero eso no es
lo más legible para mostrar en la tabla del panel. `display_name` es un
nombre amigable opcional (ej. "Apuestas y juego online") que se muestra en
su lugar cuando existe; nace en NULL para toda categoría existente, sin
cambiar nada de lo que ya hay.

Revision ID: 0027
Revises: 0026
"""
from alembic import op
import sqlalchemy as sa

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("acls", sa.Column("display_name", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("acls", "display_name")
