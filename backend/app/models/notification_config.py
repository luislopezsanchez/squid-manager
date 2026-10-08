"""Modelo NotificationConfig: configuración de notificaciones (email + Telegram + XMPP)."""

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

    # XMPP: SquidManager solo es CLIENTE de un servidor de mensajería que la
    # empresa ya tiene; el admin indica host, puerto, cuenta (JID) y clave.
    xmpp_enabled = Column(Boolean, default=False, nullable=False)
    xmpp_host = Column(String(255), nullable=True)
    xmpp_port = Column(Integer, default=5222, nullable=False)
    xmpp_jid = Column(String(255), nullable=True)  # cuenta emisora, ej. squid@empresa.local
    xmpp_password = Column(EncryptedString, nullable=True)
    xmpp_encryption = Column(String(20), default="starttls", nullable=False)  # none, starttls, ssl
    xmpp_verify_cert = Column(Boolean, default=True, nullable=False)
    xmpp_recipients = Column(String(500), nullable=True)  # JIDs coma-separados
    xmpp_room = Column(String(255), nullable=True)  # sala (MUC) opcional, ej. avisos@conference.empresa.local

    # Qué eventos notificar
    notify_on_apply = Column(Boolean, default=True, nullable=False)
    notify_on_user_change = Column(Boolean, default=False, nullable=False)
    notify_on_acl_change = Column(Boolean, default=False, nullable=False)
    notify_on_rule_change = Column(Boolean, default=False, nullable=False)
    notify_on_security_alert = Column(Boolean, default=True, nullable=False)
    # Un nodo de Monitoreo Centralizado (ver MonitoredNode) que deja de
    # responder, o cuyo Squid deja de responder aunque el panel siga
    # arriba -ver node_alert_service.py. Mismo criterio de default que
    # notify_on_security_alert: es una condición detectada sola, no una
    # acción deliberada de un admin (a diferencia de apply/user_change/etc).
    notify_on_node_down = Column(Boolean, default=True, nullable=False)
    # Un usuario (o grupo) agotó su cuota de navegación.
    notify_on_quota_reached = Column(Boolean, default=True, nullable=False)
    # Un usuario insiste contra las reglas de denegación (blocked_threshold
    # peticiones bloqueadas en 10 minutos).
    notify_on_blocked_access = Column(Boolean, default=False, nullable=False)
    blocked_threshold = Column(Integer, default=10, nullable=False)
    # Reporte diario por correo a los administradores con email.
    daily_report_enabled = Column(Boolean, default=False, nullable=False)
    daily_report_time = Column(String(5), default="23:55", nullable=False)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
