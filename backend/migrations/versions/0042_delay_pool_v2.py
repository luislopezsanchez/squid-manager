"""Reglas de ancho de banda con varios objetivos

Hasta ahora un delay pool apuntaba a UNA ACL y solo limitaba la descarga.
Las columnas nuevas permiten que una regla aplique a varios objetos (ACLs,
usuarios, grupos, tipos de tráfico).
Las reglas existentes (targets = NULL) siguen funcionando exactamente igual.

- targets:  JSON [{"kind": "acl|user|group|tipo|all", "value": "...", "acl": "<ACL resuelta>"}]
- acl_names: nombres de ACL resueltos, separados por espacio (para saber
             dónde se usa una ACL antes de borrarla)
- download_bps: bytes por segundo de descarga
- shared: True = el límite se reparte entre todo lo que cae en la regla;
          False = cada equipo tiene el suyo.

Revision ID: 0042
Revises: 0041
"""
from alembic import op
import sqlalchemy as sa

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("delay_pools", sa.Column("targets", sa.Text(), nullable=True))
    op.add_column("delay_pools", sa.Column("acl_names", sa.Text(), nullable=True))
    op.add_column("delay_pools", sa.Column("download_bps", sa.BigInteger(), nullable=True))
    op.add_column("delay_pools", sa.Column("shared", sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    for c in ("shared", "download_bps", "acl_names", "targets"):
        op.drop_column("delay_pools", c)
