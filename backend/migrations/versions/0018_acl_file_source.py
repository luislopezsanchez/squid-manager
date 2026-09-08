"""ACLs respaldadas por archivo, para listas de dominios grandes

Hasta ahora una ACL siempre se escribe inline en squid.conf:
`acl nombre tipo valor1 valor2 ...` en una sola linea. Funciona bien para
una lista corta, pero una blocklist de miles de dominios (el caso de uso de
"cargar un archivo con dominios a bloquear") produciria una linea de
squid.conf de decenas de miles de caracteres -dificil de editar a mano,
mas lenta de parsear en cada reconfigure, y el valor ya no entra comodo en
un campo de texto del panel-.

source = 'inline' (por defecto, como hoy) o 'file': con 'file', el
contenido de `value` (los dominios, uno por linea logica) se escribe a un
archivo aparte en el volumen compartido con Squid, y squid.conf referencia
ese archivo (`acl nombre dstdomain "/etc/squid/acl_lists/nombre.txt"`) en
vez de listar los dominios inline. `value` en la BD sigue siendo la fuente
de verdad -se puede seguir editando, exportando en un backup, etc-; el
archivo es solo la forma en la que Squid lo lee cuando la lista es grande.

Revision ID: 0018
Revises: 0017
"""
from alembic import op
import sqlalchemy as sa

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "acls",
        sa.Column("source", sa.String(length=10), nullable=False, server_default="inline"),
    )


def downgrade() -> None:
    op.drop_column("acls", "source")
