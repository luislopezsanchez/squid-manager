"""Cuotas de navegación por usuario del proxy

Amplía ProxyUser con una cuota de volumen opcional (bytes por periodo
diario/semanal/mensual) y la acción a tomar al agotarse: cortar la
navegación (deshabilitar al usuario, igual que el interruptor manual de
Gestión > Usuarios) o limitar la velocidad (delay pool automático, ver
migración 0029). Nace en NULL/0 para todo usuario existente -nadie queda
con una cuota activa sin que el admin la configure a propósito, mismo
criterio que LDAP/Kerberos/HaGeZi.

`quota_bytes_used` y `quota_period_started_at` son el estado que lleva el
hilo de fondo (quota_service.py) para saber cuánto lleva consumido el
usuario en el periodo actual y cuándo reiniciarlo; `quota_action_applied`
evita reaplicar la acción en cada vuelta del hilo una vez ya disparada.

Revision ID: 0028
Revises: 0027
"""
from alembic import op
import sqlalchemy as sa

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("proxy_users", sa.Column("quota_bytes", sa.BigInteger(), nullable=True))
    op.add_column("proxy_users", sa.Column("quota_period", sa.String(length=10), nullable=True))
    op.add_column("proxy_users", sa.Column("quota_action", sa.String(length=10), nullable=True))
    op.add_column("proxy_users", sa.Column("quota_throttle_bytes_per_sec", sa.Integer(), nullable=True))
    op.add_column("proxy_users", sa.Column(
        "quota_bytes_used", sa.BigInteger(), nullable=False, server_default="0",
    ))
    op.add_column("proxy_users", sa.Column("quota_period_started_at", sa.DateTime(), nullable=True))
    op.add_column("proxy_users", sa.Column(
        "quota_action_applied", sa.Boolean(), nullable=False, server_default=sa.false(),
    ))


def downgrade() -> None:
    op.drop_column("proxy_users", "quota_action_applied")
    op.drop_column("proxy_users", "quota_period_started_at")
    op.drop_column("proxy_users", "quota_bytes_used")
    op.drop_column("proxy_users", "quota_throttle_bytes_per_sec")
    op.drop_column("proxy_users", "quota_action")
    op.drop_column("proxy_users", "quota_period")
    op.drop_column("proxy_users", "quota_bytes")
