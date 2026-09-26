"""Modelo MonitoredNode: instancias remotas que este panel consulta desde
"Monitoreo centralizado" (ver docs/project-log.md, entrada "Monitoreo
centralizado de varias instancias").

Dos tipos posibles (`tipo`):
- "squidmanager" (default): otra instancia de SquidManager. Se autentica
  con el login normal (POST /api/auth/login) usando una cuenta que ya
  exista ahí -se recomienda una cuenta con rol "viewer" (ver Admin.role)
  dedicada solo a esto, que solo puede leer- y de ahí en más se consulta
  su API (dashboard, árbol de sus propios nodos, etc). username/password
  obligatorios.
- "squid_basico": un Squid sin SquidManager encima, agregado a mano. No
  hay cuenta que validar ni API que consultar: se lee directo el Cache
  Manager de Squid (mgr:info) en HTTP plano contra `url` (que acá es
  host:puerto DEL PROPIO SQUID, no de un panel) -ver
  central_monitor_service.consultar_nodo_basico. username/password
  quedan en None; el árbol solo puede mostrar estado y uptime, nunca
  tráfico ni usuarios activos (eso sale de la base de datos de
  SquidManager, que un Squid puro no tiene). Requiere que el squid.conf
  remoto tenga una ACL que permita esta consulta desde este servidor
  -por defecto Squid solo la permite desde localhost.
"""

from app.utils import utcnow
from app.crypto_service import EncryptedString
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from app.database import Base


class MonitoredNode(Base):
    __tablename__ = "monitored_nodes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    tipo = Column(String(20), default="squidmanager", nullable=False)
    url = Column(String(255), nullable=False)  # http(s)://host:puerto, sin barra final
    username = Column(String(100), nullable=True)
    # Cifrada en reposo con DATA_KEY (ver crypto_service.py), mismo criterio
    # que el resto de credenciales de terceros del proyecto.
    password = Column(EncryptedString, nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
