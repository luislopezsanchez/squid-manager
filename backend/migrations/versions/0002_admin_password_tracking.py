"""Revocación de tokens al cambiar contraseña e integridad de los grupos

- admins.password_changed_at: permite invalidar los JWT emitidos antes del
  último cambio de contraseña.
- admins.must_change_password: fuerza el cambio en el primer inicio de sesión.
- user_group_members: clave foránea con ON DELETE CASCADE y unicidad de
  (grupo, usuario). Antes eran filas sueltas que sobrevivían al borrado del
  grupo y seguían apareciendo en el squid.conf generado.

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("admins", sa.Column("password_changed_at", sa.DateTime(), nullable=True))
    op.add_column(
        "admins",
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # Las cuentas existentes se marcan como cambiadas ahora, para no invalidar
    # de golpe las sesiones abiertas en el momento del despliegue.
    op.execute("UPDATE admins SET password_changed_at = NOW() WHERE password_changed_at IS NULL")

    # Limpiar miembros huérfanos antes de crear la clave foránea.
    op.execute(
        "DELETE FROM user_group_members m "
        "WHERE NOT EXISTS (SELECT 1 FROM user_groups g WHERE g.id = m.group_id)"
    )
    # Y los duplicados (grupo, usuario), conservando el más antiguo.
    op.execute(
        "DELETE FROM user_group_members a USING user_group_members b "
        "WHERE a.id > b.id AND a.group_id = b.group_id AND a.username = b.username"
    )

    op.create_unique_constraint(
        "uq_group_member", "user_group_members", ["group_id", "username"]
    )
    op.create_foreign_key(
        "fk_group_member_group",
        "user_group_members",
        "user_groups",
        ["group_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    op.drop_constraint("fk_group_member_group", "user_group_members", type_="foreignkey")
    op.drop_constraint("uq_group_member", "user_group_members", type_="unique")
    op.drop_column("admins", "must_change_password")
    op.drop_column("admins", "password_changed_at")
