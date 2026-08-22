"""Modelo LdapUser: usuarios sincronizados desde LDAP/Active Directory.

Estos usuarios NO se autentican con htpasswd local; se autentican contra LDAP.
La tabla sirve para gestionar la allow-list: solo los usuarios con `enabled=True`
pueden navegar (allow-list estricto).
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.database import Base


class LdapUser(Base):
    __tablename__ = "ldap_users"

    id = Column(Integer, primary_key=True, index=True)
    # sAMAccountName (o uid en OpenLDAP)
    username = Column(String(255), unique=True, nullable=False, index=True)
    display_name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)
    # allow-list estricto: por defecto NO navegan hasta que el admin los habilite
    enabled = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
