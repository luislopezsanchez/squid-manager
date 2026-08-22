"""Modelo AccessRule: reglas http_access de Squid."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from app.database import Base


class AccessRule(Base):
    __tablename__ = "access_rules"

    id = Column(Integer, primary_key=True, index=True)
    # allow o deny
    action = Column(String(10), nullable=False)  # allow | deny
    # Lista de nombres de ACL que componen la regla (separados por coma)
    # Ej: "localnet,authenticated"
    acl_names = Column(Text, nullable=False)
    # Orden de evaluación (más bajo = se evalúa primero)
    order = Column(Integer, nullable=False, default=0)
    description = Column(String(255), nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)