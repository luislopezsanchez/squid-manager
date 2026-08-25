"""Poder desactivar la interceptacion de HTTPS

Squid solo puede interceptar HTTPS una vez en una cadena de proxies. Si un
SquidManager sale a traves de otro proxy que tambien intercepta, el de arriba
recibe la peticion descifrada dentro de un tunel que el mismo cifro y la
rechaza con un 403 que no explica nada. Comprobado encadenando dos
SquidManager: el CONNECT se aceptaba y la peticion de dentro se denegaba.

Con ssl_bump_enabled en false, Squid se limita a tunelizar el HTTPS (splice):
deja de poder filtrar por dominio dentro de HTTPS, pero el trafico pasa. Es lo
que hay que elegir en el proxy que NO va a filtrar: normalmente el de arriba,
porque el de abajo es el que aplica las politicas de sus usuarios.

Se crea en true, que es como se ha comportado hasta ahora.

Revision ID: 0011
Revises: 0010
"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


# description es varchar(255): el texto tiene que caber ahi.
AJUSTE = (
    "ssl_bump_enabled",
    "security",
    "true = interceptar HTTPS para poder filtrar por dominio. false = solo "
    "tunelizar. Ponlo en false si sales por otro proxy que ya intercepta: "
    "dos interceptaciones encadenadas rompen la navegacion HTTPS.",
)


def upgrade() -> None:
    conexion = op.get_bind()
    clave, categoria, descripcion = AJUSTE

    existe = conexion.execute(
        sa.text("SELECT 1 FROM squid_settings WHERE key = :k"), {"k": clave}
    ).first()
    if existe:
        return

    conexion.execute(
        sa.text(
            "INSERT INTO squid_settings (key, value, category, description) "
            "VALUES (:k, 'true', :c, :d)"
        ),
        {"k": clave, "c": categoria, "d": descripcion},
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text("DELETE FROM squid_settings WHERE key = 'ssl_bump_enabled'")
    )
