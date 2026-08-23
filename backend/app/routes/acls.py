"""Rutas de gestión de ACLs."""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.admin import Admin
from app.models.acl import Acl
from app.models.audit_log import AuditLog
from app.schemas.acl import AclCreate, AclUpdate, AclResponse
from app.services.auth_service import get_current_admin, require_writer
from app.services.notification_service import queue_notification
from app.services.config_state import mark_dirty
from app.services.squid_names import (
    validate_name, validate_acl_type, validate_value,
    ensure_not_referenced, find_references,
)

router = APIRouter()


@router.get("/", response_model=list[AclResponse])
async def list_acls(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Lista todas las ACLs."""
    return db.query(Acl).order_by(Acl.name).all()


@router.get("/unused", response_model=list[str])
async def list_unused_acls(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Nombres de ACLs que no usa ninguna regla ni delay pool.

    Una ACL por sí sola no bloquea nada: hasta que una regla de acceso la
    referencia, no tiene ningún efecto sobre el tráfico.
    """
    return [a.name for a in db.query(Acl).order_by(Acl.name).all() if not find_references(db, a.name)]


@router.post("/", response_model=AclResponse, status_code=201)
async def create_acl(
    data: AclCreate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
    background_tasks: BackgroundTasks = None,
):
    """Crea una nueva ACL."""
    name = validate_name(data.name, "ACL")
    acl_type = validate_acl_type(data.type)
    value = validate_value(data.value)

    existing = db.query(Acl).filter(Acl.name == name).first()
    if existing:
        raise HTTPException(400, detail="Ya existe una ACL con ese nombre")

    acl = Acl(name=name, type=acl_type, value=value,
              description=data.description, enabled=data.enabled)
    db.add(acl)
    db.flush()
    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="create", entity="acl", entity_id=acl.id, new_value=f"{name} {acl_type} {value}",
    ))
    db.commit()
    mark_dirty()

    if background_tasks:
        queue_notification(background_tasks, db, "acl_change",
                           "ACL creada",
                           f"El admin {current_admin.username} creó la ACL '{name}' ({acl_type}).")
    return acl


@router.put("/{acl_id}", response_model=AclResponse)
async def update_acl(
    acl_id: int,
    data: AclUpdate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
    background_tasks: BackgroundTasks = None,
):
    """Actualiza una ACL."""
    acl = db.query(Acl).filter(Acl.id == acl_id).first()
    if not acl:
        raise HTTPException(404, detail="ACL no encontrada")

    changes = data.model_dump(exclude_unset=True)
    old_value = f"{acl.name} {acl.type} {acl.value}"

    # Renombrar rompe las reglas que citan el nombre anterior.
    if "name" in changes and changes["name"] != acl.name:
        ensure_not_referenced(db, acl.name, "renombrar")
        changes["name"] = validate_name(changes["name"], "ACL")
        if db.query(Acl).filter(Acl.name == changes["name"], Acl.id != acl_id).first():
            raise HTTPException(400, detail="Ya existe una ACL con ese nombre")
    if "type" in changes and changes["type"] is not None:
        changes["type"] = validate_acl_type(changes["type"])
    if "value" in changes and changes["value"] is not None:
        changes["value"] = validate_value(changes["value"])

    for field, value in changes.items():
        setattr(acl, field, value)

    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="update", entity="acl", entity_id=acl.id,
        old_value=old_value, new_value=f"{acl.name} {acl.type} {acl.value}",
    ))
    db.commit()
    mark_dirty()

    if background_tasks:
        queue_notification(background_tasks, db, "acl_change",
                           "ACL actualizada",
                           f"El admin {current_admin.username} actualizó la ACL '{acl.name}'.")
    return acl


@router.delete("/{acl_id}", status_code=204)
async def delete_acl(
    acl_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
    background_tasks: BackgroundTasks = None,
):
    """Elimina una ACL."""
    acl = db.query(Acl).filter(Acl.id == acl_id).first()
    if not acl:
        raise HTTPException(404, detail="ACL no encontrada")

    ensure_not_referenced(db, acl.name, "eliminar")

    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="delete", entity="acl", entity_id=acl.id, old_value=acl.name,
    ))
    name = acl.name
    db.delete(acl)
    db.commit()
    mark_dirty()

    if background_tasks:
        queue_notification(background_tasks, db, "acl_change",
                           "ACL eliminada",
                           f"El admin {current_admin.username} eliminó la ACL '{name}'.")
