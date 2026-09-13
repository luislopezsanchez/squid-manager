"""SMTP compartido: separar el servidor de correo de Notificaciones

`notification_config` mezclaba dos cosas distintas: el servidor SMTP en sí
(host/puerto/usuario/contraseña/cifrado) y cuándo/a quién mandar una alerta
de Squid (email_enabled, destinatarios, notify_on_*). Contacto (Ayuda >
Contacto) necesita el mismo relay de salida pero con un destinatario fijo
distinto al de las alertas -de ahí que el SMTP pase a vivir solo, en
`smtp_config`, y tanto Notificaciones como Contacto lo consulten.

Esta migración COPIA los valores ya configurados de notification_config a
smtp_config antes de borrar esas columnas: una instalación existente que ya
tenía SMTP configurado para alertas lo sigue teniendo tal cual después de
actualizar, sin volver a tipear nada -incluida la contraseña, que se copia
tal cual está en la columna (ya cifrada con DATA_KEY si la instalación es
posterior a la 0020, o en texto plano si es una instalación más vieja que
todavía no la había vuelto a guardar; EncryptedString sigue leyendo ambos
casos igual que antes).

Revision ID: 0022
Revises: 0021
"""
from alembic import op
import sqlalchemy as sa

revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "smtp_config",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("smtp_host", sa.String(length=255), nullable=True),
        sa.Column("smtp_port", sa.Integer(), nullable=False, server_default="587"),
        sa.Column("smtp_user", sa.String(length=255), nullable=True),
        sa.Column("smtp_password", sa.Text(), nullable=True),
        sa.Column("smtp_from", sa.String(length=255), nullable=True),
        sa.Column("smtp_encryption", sa.String(length=20), nullable=False, server_default="starttls"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    # Copia los valores ya configurados, si los hay -no pisa nada si
    # notification_config todavía no tiene fila (instalación nueva).
    op.execute("""
        INSERT INTO smtp_config (id, smtp_host, smtp_port, smtp_user, smtp_password,
                                  smtp_from, smtp_encryption, created_at, updated_at)
        SELECT 1, smtp_host, smtp_port, smtp_user, smtp_password,
               smtp_from, smtp_encryption, created_at, updated_at
        FROM notification_config WHERE id = 1
    """)

    with op.batch_alter_table("notification_config") as batch:
        batch.drop_column("smtp_host")
        batch.drop_column("smtp_port")
        batch.drop_column("smtp_user")
        batch.drop_column("smtp_password")
        batch.drop_column("smtp_from")
        batch.drop_column("smtp_encryption")


def downgrade() -> None:
    with op.batch_alter_table("notification_config") as batch:
        batch.add_column(sa.Column("smtp_host", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("smtp_port", sa.Integer(), nullable=False, server_default="587"))
        batch.add_column(sa.Column("smtp_user", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("smtp_password", sa.Text(), nullable=True))
        batch.add_column(sa.Column("smtp_from", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("smtp_encryption", sa.String(length=20), nullable=False, server_default="starttls"))

    op.execute("""
        UPDATE notification_config n SET
            smtp_host = s.smtp_host, smtp_port = s.smtp_port, smtp_user = s.smtp_user,
            smtp_password = s.smtp_password, smtp_from = s.smtp_from, smtp_encryption = s.smtp_encryption
        FROM smtp_config s WHERE n.id = 1 AND s.id = 1
    """)

    op.drop_table("smtp_config")
