"""Salida a Internet a traves de un proxy padre

En muchas empresas la salida directa esta cerrada en el cortafuegos y todo el
trafico tiene que pasar por el proxy corporativo. Sin esta opcion, SquidManager
no se puede desplegar en esas redes.

La tabla se crea apagada (enabled=False): la mayoria de instalaciones salen
directas, y activar esto sin configurarlo cortaria la navegacion entera.

never_direct por defecto en True porque es lo coherente con tener un padre: si
existe, normalmente el cortafuegos bloquea la salida directa, e intentarla solo
anade una espera antes de fallar igual.

Revision ID: 0008
Revises: 0007
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "parent_proxy",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("host", sa.String(length=255), nullable=True),
        sa.Column("port", sa.Integer(), nullable=False, server_default="3128"),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("password", sa.String(length=255), nullable=True),
        sa.Column("never_direct", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("direct_domains", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("parent_proxy")
