"""Modelo KerberosConfig: autenticación Negotiate (SPNEGO/Kerberos) contra AD.

Permite que los clientes Windows unidos a un dominio Active Directory naveguen
sin que se les pida usuario y contraseña (SSO transparente): el navegador
presenta un ticket Kerberos y Squid lo valida contra el keytab del proxy.

Convive con la autenticación Basic que ya existe — no la reemplaza. Los
clientes que no soportan Negotiate (móviles, Linux sin sesión de dominio,
invitados) siguen usando usuario/contraseña del panel como hasta ahora.
"""

from app.utils import utcnow
from sqlalchemy import Column, Integer, String, Boolean, DateTime, LargeBinary
from app.database import Base


class KerberosConfig(Base):
    __tablename__ = "kerberos_config"

    id = Column(Integer, primary_key=True, default=1)

    # Apagado por defecto: activar esto sin un keytab valido no rompe nada
    # (Squid simplemente no ofrece Negotiate), pero tampoco sirve de nada.
    enabled = Column(Boolean, default=False, nullable=False)

    # Realm en mayusculas, ej. EMPRESA.LOCAL. Va tal cual en el principal de
    # servicio que Squid presenta (-s HTTP/fqdn@REALM).
    realm = Column(String(255), nullable=True)

    # FQDN del proxy tal como lo resuelve el cliente Windows, ej.
    # proxy.empresa.local. Tiene que coincidir con el nombre que el cliente usa
    # para conectarse, o el ticket que presenta no sirve para este servicio.
    proxy_fqdn = Column(String(255), nullable=True)

    # El .keytab lo genera el administrador de AD del cliente con msktutil (o
    # equivalente) FUERA de SquidManager: crear la cuenta de equipo en el
    # directorio requiere credenciales de administrador de dominio, algo que
    # este panel no debe pedir ni manejar. Se sube ya generado, como el
    # certificado CA del proxy padre.
    keytab_data = Column(LargeBinary, nullable=True)
    keytab_filename = Column(String(255), nullable=True)
    keytab_uploaded_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
