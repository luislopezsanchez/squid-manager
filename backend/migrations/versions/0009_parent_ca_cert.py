"""Certificado CA del proxy padre

Cuando el proxy padre tambien intercepta HTTPS —caso de otro SquidManager, o de
cualquier proxy corporativo con inspeccion TLS— presenta su propio certificado
al reenviar el trafico. Squid no lo conoce, lo rechaza por autofirmado y la
navegacion HTTPS falla entera:

    X509_V_ERR_SELF_SIGNED_CERT_IN_CHAIN

Guardando aqui el certificado del padre, el backend lo escribe en el volumen
compartido y el squid.conf lo declara con tls_outgoing_options cafile=, de modo
que Squid pasa a confiar en el.

Revision ID: 0009
Revises: 0008
"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("parent_proxy", sa.Column("ca_cert", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("parent_proxy", "ca_cert")
