"""Retira dns_v4_first: Squid 6 ya no soporta esa directiva

El ajuste se anadio en la 0006 para poder priorizar IPv4 en las resoluciones,
pero la directiva esta obsoleta desde Squid 5 y la 6 la rechaza al arrancar:

    ERROR: Directive 'dns_v4_first' is obsolete.
    Squid no longer supports preferential treatment of DNS A records.

Es decir, el ajuste no hacia nada: se guardaba, se escribia en el squid.conf y
Squid lo descartaba dejando un ERROR en su log. Se elimina para no ofrecer en
el panel una opcion que no surte efecto.

Quien necesite priorizar IPv4 hoy tiene que hacerlo por otra via (por ejemplo,
que el servidor DNS no devuelva registros AAAA, o desactivar IPv6 en el
contenedor), no desde este ajuste.

Revision ID: 0007
Revises: 0006
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.get_bind().execute(
        sa.text("DELETE FROM squid_settings WHERE key = 'dns_v4_first'")
    )


def downgrade() -> None:
    # Se vuelve a crear vacio para no reintroducir una directiva que Squid
    # rechaza: aunque exista la fila, con el valor vacio no se emite nada.
    conexion = op.get_bind()
    existe = conexion.execute(
        sa.text("SELECT 1 FROM squid_settings WHERE key = 'dns_v4_first'")
    ).first()
    if not existe:
        conexion.execute(sa.text(
            "INSERT INTO squid_settings (key, value, category, description) "
            "VALUES ('dns_v4_first', '', 'network', "
            "'Obsoleto: Squid 6 ya no soporta esta directiva.')"
        ))
