"""Schemas de usuarios del proxy."""

from datetime import datetime
from pydantic import BaseModel, Field, field_validator

from app.services.auth_service import validar_largo_bcrypt


class ProxyUserCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=8, max_length=100)
    # Mismo campo que LdapUser.display_name -acá opcional y a mano, en vez
    # de sincronizado desde un directorio.
    display_name: str | None = Field(None, max_length=255)
    email: str | None = Field(None, max_length=255)
    enabled: bool = True
    expires_at: datetime | None = None

    _largo = field_validator("password")(validar_largo_bcrypt)


class ProxyUserUpdate(BaseModel):
    password: str | None = Field(None, min_length=8, max_length=100)
    display_name: str | None = Field(None, max_length=255)
    email: str | None = Field(None, max_length=255)
    enabled: bool | None = None
    expires_at: datetime | None = None

    _largo = field_validator("password")(validar_largo_bcrypt)


class ProxyUserResponse(BaseModel):
    id: int
    username: str
    display_name: str | None = None
    email: str | None = None
    enabled: bool
    expires_at: datetime | None = None
    # True si el usuario puede navegar ahora mismo: habilitado y sin caducar.
    # Un usuario habilitado con la fecha de caducidad pasada tiene
    # enabled=True y active=False.
    active: bool = True
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
