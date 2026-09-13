"""Modelo SmtpConfig: servidor SMTP de salida, compartido por Notificaciones
(alertas de red) y Contacto (soporte del producto).

Antes vivía duplicado dentro de NotificationConfig -mezclaba "cómo mando
correo" con "cuándo/a quién mando una alerta de Squid", dos cosas distintas.
Se separa a pedido del usuario (2026-09-12) al agregar Contacto, que
necesitaba el mismo relay de salida pero un destinatario fijo distinto al
de las alertas. La migración 0022 copia los valores ya configurados de
notification_config antes de borrar esas columnas -ninguna instalación
existente pierde su SMTP ya configurado al actualizar.
"""

from app.utils import utcnow
from app.crypto_service import EncryptedString
from sqlalchemy import Column, Integer, String, DateTime
from app.database import Base


class SmtpConfig(Base):
    __tablename__ = "smtp_config"

    id = Column(Integer, primary_key=True, default=1)
    smtp_host = Column(String(255), nullable=True)
    smtp_port = Column(Integer, default=587, nullable=False)
    smtp_user = Column(String(255), nullable=True)
    # Cifrada en reposo con DATA_KEY (mismo criterio que antes en
    # NotificationConfig -ver crypto_service.py).
    smtp_password = Column(EncryptedString, nullable=True)
    smtp_from = Column(String(255), nullable=True)
    smtp_encryption = Column(String(20), default="starttls", nullable=False)  # none, starttls, ssl

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
