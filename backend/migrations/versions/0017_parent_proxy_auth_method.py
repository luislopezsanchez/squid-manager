"""Metodo de login hacia el proxy padre: fijo o passthru

Squid no tiene forma nativa de presentar credenciales Digest (ni NTLM/
Negotiate) propias a un cache_peer: la directiva login=user:pass de
cache_peer solo sabe hacer Basic (documentado en
https://www.squid-cache.org/Doc/config/cache_peer/). La unica forma de
llegar a un padre que exige Digest es reenviar tal cual las credenciales que
ya trae el cliente (login=PASSTHRU connection-auth=on), lo que exige que
este Squid NO autentique a sus propios clientes al mismo tiempo -HTTP solo
permite un Proxy-Authorization por peticion.

auth_method = 'fixed' (por defecto, como hoy: login=user:pass, solo Basic) o
'passthru' (login=PASSTHRU connection-auth=on, incompatible con auth local).

Revision ID: 0017
Revises: 0016
"""
from alembic import op
import sqlalchemy as sa

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "parent_proxy",
        sa.Column("auth_method", sa.String(length=20), nullable=False, server_default="fixed"),
    )


def downgrade() -> None:
    op.drop_column("parent_proxy", "auth_method")
