"""Módulos opcionales del panel (activar/desactivar desde Sistema → Módulos)

Un módulo apagado desaparece del menú y de las rutas del panel; no borra
datos ni detiene el registro de actividad (los agregados del access.log se
siguen calculando), solo deja de mostrarse. Por defecto: Análisis y Asistente
encendidos, Panel Central apagado -es una función para quien administra
varios proxies, no para el resto-.

Para no romper instalaciones que ya usan el Panel Central, la migración lo
deja encendido si ya había nodos configurados o el monitoreo estaba activo.

Revision ID: 0043
Revises: 0042
"""
from alembic import op
import sqlalchemy as sa

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_modules",
        sa.Column("key", sa.String(50), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    usa_central = False
    if "monitored_nodes" in inspector.get_table_names():
        usa_central = conn.execute(sa.text("SELECT COUNT(*) FROM monitored_nodes")).scalar() > 0
    if not usa_central and "central_monitor_config" in inspector.get_table_names():
        try:
            usa_central = bool(conn.execute(sa.text("SELECT COALESCE(BOOL_OR(enabled), false) FROM central_monitor_config")).scalar())
        except Exception:
            usa_central = False
    if usa_central:
        conn.execute(sa.text("INSERT INTO app_modules (key, enabled, updated_at) VALUES ('panel_central', true, NOW())"))


def downgrade() -> None:
    op.drop_table("app_modules")
