"""Modelo Acl: Listas de Control de Acceso de Squid."""

from app.utils import utcnow
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from app.database import Base


class Acl(Base):
    __tablename__ = "acls"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    # Tipo de ACL: src, dst, dstdomain, url_regex, port, time, proxy_auth, etc.
    type = Column(String(50), nullable=False)
    # Valor/es de la ACL (puede ser IP, dominio, regex, etc.). Sigue siendo
    # la fuente de verdad aunque source='file': ver esa columna.
    value = Column(Text, nullable=False)
    # 'inline' (por defecto): el valor se escribe tal cual en squid.conf.
    # 'file': el valor se escribe a un archivo aparte (uno por línea) y
    # squid.conf referencia ese archivo -para listas grandes (miles de
    # dominios), donde una sola línea inline es impracticable de editar y
    # más lenta de parsear en cada reconfigure. Ver
    # squid_service.ACL_LISTS_DIR y build_acl_list_file().
    source = Column(String(10), nullable=False, default="inline")
    description = Column(String(255), nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)