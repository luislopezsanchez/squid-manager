"""Mueve la cuota de navegación a su propia tabla, por nombre de usuario

Antes vivía como columnas de `proxy_users`, lo que dejaba a los usuarios
LDAP sin ninguna forma de tener cuota (no tienen fila en esa tabla). Se
migran los datos existentes (si hay alguno) a la tabla nueva y se borran
las columnas viejas. También se retarget-ea `delay_pools.quota_user_id`
(que apuntaba a `proxy_users.id`) a la nueva tabla, con el nombre
`quota_id` -los pools que gestiona quota_service.py son estado
regenerable, no datos reales del admin, así que se borran en vez de
intentar remapearlos: si la cuota sigue agotada, el propio hilo de fondo
los vuelve a crear en su próxima vuelta.

Revision ID: 0030
Revises: 0029
"""
from alembic import op
import sqlalchemy as sa

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "navigation_quotas",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("username", sa.String(length=100), nullable=False, unique=True, index=True),
        sa.Column("quota_bytes", sa.BigInteger(), nullable=False),
        sa.Column("quota_period", sa.String(length=10), nullable=False),
        sa.Column("quota_action", sa.String(length=10), nullable=False, server_default="cut"),
        sa.Column("quota_throttle_bytes_per_sec", sa.Integer(), nullable=True),
        sa.Column("quota_bytes_used", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("quota_period_started_at", sa.DateTime(), nullable=True),
        sa.Column("quota_action_applied", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    # Migra cualquier cuota que ya estuviera configurada.
    op.execute("""
        INSERT INTO navigation_quotas (
            username, quota_bytes, quota_period, quota_action,
            quota_throttle_bytes_per_sec, quota_bytes_used,
            quota_period_started_at, quota_action_applied,
            created_at, updated_at
        )
        SELECT
            username, quota_bytes, quota_period, COALESCE(quota_action, 'cut'),
            quota_throttle_bytes_per_sec, COALESCE(quota_bytes_used, 0),
            quota_period_started_at, COALESCE(quota_action_applied, false),
            now(), now()
        FROM proxy_users
        WHERE quota_bytes IS NOT NULL
    """)

    # Los delay pools que gestiona quota_service.py son estado regenerable
    # (ver docstring del módulo); se borran antes de retargetear la columna
    # en vez de remapearlos.
    op.execute("DELETE FROM delay_pools WHERE quota_user_id IS NOT NULL")
    op.drop_column("delay_pools", "quota_user_id")
    op.add_column("delay_pools", sa.Column(
        "quota_id", sa.Integer(),
        sa.ForeignKey("navigation_quotas.id", ondelete="CASCADE"),
        nullable=True, unique=True,
    ))

    op.drop_column("proxy_users", "quota_action_applied")
    op.drop_column("proxy_users", "quota_period_started_at")
    op.drop_column("proxy_users", "quota_bytes_used")
    op.drop_column("proxy_users", "quota_throttle_bytes_per_sec")
    op.drop_column("proxy_users", "quota_action")
    op.drop_column("proxy_users", "quota_period")
    op.drop_column("proxy_users", "quota_bytes")


def downgrade() -> None:
    op.add_column("proxy_users", sa.Column("quota_bytes", sa.BigInteger(), nullable=True))
    op.add_column("proxy_users", sa.Column("quota_period", sa.String(length=10), nullable=True))
    op.add_column("proxy_users", sa.Column("quota_action", sa.String(length=10), nullable=True))
    op.add_column("proxy_users", sa.Column("quota_throttle_bytes_per_sec", sa.Integer(), nullable=True))
    op.add_column("proxy_users", sa.Column("quota_bytes_used", sa.BigInteger(), nullable=False, server_default="0"))
    op.add_column("proxy_users", sa.Column("quota_period_started_at", sa.DateTime(), nullable=True))
    op.add_column("proxy_users", sa.Column("quota_action_applied", sa.Boolean(), nullable=False, server_default=sa.false()))

    op.execute("""
        UPDATE proxy_users p SET
            quota_bytes = q.quota_bytes,
            quota_period = q.quota_period,
            quota_action = q.quota_action,
            quota_throttle_bytes_per_sec = q.quota_throttle_bytes_per_sec,
            quota_bytes_used = q.quota_bytes_used,
            quota_period_started_at = q.quota_period_started_at,
            quota_action_applied = q.quota_action_applied
        FROM navigation_quotas q
        WHERE q.username = p.username
    """)

    op.drop_column("delay_pools", "quota_id")
    op.add_column("delay_pools", sa.Column(
        "quota_user_id", sa.Integer(),
        sa.ForeignKey("proxy_users.id", ondelete="CASCADE"),
        nullable=True, unique=True,
    ))

    op.drop_table("navigation_quotas")
