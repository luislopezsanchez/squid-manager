"""Modelo SyslogConfig: reenvío opcional de logs de acceso a un syslog externo."""

from app.utils import utcnow
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.database import Base


class SyslogConfig(Base):
    __tablename__ = "syslog_config"

    id = Column(Integer, primary_key=True, default=1)
    # Apagado por defecto: es un canal opcional, no algo que se active solo.
    enabled = Column(Boolean, default=False, nullable=False)
    host = Column(String(255), nullable=True)
    port = Column(Integer, default=514, nullable=False)
    protocol = Column(String(10), default="udp", nullable=False)  # udp | tcp
    rfc_format = Column(String(20), default="rfc3164", nullable=False)  # rfc3164 | rfc5424
    facility = Column(String(20), default="local0", nullable=False)  # local0..local7, etc.
    # Cuerpo del mensaje: la linea nativa de Squid, o el mismo objeto JSON que
    # ya se usa en la exportacion NDJSON — mismo criterio, mismo codigo.
    log_format = Column(String(20), default="raw", nullable=False)  # raw | ndjson
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
