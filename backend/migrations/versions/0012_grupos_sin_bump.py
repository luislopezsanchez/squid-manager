"""Grupos exentos de la interceptacion de HTTPS

Hay equipos donde no se puede instalar el certificado (moviles personales,
BYOD) y herramientas que se rompen al interceptarlas: git, npm, docker y
cualquier aplicacion con certificate pinning. Sin una via para eximirlos, la
unica salida era desactivar la interceptacion para todo el mundo.

Quedar exento del descifrado NO es quedar exento del filtrado: el bloqueo por
dominio actua antes de descifrar (sobre el SNI) y les sigue afectando. Lo que
se pierde en esos usuarios es la inspeccion de la URL completa y del contenido.

Se crea en false: ningun grupo queda exento salvo que se marque a proposito.

Revision ID: 0012
Revises: 0011
"""
from alembic import op
import sqlalchemy as sa

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_groups",
        sa.Column("no_bump", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("user_groups", "no_bump")
