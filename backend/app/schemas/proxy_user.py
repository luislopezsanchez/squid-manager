"""Schemas de usuarios del proxy."""

from datetime import datetime
from pydantic import BaseModel, Field


class ProxyUserCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=4, max_length=100)
    enabled: bool = True
    expires_at: datetime | None = None


class ProxyUserUpdate(BaseModel):
    password: str | None = Field(None, min_length=4, max_length=100)
    enabled: bool | None = None
    expires_at: datetime | None = None


class ProxyUserResponse(BaseModel):
    id: int
    username: str
    enabled: bool
    expires_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True