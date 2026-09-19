"""Modelo MonitoredNode: instancias remotas de SquidManager que este panel
consulta desde "Monitoreo centralizado" (ver docs/project-log.md, entrada
"Monitoreo centralizado de varias instancias").

No hay un mecanismo de token propio: se autentica contra cada nodo con el
login normal (POST /api/auth/login) usando una cuenta que ya exista ahí.
Se recomienda una cuenta con rol "viewer" (ver Admin.role) dedicada solo a
esto en cada nodo hijo, que solo puede leer -nunca aplicar cambios- si
llegara a filtrarse.
"""

from app.utils import utcnow
from app.crypto_service import EncryptedString
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from app.database import Base


class MonitoredNode(Base):
    __tablename__ = "monitored_nodes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    url = Column(String(255), nullable=False)  # http(s)://host:puerto, sin barra final
    username = Column(String(100), nullable=False)
    # Cifrada en reposo con DATA_KEY (ver crypto_service.py), mismo criterio
    # que el resto de credenciales de terceros del proyecto.
    password = Column(EncryptedString, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
