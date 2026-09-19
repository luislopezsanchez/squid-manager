"""Modelo DelayPool: control de ancho de banda (delay pools de Squid)."""

from app.utils import utcnow
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey
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
    # No NULL solo en el pool que quota_service.py crea solo cuando un
    # usuario agota su cuota con la acción "limitar velocidad" -identifica
    # ese pool como propio para poder borrarlo al reiniciar el periodo, sin
    # arriesgarse a tocar un pool creado a mano. Apunta a NavigationQuota
    # (no a ProxyUser: una cuota puede ser de un usuario LDAP, que no tiene
    # fila en proxy_users). Ver migración 0030.
    quota_id = Column(Integer, ForeignKey("navigation_quotas.id", ondelete="CASCADE"), nullable=True, unique=True)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)