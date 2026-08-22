"""Modelo DelayPool: control de ancho de banda (delay pools de Squid)."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from app.database import Base


class DelayPool(Base):
    __tablename__ = "delay_pools"

    id = Column(Integer, primary_key=True, index=True)
    # Clase 1-5
    pool_class = Column(Integer, nullable=False)
    # Parámetros en formato Squid: "rate/limit" o "rate/limit rate/limit"
    parameters = Column(Text, nullable=False)
    # ACL asociada a este pool
    acl_name = Column(String(100), nullable=True)
    description = Column(String(255), nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)