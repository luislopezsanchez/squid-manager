"""Rutas de autenticación del admin."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.admin import Admin
from app.models.audit_log import AuditLog
from app.middleware import login_attempts_exceeded, record_failed_login
from app.schemas.auth import Token, AdminResponse
from app.services.auth_service import (
    authenticate_admin, create_access_token, get_current_admin,
)
from app.utils import utcnow

router = APIRouter()


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """Login del administrador. Devuelve un JWT.

    El límite de intentos por cuenta se comprueba DESPUÉS de validar la
    contraseña, nunca antes: si se comprobara antes, cualquiera podría dejar
    sin acceso al admin real mandando unas pocas contraseñas mal escritas
    contra su usuario -sin acertar nunca ni moverse de IP-, porque el 429 le
    llegaría también a él en cuanto quisiera entrar de verdad. Una
    contraseña CORRECTA siempre se acepta, sin importar cuántos intentos
    fallidos previos tenga esa cuenta acumulados; el límite solo frena los
    intentos que YA son incorrectos, que es lo único que hace falta frenar.
    """
    admin = authenticate_admin(db, form_data.username, form_data.password)
    if not admin:
        # Ya perdió (contraseña incorrecta): recién ahora, si la cuenta venía
        # excedida, se devuelve 429 en vez del 401 normal.
        excedido = login_attempts_exceeded(form_data.username)
        record_failed_login(form_data.username)
        db.add(AuditLog(
            admin_id=None, admin_username=form_data.username,
            action="login_failed", entity="admin",
        ))
        db.commit()
        if excedido:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Demasiados intentos fallidos para esta cuenta. Espera un minuto.",
                headers={"Retry-After": "60"},
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    admin.last_login = utcnow()
    db.add(AuditLog(
        admin_id=admin.id, admin_username=admin.username,
        action="login", entity="admin", entity_id=admin.id,
    ))
    db.commit()

    token = create_access_token({"sub": admin.username})
    return {
        "access_token": token,
        "token_type": "bearer",
        "must_change_password": admin.must_change_password,
        "role": admin.role,
    }


@router.get("/me", response_model=AdminResponse)
async def get_me(current_admin: Admin = Depends(get_current_admin)):
    """Información del admin autenticado."""
    return current_admin
