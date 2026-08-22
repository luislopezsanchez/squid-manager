"""Rutas de gestión de ACLs."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.admin import Admin
from app.models.acl import Acl
from app.models.audit_log import AuditLog
from app.schemas.acl import AclCreate, AclUpdate, AclResponse
from app.services.auth_service import get_current_admin

router = APIRouter()


@router.get("/", response_model=list[AclResponse])
async def list_acls(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Lista todas las ACLs."""
    return db.query(Acl).order_by(Acl.name).all()


@router.post("/", response_model=AclResponse, status_code=201)
async def create_acl(
    data: AclCreate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """Crea una nueva ACL."""
    existing = db.query(Acl).filter(Acl.name == data.name).first()
    if existing:
        raise HTTPException(400, detail="Ya existe una ACL con ese nombre")

    acl = Acl(name=data.name, type=data.type, value=data.value,
              description=data.description, enabled=data.enabled)
    db.add(acl)
    db.flush()
    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="create", entity="acl", entity_id=acl.id, new_value=data.name,
    ))
    db.commit()
    return acl


@router.put("/{acl_id}", response_model=AclResponse)
async def update_acl(
    acl_id: int,
    data: AclUpdate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """Actualiza una ACL."""
    acl = db.query(Acl).filter(Acl.id == acl_id).first()
    if not acl:
        raise HTTPException(404, detail="ACL no encontrada")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(acl, field, value)
    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="update", entity="acl", entity_id=acl.id,
    ))
    db.commit()
    return acl


@router.delete("/{acl_id}", status_code=204)
async def delete_acl(
    acl_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """Elimina una ACL."""
    acl = db.query(Acl).filter(Acl.id == acl_id).first()
    if not acl:
        raise HTTPException(404, detail="ACL no encontrada")

    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="delete", entity="acl", entity_id=acl.id, old_value=acl.name,
    ))
    db.delete(acl)
    db.commit()