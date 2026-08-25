"""Origenes de confianza exentos de autenticacion

Hace falta para poner SquidManager en cascada con otro proxy. Cuando un proxy
hijo reenvia trafico a este, la autenticacion de los usuarios finales ya la hizo
el hijo, y el padre no puede volver a pedirla: dentro de un tunel TLS
interceptado no hay forma de negociar un 407, asi que la peticion acaba
denegada con un 403 que no explica nada.

Se crea vacio: sin origenes, todo el mundo sigue teniendo que autenticarse,
que es el comportamiento de siempre.

Revision ID: 0010
Revises: 0009
"""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


# La columna description es varchar(255): el texto tiene que caber ahi.
AJUSTE = (
    "trusted_sources",
    "security",
    "IPs o redes que navegan SIN autenticarse (ej: 203.0.113.10 o "
    "203.0.113.0/24). Para un proxy hijo que ya autentica a sus usuarios. "
    "Vacio = todos deben autenticarse. Indica el origen concreto, nunca un "
    "rango amplio.",
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
            "VALUES (:k, '', :c, :d)"
        ),
        {"k": clave, "c": categoria, "d": descripcion},
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text("DELETE FROM squid_settings WHERE key = 'trusted_sources'")
    )
