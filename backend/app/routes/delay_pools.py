"""Rutas de gestión de Delay Pools (control de ancho de banda)."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.database import get_db
from app.models.admin import Admin
from app.models.delay_pool import DelayPool
from app.models.audit_log import AuditLog
from app.services.auth_service import get_current_admin
from app.services.config_state import mark_dirty

router = APIRouter()


class DelayPoolCreate(BaseModel):
    pool_class: int = Field(..., ge=1, le=5, description="Clase 1-5")
    parameters: str = Field(..., description="Parámetros en formato Squid: rate/limit")
    acl_name: str | None = Field(None, description="ACL asociada al pool")
    description: str | None = None
    enabled: bool = True


class DelayPoolUpdate(BaseModel):
    pool_class: int | None = Field(None, ge=1, le=5)
    parameters: str | None = None
    acl_name: str | None = None
    description: str | None = None
    enabled: bool | None = None


class DelayPoolResponse(BaseModel):
    id: int
    pool_class: int
    parameters: str
    acl_name: str | None
    description: str | None
    enabled: bool

    class Config:
        from_attributes = True


@router.get("/", response_model=list[DelayPoolResponse])
async def list_delay_pools(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Lista todos los delay pools."""
    return db.query(DelayPool).order_by(DelayPool.id).all()


@router.post("/", response_model=DelayPoolResponse, status_code=201)
async def create_delay_pool(
    data: DelayPoolCreate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """Crea un nuevo delay pool."""
    pool = DelayPool(
        pool_class=data.pool_class,
        parameters=data.parameters,
        acl_name=data.acl_name,
        description=data.description,
        enabled=data.enabled,
    )
    db.add(pool)
    db.flush()
    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="create", entity="delay_pool", entity_id=pool.id,
        new_value=f"class {data.pool_class}: {data.parameters}",
    ))
    db.commit()
    mark_dirty()
    return pool


@router.put("/{pool_id}", response_model=DelayPoolResponse)
async def update_delay_pool(
    pool_id: int,
    data: DelayPoolUpdate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """Actualiza un delay pool."""
    pool = db.query(DelayPool).filter(DelayPool.id == pool_id).first()
    if not pool:
        raise HTTPException(404, detail="Delay pool no encontrado")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(pool, field, value)
    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="update", entity="delay_pool", entity_id=pool.id,
    ))
    db.commit()
    mark_dirty()
    return pool


@router.delete("/{pool_id}", status_code=204)
async def delete_delay_pool(
    pool_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """Elimina un delay pool."""
    pool = db.query(DelayPool).filter(DelayPool.id == pool_id).first()
    if not pool:
        raise HTTPException(404, detail="Delay pool no encontrado")

    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="delete", entity="delay_pool", entity_id=pool.id,
        old_value=f"class {pool.pool_class}: {pool.parameters}",
    ))
    db.delete(pool)
    db.commit()
    mark_dirty()