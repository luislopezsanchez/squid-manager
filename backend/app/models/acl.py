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
    # Valor/es de la ACL (puede ser IP, dominio, regex, etc.). Fuente de
    # verdad SOLO cuando source='inline'. Para source='file' el archivo en
    # /etc/squid/acl_lists/ (ver squid_service.ACL_LISTS_DIR) es la fuente
    # de verdad y esta columna queda en NULL -guardar aquí también un
    # duplicado de una lista de millones de dominios es lo que hacía lenta
    # cualquier lectura de esta tabla (listar ACLs, generar squid.conf,
    # exportar un backup), no solo el propio archivo. Ver content_hash y
    # line_count, que sí se guardan para 'file'.
    value = Column(Text, nullable=True)
    # 'inline' (por defecto): el valor se escribe tal cual en squid.conf.
    # 'file': el valor se escribe a un archivo aparte (uno por línea) y
    # squid.conf referencia ese archivo -para listas grandes (miles de
    # dominios), donde una sola línea inline es impracticable de editar y
    # más lenta de parsear en cada reconfigure. Ver
    # squid_service.ACL_LISTS_DIR y build_acl_list_files().
    source = Column(String(10), nullable=False, default="inline")
    # Solo tienen sentido para source='file' (NULL en 'inline'): permiten
    # saber si el archivo en disco ya refleja lo último cargado sin tener
    # que releer ni comparar su contenido -content_hash es un sha256 de las
    # líneas ya normalizadas, en el mismo formato con el que se escribe el
    # archivo. line_count es solo para mostrar un conteo en el panel sin
    # tener que traer ni contar el contenido.
    content_hash = Column(String(64), nullable=True)
    line_count = Column(Integer, nullable=True)
    # Una "categoría" (Redes sociales, Streaming...) es, para Squid, una ACL
    # de dominios como cualquier otra -este flag es solo una capa de
    # identidad para que el panel la muestre en su propia pantalla y la
    # destaque al crear reglas/delay pools, sin duplicar el mecanismo de
    # carga de archivo ni la generación de squid.conf, que ya funcionan
    # igual para las dos. Solo tiene sentido con type in
    # ('dstdomain', 'dstdom_regex') -reforzado en la ruta, no aquí.
    is_category = Column(Boolean, default=False, nullable=False)
    description = Column(String(255), nullable=True)
    enabled = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)