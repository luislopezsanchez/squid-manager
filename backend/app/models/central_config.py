"""Modelo CentralMonitorConfig: interruptores del Monitoreo Centralizado en
ESTE servidor.

Los dos interruptores de acá solo controlan el lado SALIENTE -que ESTE
servidor use la función para ir a consultar a otros-, nunca el lado
ENTRANTE: que otro SquidManager consulte a este como nodo (GET
/api/central/dashboard) SIEMPRE responde con solo tener una cuenta válida
acá, sin importar cómo estén estos dos campos. "Dejarse monitorear" nunca
debería depender de un interruptor propio -alcanza con las credenciales
que el padre ya tiene guardadas, ni más ni menos que cualquier otro
endpoint de métricas del proyecto. Confusión real, reportada en vivo
2026-09-26: un admin apagaba `enabled` pensando "dejo de monitorear a mis
nodos" y de paso su propio padre lo veía "Sin conexión" (403), sin haber
tocado nada del lado del padre.

`enabled` es el interruptor maestro del lado saliente -listar/crear/editar/
borrar los nodos propios, probarlos, sincronizarles la config. Apagado por
defecto, mismo criterio que LDAP/Kerberos/Syslog/IA: son llamadas
salientes con credenciales guardadas hacia otras máquinas, y no toda
instalación lo necesita.

`monitorizar_hijos` es un segundo interruptor, independiente: con `enabled`
prendido pero este apagado (o con `enabled` apagado directamente), el
servidor SIGUE respondiendo `self` a quien lo consulte como nodo, pero deja
de recorrer sus propios nodos configurados al armar ese dashboard -su
`children` sale vacío para cualquiera que pregunte, sea su propio panel o
un padre. Resuelve el caso de un servidor que es hijo de otro pero no tiene
(o ya no quiere tener) hijos propios. Prendido por defecto: el
comportamiento de antes de que existiera este campo ya recorría los nodos
propios en cuanto `enabled` estaba prendido.
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
