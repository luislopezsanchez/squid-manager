"""Notificaciones: canal XMPP (cliente de un servidor de mensajería existente)

Revision ID: 0047
Revises: 0046
"""
from alembic import op
import sqlalchemy as sa

revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    t = "notification_config"
    op.add_column(t, sa.Column("xmpp_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column(t, sa.Column("xmpp_host", sa.String(255), nullable=True))
    op.add_column(t, sa.Column("xmpp_port", sa.Integer(), nullable=False, server_default="5222"))
    op.add_column(t, sa.Column("xmpp_jid", sa.String(255), nullable=True))
    # Va cifrada en reposo (EncryptedString): TEXT, sin tope, como las demas credenciales.
    op.add_column(t, sa.Column("xmpp_password", sa.Text(), nullable=True))
    op.add_column(t, sa.Column("xmpp_encryption", sa.String(20), nullable=False, server_default="starttls"))
    op.add_column(t, sa.Column("xmpp_verify_cert", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column(t, sa.Column("xmpp_recipients", sa.String(500), nullable=True))
    op.add_column(t, sa.Column("xmpp_room", sa.String(255), nullable=True))


def downgrade() -> None:
    t = "notification_config"
    for c in ("xmpp_room", "xmpp_recipients", "xmpp_verify_cert", "xmpp_encryption", "xmpp_password",
              "xmpp_jid", "xmpp_port", "xmpp_host", "xmpp_enabled"):
        op.drop_column(t, c)
