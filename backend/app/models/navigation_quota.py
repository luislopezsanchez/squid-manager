"""Modelo NavigationQuota: cuota de navegación por nombre de usuario.

Vive en su propia tabla, separada de ProxyUser/LdapUser a propósito: una
cuota es, en esencia, "este nombre de usuario tiene un límite de datos",
sin importar si ese nombre corresponde a un usuario local o importado de
LDAP/Active Directory -antes vivía como columnas de ProxyUser, y eso
dejaba a los usuarios LDAP sin ninguna forma de tener cuota (no tienen
fila en esa tabla). quota_service.py resuelve en tiempo de aplicación
contra cuál de las dos tablas corresponde actuar (ver
_resolver_usuario en ese archivo).
"""

from app.utils import utcnow
from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Boolean
from app.database import Base


class NavigationQuota(Base):
    __tablename__ = "navigation_quotas"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
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
