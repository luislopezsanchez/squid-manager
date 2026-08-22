"""Modelo AuditLog: registro de cambios para auditoría."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text
from app.database import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(Integer, nullable=True)
    admin_username = Column(String(100), nullable=True)
    action = Column(String(50), nullable=False)  # create, update, delete, apply
    entity = Column(String(50), nullable=False)   # proxy_user, acl, rule, etc.
    entity_id = Column(Integer, nullable=True)
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)