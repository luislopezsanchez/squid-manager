"""Modelo SquidSetting: configuración general de Squid (key-value)."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text
from app.database import Base


class SquidSetting(Base):
    __tablename__ = "squid_settings"

    id = Column(Integer, primary_key=True, index=True)
    # Clave de configuración: http_port, cache_mem, cache_dir, etc.
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=False)
    # Categoría: network, cache, logging, security, etc.
    category = Column(String(50), default="general", nullable=False)
    description = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)