"""Desactiva store.log en instalaciones existentes

store.log registra cada objeto que entra y sale de la caché. No lo consume
ninguna parte de la aplicación y en un día de uso con un solo usuario ya
ocupaba más que el access.log. Las instalaciones anteriores lo tienen apuntando
a un fichero; aquí se pasa a 'none', que es el valor con el que se crean las
instalaciones nuevas.

Quien lo quiera de vuelta solo tiene que poner la ruta en Configuración.

Revision ID: 0003
Revises: 0002
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Solo se toca si conserva el valor por defecto: si alguien lo cambió a
    # propósito, se respeta su elección.
    op.execute(
        "UPDATE squid_settings SET value = 'none' "
        "WHERE key = 'cache_store_log' "
        "AND value IN ('/var/log/squid/store.log', 'stdio:/var/log/squid/store.log')"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE squid_settings SET value = '/var/log/squid/store.log' "
        "WHERE key = 'cache_store_log' AND value = 'none'"
    )
