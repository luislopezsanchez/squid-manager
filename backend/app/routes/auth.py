"""Rutas de autenticación del admin."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.admin import Admin
from app.schemas.auth import Token, AdminResponse
from app.services.auth_service import (
    authenticate_admin, create_access_token, get_current_admin,
)

router = APIRouter()


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """Login del administrador. Devuelve un JWT."""
    admin = authenticate_admin(db, form_data.username, form_data.password)
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Actualizar last_login
    admin.last_login = datetime.now(timezone.utc)
    db.commit()

    token = create_access_token({"sub": admin.username})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=AdminResponse)
async def get_me(current_admin: Admin = Depends(get_current_admin)):
    """Información del admin autenticado."""
    return current_admin