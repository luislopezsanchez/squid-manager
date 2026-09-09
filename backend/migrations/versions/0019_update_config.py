"""Comprobación de actualizaciones del propio SquidManager

Tabla de configuración para la nueva sección "Actualizaciones": si está
activada la comprobación automática contra el repositorio de GitHub del
proyecto. El estado operativo (si hay una actualización disponible, si hay
una aprobada/programada, el resultado de la última aplicada) vive fuera de
la base de datos, en un archivo que también necesita leer/escribir un
script sin credenciales de Postgres -ver app/services/update_service.py-.

Revision ID: 0019
Revises: 0018
"""
from alembic import op
import sqlalchemy as sa

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "update_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("check_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("update_config")
