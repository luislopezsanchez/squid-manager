"""Modelo NotificationConfig: configuración de notificaciones (email + Telegram)."""

from app.utils import utcnow
from app.crypto_service import EncryptedString
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.database import Base


class NotificationConfig(Base):
    __tablename__ = "notification_config"

    id = Column(Integer, primary_key=True, default=1)
    # Email: el "cómo" (servidor SMTP) vive en SmtpConfig, compartido con
    # Contacto -acá solo queda el "cuándo/a quién" de las alertas.
    email_enabled = Column(Boolean, default=False, nullable=False)
    email_recipients = Column(String(500), nullable=True)  # coma-separado

    # Telegram
    telegram_enabled = Column(Boolean, default=False, nullable=False)
    telegram_bot_token = Column(EncryptedString, nullable=True)
    telegram_chat_id = Column(String(100), nullable=True)

    # Qué eventos notificar
    notify_on_apply = Column(Boolean, default=True, nullable=False)
    notify_on_user_change = Column(Boolean, default=False, nullable=False)
    notify_on_acl_change = Column(Boolean, default=False, nullable=False)
    notify_on_rule_change = Column(Boolean, default=False, nullable=False)
    notify_on_security_alert = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
