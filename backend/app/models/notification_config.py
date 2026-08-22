"""Modelo NotificationConfig: configuración de notificaciones (email + Telegram)."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.database import Base


class NotificationConfig(Base):
    __tablename__ = "notification_config"

    id = Column(Integer, primary_key=True, default=1)
    # Email
    email_enabled = Column(Boolean, default=False, nullable=False)
    smtp_host = Column(String(255), nullable=True)
    smtp_port = Column(Integer, default=587, nullable=False)
    smtp_user = Column(String(255), nullable=True)
    smtp_password = Column(String(255), nullable=True)
    smtp_from = Column(String(255), nullable=True)
    smtp_encryption = Column(String(20), default="starttls", nullable=False)  # none, starttls, ssl
    email_recipients = Column(String(500), nullable=True)  # coma-separado

    # Telegram
    telegram_enabled = Column(Boolean, default=False, nullable=False)
    telegram_bot_token = Column(String(255), nullable=True)
    telegram_chat_id = Column(String(100), nullable=True)

    # Qué eventos notificar
    notify_on_apply = Column(Boolean, default=True, nullable=False)
    notify_on_user_change = Column(Boolean, default=False, nullable=False)
    notify_on_acl_change = Column(Boolean, default=False, nullable=False)
    notify_on_rule_change = Column(Boolean, default=False, nullable=False)
    notify_on_security_alert = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
