"""Rutas de gestión de administradores (solo superadmin)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from app.database import get_db
from app.models.admin import Admin
from app.services.auth_service import get_current_admin, get_password_hash

router = APIRouter()


class AdminCreate(BaseModel):
    username: str
    password: str
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

    class Config:
        from_attributes = True


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


def _require_superadmin(admin: Admin = Depends(get_current_admin)) -> Admin:
    """Dependencia que requiere rol superadmin."""
    if admin.role != "superadmin":
        raise HTTPException(status_code=403, detail="Solo el superadmin puede gestionar administradores")
    return admin


@router.get("/", response_model=list[AdminResponse])
async def list_admins(
    db: Session = Depends(get_db),
    _: Admin = Depends(_require_superadmin),
):
    """Listar todos los administradores (solo superadmin)."""
    return db.query(Admin).order_by(Admin.id).all()


@router.post("/", response_model=AdminResponse)
async def create_admin(
    data: AdminCreate,
    db: Session = Depends(get_db),
    _: Admin = Depends(_require_superadmin),
):
    """Crear un nuevo administrador (solo superadmin)."""
    if db.query(Admin).filter(Admin.username == data.username).first():
        raise HTTPException(status_code=400, detail="El nombre de usuario ya existe")
    if data.role not in ("superadmin", "admin", "viewer"):
        raise HTTPException(status_code=400, detail="Rol inválido. Debe ser: superadmin, admin o viewer")

    admin = Admin(
        username=data.username,
        password_hash=get_password_hash(data.password),
        email=data.email,
        role=data.role,
        is_active=True,
    )
    db.add(admin)
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
    from app.services.auth_service import verify_password
    if not verify_password(data.current_password, current.password_hash):
        raise HTTPException(status_code=400, detail="Contraseña actual incorrecta")
    if len(data.new_password) < 6:
        raise HTTPException(status_code=400, detail="La nueva contraseña debe tener al menos 6 caracteres")

    current.password_hash = get_password_hash(data.new_password)
    db.commit()
    return {"status": "ok", "message": "Contraseña cambiada correctamente"}


@router.put("/{admin_id}", response_model=AdminResponse)
async def update_admin(
    admin_id: int,
    data: AdminUpdate,
    db: Session = Depends(get_db),
    current: Admin = Depends(_require_superadmin),
):
    """Actualizar un administrador (solo superadmin)."""
    admin = db.query(Admin).filter(Admin.id == admin_id).first()
    if not admin:
        raise HTTPException(status_code=404, detail="Administrador no encontrado")

    # El superadmin por defecto (id=1) no puede ser degradado ni desactivado
    if admin.id == 1:
        if data.role is not None and data.role != "superadmin":
            raise HTTPException(status_code=400, detail="El superadmin principal no puede ser degradado")
        if data.is_active is not None and not data.is_active:
            raise HTTPException(status_code=400, detail="El superadmin principal no puede ser desactivado")

    if data.email is not None:
        admin.email = data.email
    if data.role is not None:
        admin.role = data.role
    if data.is_active is not None:
        admin.is_active = data.is_active

    db.commit()
    db.refresh(admin)
    return admin


@router.delete("/{admin_id}")
async def delete_admin(
    admin_id: int,
    db: Session = Depends(get_db),
    current: Admin = Depends(_require_superadmin),
):
    """Eliminar un administrador (solo superadmin)."""
    if admin_id == 1:
        raise HTTPException(status_code=400, detail="El superadmin principal no puede ser eliminado")
    if admin_id == current.id:
        raise HTTPException(status_code=400, detail="No puedes eliminar tu propia cuenta")

    admin = db.query(Admin).filter(Admin.id == admin_id).first()
    if not admin:
        raise HTTPException(status_code=404, detail="Administrador no encontrado")

    db.delete(admin)
    db.commit()
    return {"status": "ok", "message": f"Administrador '{admin.username}' eliminado"}