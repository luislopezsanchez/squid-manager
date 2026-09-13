"""Modelo ContactMessage: mensajes enviados desde el formulario de Contacto.

Se guarda siempre en base, aunque el envío por email falle o no haya SMTP
configurado -para no perder el reporte de un error o una sugerencia solo
porque la instalación no tiene notificaciones configuradas.
"""

from app.utils import utcnow
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from app.database import Base


class ContactMessage(Base):
    __tablename__ = "contact_messages"

    id = Column(Integer, primary_key=True, index=True)
    admin_username = Column(String(100), nullable=False)
    categoria = Column(String(30), nullable=False)  # error | sugerencia | otro
    mensaje = Column(Text, nullable=False)
    email_respuesta = Column(String(255), nullable=True)
    enviado_por_email = Column(Boolean, default=False, nullable=False)
    detalle_envio = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=utcnow)
