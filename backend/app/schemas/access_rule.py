"""Schemas de reglas de acceso (http_access)."""

from datetime import datetime
from pydantic import BaseModel, Field


class AccessRuleCreate(BaseModel):
    action: str = Field(..., pattern="^(allow|deny)$")
    acl_names: str = Field(..., min_length=1)
    # >= 0: el orden es una posición en una lista, no admite "antes del
    # principio". Insertar en una posición ya ocupada corre el resto hacia
    # abajo (ver create_access_rule/update_access_rule en access_rules.py),
    # así que nunca hace falta un valor negativo para "pasar primero".
    order: int = Field(0, ge=0)
    description: str | None = None
    enabled: bool = True


class AccessRuleUpdate(BaseModel):
    action: str | None = Field(None, pattern="^(allow|deny)$")
    acl_names: str | None = None
    order: int | None = Field(None, ge=0)
    description: str | None = None
    enabled: bool | None = None


class AccessRuleResponse(BaseModel):
    id: int
    action: str
    acl_names: str
    order: int
    description: str | None = None
    enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True