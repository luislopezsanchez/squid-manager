"""Schemas de reglas de acceso (http_access)."""

from datetime import datetime
from pydantic import BaseModel, Field


class AccessRuleCreate(BaseModel):
    action: str = Field(..., pattern="^(allow|deny)$")
    acl_names: str = Field(..., min_length=1)
    order: int = 0
    description: str | None = None
    enabled: bool = True


class AccessRuleUpdate(BaseModel):
    action: str | None = Field(None, pattern="^(allow|deny)$")
    acl_names: str | None = None
    order: int | None = None
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