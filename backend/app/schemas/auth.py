"""Schemas de autenticación."""

from pydantic import BaseModel


class AdminLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    # El frontend usa estos dos campos para decidir qué mostrar: si hay que
    # forzar el cambio de contraseña y qué acciones habilitar según el rol.
    must_change_password: bool = False
    role: str = "admin"


class AdminResponse(BaseModel):
    id: int
    username: str
    email: str | None = None
    role: str
    must_change_password: bool = False

    class Config:
        from_attributes = True
