"""Modelo UserGroup: grupos de usuarios para aplicar políticas por grupo."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from app.database import Base


class UserGroup(Base):
    __tablename__ = "user_groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserGroupMember(Base):
    __tablename__ = "user_group_members"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, nullable=False, index=True)
    # username local o LDAP (sAMAccountName)
    username = Column(String(255), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
