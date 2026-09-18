"""Kerberos: children/startup/idle configurables y pelar el realm del log

Hoy `auth_param negotiate children 10` está fijo en la plantilla, sin poder
ajustar `startup`/`idle` (sintaxis estándar de `auth_param`, ya usada para
basic/digest) ni pelar el `@REALM` del nombre de usuario que llega a
logs/cuotas (flag `-r` de `negotiate_kerberos_auth`, confirmado en su
manpage). Comparado contra SquidStats, que sí expone estos ajustes.

`children` nace en 10 (server_default) para que una instalación existente
no cambie de comportamiento al actualizar -es el mismo valor que estaba
fijo en la plantilla hasta ahora. `startup`/`idle` nacen NULL: sin definir,
la plantilla sigue escribiendo `children N` sin calificadores, igual que
antes. `strip_realm` nace en false: sin el flag `-r`, igual que hoy.

Revision ID: 0024
Revises: 0023
"""
from alembic import op
import sqlalchemy as sa

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("kerberos_config", sa.Column("children", sa.Integer(), nullable=False, server_default="10"))
    op.add_column("kerberos_config", sa.Column("startup", sa.Integer(), nullable=True))
    op.add_column("kerberos_config", sa.Column("idle", sa.Integer(), nullable=True))
    op.add_column("kerberos_config", sa.Column("strip_realm", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("kerberos_config", "strip_realm")
    op.drop_column("kerberos_config", "idle")
    op.drop_column("kerberos_config", "startup")
    op.drop_column("kerberos_config", "children")
