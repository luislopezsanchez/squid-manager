"""Modelo ParentProxy: salida a Internet a través de otro proxy.

En muchas empresas la salida directa está cerrada en el cortafuegos y todo el
tráfico tiene que pasar por el proxy corporativo. Sin esto, SquidManager no se
puede desplegar en esas redes.
"""

from app.utils import utcnow
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from app.database import Base


class ParentProxy(Base):
    __tablename__ = "parent_proxy"

    id = Column(Integer, primary_key=True, default=1)

    # Apagado por defecto: la mayoría de instalaciones salen directas.
    enabled = Column(Boolean, default=False, nullable=False)

    host = Column(String(255), nullable=True)
    port = Column(Integer, default=3128, nullable=False)

    # Credenciales opcionales. Muchos proxies internos no piden nada; los que
    # piden suelen usar autenticación básica, que es la única que Squid sabe
    # presentar a un padre.
    username = Column(String(255), nullable=True)
    password = Column(String(255), nullable=True)

    # Si el cortafuegos bloquea la salida directa —lo habitual cuando hay
    # proxy corporativo—, intentarla solo añade una espera antes de fallar.
    # Con esto activo, Squid no lo intenta: o pasa por el padre, o no pasa.
    never_direct = Column(Boolean, default=True, nullable=False)

    # Dominios y redes que NO deben pasar por el padre: la intranet, sobre
    # todo. Separados por espacios o saltos de línea.
    direct_domains = Column(Text, nullable=True)

    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)
