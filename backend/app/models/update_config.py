"""Modelo UpdateConfig: comprobación de actualizaciones disponibles en el
repositorio de GitHub del proyecto.

Solo guarda la parte "de configuración" (¿está activada la comprobación
automática?, ¿cada cuánto?). El estado operativo -si hay una actualización
disponible, si hay una aprobada/programada, el resultado de la última
aplicada- vive en un archivo aparte (`.update_state.json`, dentro de
`backend/`, fuera de git), no en esta tabla: ese archivo lo necesita leer y
escribir un script que corre como root sin credenciales de Postgres, así
que no puede depender de la base de datos -ver
`app/services/update_service.py`-.
"""

from app.utils import utcnow
from sqlalchemy import Column, Integer, Boolean, DateTime
from app.database import Base


class UpdateConfig(Base):
    __tablename__ = "update_config"

    id = Column(Integer, primary_key=True, default=1)
    # A diferencia de LDAP/Kerberos/Asistente de IA, esto no envía ningún dato
    # propio a ningún lado: solo consulta el repositorio público del propio
    # proyecto en GitHub, sin credenciales. Por eso arranca activado, más
    # parecido a cómo un sistema operativo revisa actualizaciones por
    # defecto que a una integración con un tercero que sí requiere consentimiento
    # explícito.
    check_enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
