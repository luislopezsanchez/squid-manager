"""Modelo LdapConfig: configuración LDAP/Active Directory."""

from app.utils import utcnow
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from app.database import Base


class LdapConfig(Base):
    __tablename__ = "ldap_config"

    id = Column(Integer, primary_key=True, default=1)
    server_url = Column(String(255), nullable=False)  # ldap://host:389
    bind_dn = Column(String(255), nullable=False)     # cn=admin,dc=...
    bind_password = Column(String(255), nullable=False)
    search_base = Column(String(255), nullable=False)  # ou=users,dc=...
    user_filter = Column(String(255), nullable=False, default="(uid=%s)")
    # Filtro para "traer TODOS los usuarios" al sincronizar. Es distinto de
    # user_filter (que busca UNO por su nombre al hacer login): antes estaba
    # fijo en el codigo al filtro de Active Directory, y contra cualquier
    # otro directorio (OpenLDAP, FreeIPA...) no encontraba a nadie.
    sync_filter = Column(String(255), nullable=True, default="(&(objectCategory=person)(objectClass=user))")
    enabled = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)