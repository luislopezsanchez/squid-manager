"""Modelo Admin: administradores del panel web."""

from app.utils import utcnow
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from app.database import Base


class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    role = Column(String(50), default="admin", nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    last_login = Column(DateTime, nullable=True)
    # Momento del último cambio de contraseña. Los tokens emitidos antes de
    # esta marca se rechazan, de forma que cambiar la contraseña cierra las
    # sesiones abiertas en lugar de dejarlas vivas hasta que caduquen.
    password_changed_at = Column(DateTime, nullable=True, default=utcnow)
    # Obliga a cambiar la contraseña en el próximo inicio de sesión.
    must_change_password = Column(Boolean, default=False, nullable=False)
