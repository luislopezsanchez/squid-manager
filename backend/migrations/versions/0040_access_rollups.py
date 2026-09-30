"""Agregados por hora del access.log (rollups) para reportes rápidos

Hasta ahora cada consulta de Actividad de red / Latencia / Errores /
Panorama releía y parseaba el access.log (y los rotados) entero para
ventanas de 24h, 7d o 30d: segundos por petición, y proporcional al tráfico.
Estas tablas guardan el resultado ya agregado por hora, que un hilo de
fondo (services/rollup_service.py) mantiene al día leyendo solo las líneas
nuevas. Las consultas pasan a ser SELECT ... GROUP BY sobre pocas filas.

Revision ID: 0040
Revises: 0039
"""
from alembic import op
import sqlalchemy as sa

revision = "0040"
down_revision = "0039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    big = sa.BigInteger()
    op.create_table(
        "ru_total",
        sa.Column("h", big, primary_key=True),
        sa.Column("requests", big, nullable=False, server_default="0"),
        sa.Column("bytes", big, nullable=False, server_default="0"),
        sa.Column("denied", big, nullable=False, server_default="0"),
        sa.Column("errors", big, nullable=False, server_default="0"),
        sa.Column("hits", big, nullable=False, server_default="0"),
        sa.Column("misses", big, nullable=False, server_default="0"),
        sa.Column("bytes_hit", big, nullable=False, server_default="0"),
        sa.Column("lat_sum", big, nullable=False, server_default="0"),
        sa.Column("lat_n", big, nullable=False, server_default="0"),
    )
    op.create_table(
        "ru_lat",
        sa.Column("h", big, primary_key=True),
        sa.Column("b", sa.SmallInteger(), primary_key=True),
        sa.Column("n", big, nullable=False, server_default="0"),
    )
    op.create_table(
        "ru_status",
        sa.Column("h", big, primary_key=True),
        sa.Column("status", sa.SmallInteger(), primary_key=True),
        sa.Column("n", big, nullable=False, server_default="0"),
    )
    op.create_table(
        "ru_user",
        sa.Column("h", big, primary_key=True),
        sa.Column("username", sa.String(255), primary_key=True),
        sa.Column("requests", big, nullable=False, server_default="0"),
        sa.Column("bytes", big, nullable=False, server_default="0"),
        sa.Column("denied", big, nullable=False, server_default="0"),
    )
    op.create_table(
        "ru_domain",
        sa.Column("h", big, primary_key=True),
        sa.Column("domain", sa.String(255), primary_key=True),
        sa.Column("requests", big, nullable=False, server_default="0"),
        sa.Column("bytes", big, nullable=False, server_default="0"),
        sa.Column("denied", big, nullable=False, server_default="0"),
        sa.Column("denied_bytes", big, nullable=False, server_default="0"),
        sa.Column("errors", big, nullable=False, server_default="0"),
        sa.Column("lat_sum", big, nullable=False, server_default="0"),
        sa.Column("lat_n", big, nullable=False, server_default="0"),
    )
    op.create_table(
        "ru_ipuser",
        sa.Column("h", big, primary_key=True),
        sa.Column("ip", sa.String(64), primary_key=True),
        sa.Column("username", sa.String(255), primary_key=True),
        sa.Column("requests", big, nullable=False, server_default="0"),
    )
    op.create_table(
        "ru_state",
        sa.Column("k", sa.String(255), primary_key=True),
        sa.Column("v", sa.Text(), nullable=False),
    )
    # Búsquedas por dominio / usuario a lo largo de las horas (Tendencias).
    op.create_index("ix_ru_domain_domain_h", "ru_domain", ["domain", "h"])
    op.create_index("ix_ru_user_username_h", "ru_user", ["username", "h"])


def downgrade() -> None:
    for t in ("ru_ipuser", "ru_domain", "ru_user", "ru_status", "ru_lat", "ru_total", "ru_state"):
        op.drop_table(t)
