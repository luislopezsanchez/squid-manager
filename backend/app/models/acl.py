"""Modelo Acl: Listas de Control de Acceso de Squid."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from app.database import Base


class Acl(Base):
    __tablename__ = "acls"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    # Tipo de ACL: src, dst, dstdomain, url_regex, port, time, proxy_auth, etc.
    type = Column(String(50), nullable=False)
    # Valor/es de la ACL (puede ser IP, dominio, regex, etc.)
    value = Column(Text, nullable=False)
    description = Column(String(255), nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)