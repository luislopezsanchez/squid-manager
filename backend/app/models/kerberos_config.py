"""Modelo KerberosConfig: autenticación Negotiate (SPNEGO/Kerberos) contra AD.

Permite que los clientes Windows unidos a un dominio Active Directory naveguen
sin que se les pida usuario y contraseña (SSO transparente): el navegador
presenta un ticket Kerberos y Squid lo valida contra el keytab del proxy.

Convive con la autenticación Basic que ya existe — no la reemplaza. Los
clientes que no soportan Negotiate (móviles, Linux sin sesión de dominio,
invitados) siguen usando usuario/contraseña del panel como hasta ahora.
"""

from app.utils import utcnow
from app.crypto_service import EncryptedBinary
from sqlalchemy import Column, Integer, String, Boolean, DateTime
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
    # Cifrado en reposo con DATA_KEY (ver crypto_service.py -auditoria
    # 2026-09-09, hallazgo 05-003).
    keytab_data = Column(EncryptedBinary, nullable=True)
    keytab_filename = Column(String(255), nullable=True)
    keytab_uploaded_at = Column(DateTime, nullable=True)

    # Procesos del helper que Squid mantiene vivos para Negotiate. Antes
    # estaba fijo en 10 en la plantilla; el default acá es el mismo valor
    # para que una instalación existente no cambie de comportamiento al
    # actualizar.
    children = Column(Integer, default=10, nullable=False)
    # startup/idle son opcionales: si no se definen, `auth_param negotiate
    # children N` se escribe igual que hasta ahora, sin esos calificadores
    # (mismo comportamiento que Squid ya tenía por defecto).
    startup = Column(Integer, nullable=True)
    idle = Column(Integer, nullable=True)
    # Corresponde al flag `-r` de negotiate_kerberos_auth (confirmado en su
    # manpage): sin él, el usuario llega a logs/cuotas como `user@REALM`;
    # con él, solo `user`. Apagado por defecto -no cambia lo que ya hay.
    strip_realm = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
