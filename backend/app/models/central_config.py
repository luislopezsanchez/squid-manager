"""Modelo CentralMonitorConfig: interruptor del Monitoreo Centralizado en
ESTE servidor -tanto para actuar de "central" (consultar nodos propios) como
para dejarse consultar por otro SquidManager que lo tenga a este como nodo.

Apagado por defecto, mismo criterio que LDAP/Kerberos/Syslog/IA: son
llamadas salientes con credenciales guardadas hacia otras máquinas (o,
mirado al revés, un servidor que acepta ser consultado por otro), y no toda
instalación lo necesita.
"""

import uuid

from app.utils import utcnow
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.database import Base


class CentralMonitorConfig(Base):
    __tablename__ = "central_monitor_config"

    id = Column(Integer, primary_key=True, default=1)
    enabled = Column(Boolean, default=False, nullable=False)
    # Generado una sola vez, a la primera lectura de esta config (ver
    # routes/central.py::_obtener_o_crear_config). Identifica a ESTE
    # servidor sin ambigüedad para quien lo monitoree, incluso si le cambian
    # el nombre o la URL después -no es secreto: viaja en la respuesta de
    # /api/central/dashboard para que el que arma el árbol pueda notar el
    # mismo servidor agregado dos veces con otro nombre.
    instance_id = Column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
