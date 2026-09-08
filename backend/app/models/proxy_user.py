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
    # HA1 = MD5(usuario:realm:password) para Squid digest_file_auth. Se
    # calcula junto al htpasswd_hash de arriba, en el único momento en que el
    # backend tiene la contraseña en claro (al crearla o resetearla) - ver
    # routes/proxy_users.py:_generate_digest_ha1(). El realm queda "horneado"
    # dentro del hash: si se cambia auth_realm después, este HA1 queda
    # inválido para el realm nuevo. digest_ha1_realm guarda con qué realm se
    # calculó, para poder detectarlo y excluir esa línea al escribir el
    # archivo en vez de servir un HA1 que ya no sirve (ver
    # squid_service.write_digest_file).
    digest_ha1 = Column(String(64), nullable=True)
    digest_ha1_realm = Column(String(255), nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)