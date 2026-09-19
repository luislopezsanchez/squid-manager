"""Marca los delay pools creados automáticamente por una cuota agotada

`quota_user_id` identifica el delay pool que el hilo de fondo de cuotas
(quota_service.py) crea solo cuando un usuario agota su cuota con la
acción "limitar velocidad" -así el mismo hilo puede encontrarlo y
borrarlo al empezar el siguiente periodo, sin arriesgarse a tocar un pool
que el admin haya creado a mano con el mismo nombre de ACL. NULL para
todo pool creado desde la interfaz, como hasta ahora.

Revision ID: 0029
Revises: 0028
"""
from alembic import op
import sqlalchemy as sa

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("delay_pools", sa.Column(
        "quota_user_id", sa.Integer(),
        sa.ForeignKey("proxy_users.id", ondelete="CASCADE"),
        nullable=True, unique=True,
    ))


def downgrade() -> None:
    op.drop_column("delay_pools", "quota_user_id")
