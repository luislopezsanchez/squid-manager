"""ACLs por grupo de LDAP/Active Directory

Amplía UserGroup con un origen ('local', el único que existía hasta
ahora, o 'ldap') y los datos que necesita el segundo: el nombre del
grupo en el directorio, y si hay que contar membresía anidada (solo
Active Directory) o solo directa (cualquier LDAPv3). Nace en 'local'
para todo grupo existente -nada cambia de comportamiento para lo que ya
había.

Revision ID: 0031
Revises: 0030
"""
from alembic import op
import sqlalchemy as sa

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user_groups", sa.Column(
        "source", sa.String(length=10), nullable=False, server_default="local",
    ))
    op.add_column("user_groups", sa.Column("ldap_group_name", sa.String(length=255), nullable=True))
    op.add_column("user_groups", sa.Column(
        "ldap_group_nested", sa.Boolean(), nullable=False, server_default=sa.false(),
    ))


def downgrade() -> None:
    op.drop_column("user_groups", "ldap_group_nested")
    op.drop_column("user_groups", "ldap_group_name")
    op.drop_column("user_groups", "source")
