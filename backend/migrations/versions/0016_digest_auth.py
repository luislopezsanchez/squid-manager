"""Autenticacion Digest (RFC 2617) para usuarios locales del proxy

Se agrega digest_ha1 a proxy_users: HA1 = MD5(usuario:realm:password),
calculado junto al htpasswd_hash existente en el unico momento en que el
backend tiene la contrasena en claro. El esquema activo (basic o digest) se
guarda como un squid_setting mas (proxy_auth_scheme), igual que auth_realm y
el resto de ajustes de autenticacion que ya viven ahi - no hace falta una
tabla nueva para un solo flag.

Revision ID: 0016
Revises: 0015
"""
from alembic import op
import sqlalchemy as sa

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("proxy_users", sa.Column("digest_ha1", sa.String(length=64), nullable=True))
    op.add_column("proxy_users", sa.Column("digest_ha1_realm", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("proxy_users", "digest_ha1_realm")
    op.drop_column("proxy_users", "digest_ha1")
