"""Rutas de gestión de administradores (solo superadmin)."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.database import get_db
from app.models.admin import Admin
from app.models.audit_log import AuditLog
from app.services.auth_service import (
    get_current_admin, get_password_hash, require_superadmin, verify_password,
)
from app.utils import utcnow

router = APIRouter()

VALID_ROLES = ("superadmin", "admin", "viewer")
MIN_PASSWORD_LENGTH = 10


class AdminCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=MIN_PASSWORD_LENGTH, max_length=128)
    email: str | None = None
    role: str = "admin"  # superadmin, admin, viewer


class AdminUpdate(BaseModel):
    email: str | None = None
    role: str | None = None
    is_active: bool | None = None


class AdminResponse(BaseModel):
    id: int
    username: str
    email: str | None
    role: str
    is_active: bool
    created_at: datetime
    last_login: datetime | None
    must_change_password: bool = False

    class Config:
        from_attributes = True


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=MIN_PASSWORD_LENGTH, max_length=128)


def _audit(db: Session, actor: Admin, action: str, target: Admin | None,
           old_value: str | None = None, new_value: str | None = None):
    """Registra los cambios sobre cuentas de administrador.

    Antes no se auditaba ninguno: en una herramienta de control de accesos, la
    escalada de privilegios es precisamente lo que hay que poder reconstruir.
    """
    db.add(AuditLog(
        admin_id=actor.id,
        admin_username=actor.username,
        action=action,
        entity="admin",
        entity_id=target.id if target else None,
        old_value=old_value,
        new_value=new_value,
    ))


@router.get("/", response_model=list[AdminResponse])
async def list_admins(
    db: Session = Depends(get_db),
    _: Admin = Depends(require_superadmin),
):
    """Listar todos los administradores (solo superadmin)."""
    return db.query(Admin).order_by(Admin.id).all()


@router.post("/", response_model=AdminResponse)
async def create_admin(
    data: AdminCreate,
    db: Session = Depends(get_db),
    current: Admin = Depends(require_superadmin),
):
    """Crear un nuevo administrador (solo superadmin)."""
    if db.query(Admin).filter(Admin.username == data.username).first():
        raise HTTPException(status_code=400, detail="El nombre de usuario ya existe")
    if data.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="Rol inválido. Debe ser: superadmin, admin o viewer")

    admin = Admin(
        username=data.username,
        password_hash=get_password_hash(data.password),
        email=data.email,
        role=data.role,
        is_active=True,
        password_changed_at=utcnow(),
        # Quien crea la cuenta conoce la contraseña: se pide cambiarla al entrar.
        must_change_password=True,
    )
    db.add(admin)
    db.flush()
    _audit(db, current, "create", admin, new_value=f"{admin.username} ({admin.role})")
    db.commit()
    db.refresh(admin)
    return admin


@router.put("/change-password")
async def change_password(
    data: PasswordChange,
    db: Session = Depends(get_db),
    current: Admin = Depends(get_current_admin),
):
    """Cambiar la propia contraseña (cualquier admin puede hacerlo)."""
    if not verify_password(data.current_password, current.password_hash):
        raise HTTPException(status_code=400, detail="Contraseña actual incorrecta")
    if data.new_password == data.current_password:
        raise HTTPException(status_code=400, detail="La contraseña nueva debe ser distinta de la actual")

    current.password_hash = get_password_hash(data.new_password)
    # Invalida los tokens emitidos antes de este momento, incluido cualquiera
    # que se hubiera filtrado.
    current.password_changed_at = utcnow()
    current.must_change_password = False
    _audit(db, current, "change_password", current)
    db.commit()
    return {
        "status": "ok",
        "message": "Contraseña cambiada. Vuelve a iniciar sesión.",
        "reauth_required": True,
    }


@router.put("/{admin_id}", response_model=AdminResponse)
async def update_admin(
    admin_id: int,
    data: AdminUpdate,
    db: Session = Depends(get_db),
    current: Admin = Depends(require_superadmin),
):
    """Actualizar un administrador (solo superadmin)."""
    admin = db.query(Admin).filter(Admin.id == admin_id).first()
    if not admin:
        raise HTTPException(status_code=404, detail="Administrador no encontrado")

    if data.role is not None and data.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="Rol inválido. Debe ser: superadmin, admin o viewer")

    # El superadmin por defecto (id=1) no puede ser degradado ni desactivado
    if admin.id == 1:
        if data.role is not None and data.role != "superadmin":
            raise HTTPException(status_code=400, detail="El superadmin principal no puede ser degradado")
        if data.is_active is not None and not data.is_active:
            raise HTTPException(status_code=400, detail="El superadmin principal no puede ser desactivado")

    # Quitarse a uno mismo el rol de superadmin deja la instalación sin quien
    # gestione administradores.
    if admin.id == current.id and data.role is not None and data.role != "superadmin":
        raise HTTPException(status_code=400, detail="No puedes cambiar tu propio rol de superadmin")

    old_value = f"{admin.username} rol={admin.role} activo={admin.is_active}"

    if data.email is not None:
        admin.email = data.email
    if data.role is not None:
        admin.role = data.role
    if data.is_active is not None:
        admin.is_active = data.is_active

    _audit(db, current, "update", admin, old_value=old_value,
           new_value=f"{admin.username} rol={admin.role} activo={admin.is_active}")
    db.commit()
    db.refresh(admin)
    return admin


@router.delete("/{admin_id}")
async def delete_admin(
    admin_id: int,
    db: Session = Depends(get_db),
    current: Admin = Depends(require_superadmin),
):
    """Eliminar un administrador (solo superadmin)."""
    if admin_id == 1:
        raise HTTPException(status_code=400, detail="El superadmin principal no puede ser eliminado")
    if admin_id == current.id:
        raise HTTPException(status_code=400, detail="No puedes eliminar tu propia cuenta")

    admin = db.query(Admin).filter(Admin.id == admin_id).first()
    if not admin:
        raise HTTPException(status_code=404, detail="Administrador no encontrado")

    username = admin.username
    _audit(db, current, "delete", admin, old_value=f"{username} ({admin.role})")
    db.delete(admin)
    db.commit()
    return {"status": "ok", "message": f"Administrador '{username}' eliminado"}
