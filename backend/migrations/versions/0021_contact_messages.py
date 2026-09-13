"""Mensajes del formulario de Contacto

Guarda cada mensaje enviado desde la sección Ayuda > Contacto (reporte de
error, sugerencia, u otro), aunque el envío por email falle o la instalación
no tenga SMTP configurado -no depende de la notificación por correo para no
perder el reporte.

Revision ID: 0021
Revises: 0020
"""
from alembic import op
import sqlalchemy as sa

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contact_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("admin_username", sa.String(length=100), nullable=False),
        sa.Column("categoria", sa.String(length=30), nullable=False),
        sa.Column("mensaje", sa.Text(), nullable=False),
        sa.Column("email_respuesta", sa.String(length=255), nullable=True),
        sa.Column("enviado_por_email", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("detalle_envio", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("contact_messages")
