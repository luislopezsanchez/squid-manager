"""Ensanchar a TEXT las columnas que ahora se cifran en reposo

Un token Fernet agrega ~57 bytes de overhead (IV, timestamp, HMAC) mas la
expansion de base64 (~33%) sobre el texto plano -ver app/services/
crypto_service.py-. Con las columnas VARCHAR(255)/VARCHAR(500) originales,
guardar una credencial ya larga (una API key, la contraseña de un servicio)
podia superar el limite despues de cifrarse y Postgres rechazaba el
INSERT/UPDATE entero. Se ensanchan a TEXT (sin tope) para que el cifrado no
introduzca ese limite nuevo (auditoria 2026-09-09, hallazgo 05-003).

No hace falta backfill de datos: el propio tipo (EncryptedString) hace
migracion de doble lectura -un valor existente sin cifrar se sigue leyendo
como texto plano hasta que se vuelve a guardar, momento en que se cifra-.

Revision ID: 0020
Revises: 0019
"""
from alembic import op
import sqlalchemy as sa

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None

_COLUMNAS = [
    ("ldap_config", "bind_password", sa.String(255)),
    ("notification_config", "smtp_password", sa.String(255)),
    ("notification_config", "telegram_bot_token", sa.String(255)),
    ("ai_config", "api_key", sa.String(500)),
    ("ai_config", "embedding_api_key", sa.String(500)),
    ("parent_proxy", "password", sa.String(255)),
]


def upgrade() -> None:
    for tabla, columna, _tipo_original in _COLUMNAS:
        op.alter_column(tabla, columna, type_=sa.Text(), existing_nullable=True)


def downgrade() -> None:
    # Si algun valor ya cifrado supera el ancho original, esta migracion
    # hacia atras falla al truncar -es un riesgo aceptado y documentado de
    # volver atras despues de haber cifrado datos, igual que la nota general
    # sobre migraciones en docs/actualizacion.md: hacer un backup antes.
    for tabla, columna, tipo_original in _COLUMNAS:
        op.alter_column(tabla, columna, type_=tipo_original, existing_nullable=True)
