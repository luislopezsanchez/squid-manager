"""Autenticacion Negotiate (SPNEGO/Kerberos) contra Active Directory

Permite SSO transparente para clientes Windows unidos a un dominio: el
navegador presenta un ticket Kerberos y Squid lo valida contra un keytab, sin
pedir usuario ni contrasena. Convive con la autenticacion Basic que ya existe,
no la reemplaza.

La tabla se crea apagada (enabled=False): activarla sin un keytab valido no
rompe nada (Squid simplemente no ofrece Negotiate), pero conviene que sea un
paso explicito del admin, no un default sorpresa.

El .keytab lo genera el administrador de AD del cliente FUERA de SquidManager
(msktutil u equivalente, con sus propias credenciales de administrador de
dominio) y se sube ya generado, igual que el certificado CA del proxy padre.

Revision ID: 0013
Revises: 0012
"""
from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "kerberos_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("realm", sa.String(length=255), nullable=True),
        sa.Column("proxy_fqdn", sa.String(length=255), nullable=True),
        sa.Column("keytab_data", sa.LargeBinary(), nullable=True),
        sa.Column("keytab_filename", sa.String(length=255), nullable=True),
        sa.Column("keytab_uploaded_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("kerberos_config")
