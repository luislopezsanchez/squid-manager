"""Schemas de ACLs."""

from datetime import datetime
from pydantic import BaseModel, Field


class AclCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    type: str = Field(..., min_length=1, max_length=50)
    value: str = Field(..., min_length=1)
    description: str | None = None
    enabled: bool = True


class AclUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    type: str | None = Field(None, min_length=1, max_length=50)
    value: str | None = None
    description: str | None = None
    enabled: bool | None = None


class AclResponse(BaseModel):
    id: int
    name: str
    type: str
    # NULL para una ACL 'file': su contenido vive únicamente en
    # /etc/squid/acl_lists/<name>.txt (ver migración 0023), no se manda por
    # la API -puede tener millones de líneas. El frontend usa `line_count`
    # para mostrar cuántos dominios tiene sin necesitar el contenido.
    value: str | None
    # 'inline' (se edita como cualquier ACL) o 'file' (viene de una carga
    # masiva de dominios; su valor no se edita a mano, se vuelve a subir el
    # archivo). Solo informativo para el frontend, no se acepta en
    # AclCreate/AclUpdate: una ACL 'file' se crea únicamente vía
    # /acls/bulk-domains.
    source: str = "inline"
    line_count: int | None = None
    description: str | None = None
    enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True