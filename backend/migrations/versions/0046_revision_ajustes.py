"""Ajustes de la revisión: zona horaria, cuándo se excedió una cuota, avisos y reporte diario

- `app_settings`: pares clave/valor de la instalación (por ahora, la zona horaria).
- `quota_exceeded_at`: cuándo se agotó cada cuota (Actividad de red lo muestra).
- Notificaciones: avisar cuando un usuario llega a su cuota, cuando insiste en sitios
  bloqueados, y el reporte diario por correo.

Revision ID: 0046
Revises: 0045
"""
from alembic import op
import sqlalchemy as sa

revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("k", sa.String(100), primary_key=True),
        sa.Column("v", sa.Text(), nullable=False),
    )
    op.add_column("navigation_quotas", sa.Column("quota_exceeded_at", sa.DateTime(), nullable=True))
    op.add_column("group_quotas", sa.Column("quota_exceeded_at", sa.DateTime(), nullable=True))
    op.add_column("notification_config", sa.Column("notify_on_quota_reached", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("notification_config", sa.Column("notify_on_blocked_access", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("notification_config", sa.Column("blocked_threshold", sa.Integer(), nullable=False, server_default="10"))
    op.add_column("notification_config", sa.Column("daily_report_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("notification_config", sa.Column("daily_report_time", sa.String(5), nullable=False, server_default="23:55"))


def downgrade() -> None:
    for c in ("daily_report_time", "daily_report_enabled", "blocked_threshold", "notify_on_blocked_access", "notify_on_quota_reached"):
        op.drop_column("notification_config", c)
    op.drop_column("group_quotas", "quota_exceeded_at")
    op.drop_column("navigation_quotas", "quota_exceeded_at")
    op.drop_table("app_settings")
