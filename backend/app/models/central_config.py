"""Modelo CentralMonitorConfig: interruptores del Monitoreo Centralizado en
ESTE servidor.

`enabled` es el interruptor maestro -tanto para actuar de "central"
(consultar nodos propios) como para dejarse consultar por otro SquidManager
que lo tenga a este como nodo. Apagado por defecto, mismo criterio que
LDAP/Kerberos/Syslog/IA: son llamadas salientes con credenciales guardadas
hacia otras máquinas (o, mirado al revés, un servidor que acepta ser
consultado por otro), y no toda instalación lo necesita. Apagarlo acá
también significa "no dejarse monitorear" -nada de esta sección responde,
ni siquiera a un padre.

`monitorizar_hijos` es un segundo interruptor, independiente: con `enabled`
prendido pero este apagado, el servidor SIGUE respondiendo cuando otro
SquidManager lo consulta como nodo (su `self` con sus propios datos), pero
deja de recorrer SUS PROPIOS nodos configurados al armar ese dashboard -su
`children` sale vacío para cualquiera que pregunte, sea su propio panel o
un padre. Resuelve el caso de un servidor que es hijo de otro pero no tiene
(o ya no quiere tener) hijos propios: antes había que elegir entre "no me
dejo monitorear" y "sigo monitoreando a mis nodos", con un único
interruptor todo-o-nada -encontrado en vivo, 2026-09-26. Prendido por
defecto: el comportamiento de HOY (antes de que existiera este campo) ya
recorría los nodos propios en cuanto `enabled` estaba prendido.
"""

import uuid

from app.utils import utcnow
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.database import Base


class CentralMonitorConfig(Base):
    __tablename__ = "central_monitor_config"

    id = Column(Integer, primary_key=True, default=1)
    enabled = Column(Boolean, default=False, nullable=False)
    monitorizar_hijos = Column(Boolean, default=True, nullable=False)
    # Generado una sola vez, a la primera lectura de esta config (ver
    # routes/central.py::_obtener_o_crear_config). Identifica a ESTE
    # servidor sin ambigüedad para quien lo monitoree, incluso si le cambian
    # el nombre o la URL después -no es secreto: viaja en la respuesta de
    # /api/central/dashboard para que el que arma el árbol pueda notar el
    # mismo servidor agregado dos veces con otro nombre.
    instance_id = Column(String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
