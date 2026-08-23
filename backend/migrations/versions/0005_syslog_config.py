"""Reenvio opcional de logs a un syslog externo

Nueva tabla syslog_config, apagada por defecto (enabled=False): es un canal
opcional para compartir logs con un SIEM o herramienta de auditoria externa,
no algo que se activa solo. El admin define host, puerto, protocolo (UDP/TCP),
formato del mensaje (RFC 3164 / RFC 5424) y formato del cuerpo (linea nativa
de Squid o el mismo NDJSON de la exportacion) cuando lo necesite.

Revision ID: 0005
Revises: 0004
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "syslog_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("host", sa.String(length=255), nullable=True),
        sa.Column("port", sa.Integer(), nullable=False, server_default="514"),
        sa.Column("protocol", sa.String(length=10), nullable=False, server_default="udp"),
        sa.Column("rfc_format", sa.String(length=20), nullable=False, server_default="rfc3164"),
        sa.Column("facility", sa.String(length=20), nullable=False, server_default="local0"),
        sa.Column("log_format", sa.String(length=20), nullable=False, server_default="raw"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("syslog_config")
