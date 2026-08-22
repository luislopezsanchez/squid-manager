"""Schemas de autenticación."""

from pydantic import BaseModel


class AdminLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminResponse(BaseModel):
    id: int
    username: str
    email: str | None = None
    role: str

    class Config:
        from_attributes = True