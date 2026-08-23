"""Modelo UserGroup: grupos de usuarios para aplicar políticas por grupo."""

from app.utils import utcnow
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from app.database import Base


class UserGroup(Base):
    __tablename__ = "user_groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)


class UserGroupMember(Base):
    __tablename__ = "user_group_members"
    # Un usuario no puede estar dos veces en el mismo grupo.
    __table_args__ = (UniqueConstraint("group_id", "username", name="uq_group_member"),)

    id = Column(Integer, primary_key=True, index=True)
    # Borrar el grupo borra sus miembros: sin esto quedaban filas huérfanas
    # que seguían apareciendo en el squid.conf generado.
    group_id = Column(
        Integer,
        ForeignKey("user_groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # username local o LDAP (sAMAccountName)
    username = Column(String(255), nullable=False, index=True)
    created_at = Column(DateTime, default=utcnow)
