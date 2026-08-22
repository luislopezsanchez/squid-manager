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
    value: str
    description: str | None = None
    enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True