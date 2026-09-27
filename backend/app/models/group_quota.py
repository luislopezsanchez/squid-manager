"""Modelo GroupQuota: cuota de navegación compartida por un grupo LOCAL
entero (un "pool" único que consumen juntos todos sus miembros), a
diferencia de NavigationQuota (por usuario individual).

Solo grupos locales (UserGroup.source == 'local'): un grupo de LDAP no
tiene una lista de miembros que este backend pueda leer directo de la
base -se resuelve en vivo contra el directorio, por el propio Squid, vía
ldap_group_helper- así que no hay de dónde sumar "cuánto consumió cada
miembro" sin volver a consultar LDAP en cada tick. Ver quota_service.py.
"""

from app.utils import utcnow
from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Boolean
from app.database import Base


class GroupQuota(Base):
    __tablename__ = "group_quotas"

    id = Column(Integer, primary_key=True, index=True)
    group_name = Column(String(100), unique=True, nullable=False, index=True)
    quota_bytes = Column(BigInteger, nullable=False)
    quota_period = Column(String(10), nullable=False)  # 'daily' | 'weekly' | 'monthly'
    quota_action = Column(String(10), nullable=False, default="cut")  # 'cut' | 'throttle'
    quota_throttle_bytes_per_sec = Column(Integer, nullable=True)
    # Estado en vivo, actualizado por quota_service.py -no algo que se edite a mano.
    quota_bytes_used = Column(BigInteger, default=0, nullable=False)
    quota_period_started_at = Column(DateTime, nullable=True)
    quota_action_applied = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
