"""Filtro de sincronizacion LDAP configurable, no fijo a Active Directory

El filtro de busqueda que usa "Sincronizar" para traer TODOS los usuarios del
directorio estaba fijo en el codigo a (&(objectCategory=person)(objectClass=user)),
que es un atributo exclusivo de Active Directory. Contra OpenLDAP o cualquier
LDAPv3 generico, esa busqueda no devuelve nada -- sin error, solo "0 sincronizados".
El filtro de login (user_filter) ya era configurable; este completa la parte
que faltaba.

Se guarda el valor de AD como default explicito en la fila existente, para que
las instalaciones que ya dependian de ese comportamiento no cambien de golpe.

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

_AD_FILTER = "(&(objectCategory=person)(objectClass=user))"


def upgrade() -> None:
    op.add_column(
        "ldap_config",
        sa.Column("sync_filter", sa.String(length=255), nullable=True),
    )
    # Fila existente: se deja explicito el filtro que ya se estaba usando en
    # la practica, para no cambiar el comportamiento de instalaciones en marcha.
    op.execute(f"UPDATE ldap_config SET sync_filter = '{_AD_FILTER}'")


def downgrade() -> None:
    op.drop_column("ldap_config", "sync_filter")
