"""Modelo ProxyUser: usuarios del proxy Squid (autenticación local)."""

from app.utils import utcnow
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from app.database import Base


class ProxyUser(Base):
    __tablename__ = "proxy_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    # Hash bcrypt para validación interna (API)
    password_hash = Column(String(255), nullable=False)
    # Hash htpasswd para Squid basic_ncsa_auth
    htpasswd_hash = Column(String(255), nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)