"""Rutas de gestión de reglas de acceso (http_access)."""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.admin import Admin
from app.models.access_rule import AccessRule
from app.models.audit_log import AuditLog
from app.schemas.access_rule import (
    AccessRuleCreate, AccessRuleUpdate, AccessRuleResponse,
)
from app.services.auth_service import get_current_admin
from app.services.notification_service import queue_notification

router = APIRouter()


class ReorderRequest(BaseModel):
    rule_ids: list[int]


@router.get("/", response_model=list[AccessRuleResponse])
async def list_access_rules(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Lista todas las reglas de acceso ordenadas."""
    return db.query(AccessRule).order_by(AccessRule.order).all()


@router.post("/", response_model=AccessRuleResponse, status_code=201)
async def create_access_rule(
    data: AccessRuleCreate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    background_tasks: BackgroundTasks = None,
):
    """Crea una nueva regla de acceso."""
    rule = AccessRule(
        action=data.action, acl_names=data.acl_names,
        order=data.order, description=data.description, enabled=data.enabled,
    )
    db.add(rule)
    db.flush()
    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="create", entity="access_rule", entity_id=rule.id,
        new_value=f"{data.action} {data.acl_names}",
    ))
    db.commit()

    if background_tasks:
        queue_notification(background_tasks, db, "rule_change",
                           "Regla de acceso creada",
                           f"El admin {current_admin.username} creó la regla '{data.action} {data.acl_names}'.")
    return rule


# IMPORTANTE: /reorder debe ir ANTES de /{rule_id} para que no sea capturado
@router.put("/reorder", response_model=list[AccessRuleResponse])
async def reorder_rules(
    data: ReorderRequest,
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
    background_tasks: BackgroundTasks = None,
):
    """Reordena las reglas de acceso. Recibe una lista de IDs en el nuevo orden."""
    for new_order, rule_id in enumerate(data.rule_ids):
        rule = db.query(AccessRule).filter(AccessRule.id == rule_id).first()
        if rule:
            rule.order = new_order
    db.commit()

    if background_tasks:
        queue_notification(background_tasks, db, "rule_change",
                           "Reglas de acceso reordenadas",
                           f"El admin reordenó {len(data.rule_ids)} reglas de acceso.")
    return db.query(AccessRule).order_by(AccessRule.order).all()


@router.put("/{rule_id}", response_model=AccessRuleResponse)
async def update_access_rule(
    rule_id: int,
    data: AccessRuleUpdate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    background_tasks: BackgroundTasks = None,
):
    """Actualiza una regla de acceso."""
    rule = db.query(AccessRule).filter(AccessRule.id == rule_id).first()
    if not rule:
        raise HTTPException(404, detail="Regla no encontrada")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)
    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="update", entity="access_rule", entity_id=rule.id,
    ))
    db.commit()

    if background_tasks:
        queue_notification(background_tasks, db, "rule_change",
                           "Regla de acceso actualizada",
                           f"El admin {current_admin.username} actualizó la regla '{rule.action} {rule.acl_names}'.")
    return rule


@router.delete("/{rule_id}", status_code=204)
async def delete_access_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    background_tasks: BackgroundTasks = None,
):
    """Elimina una regla de acceso."""
    rule = db.query(AccessRule).filter(AccessRule.id == rule_id).first()
    if not rule:
        raise HTTPException(404, detail="Regla no encontrada")

    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="delete", entity="access_rule", entity_id=rule.id,
        old_value=rule.acl_names,
    ))
    db.delete(rule)
    db.commit()

    if background_tasks:
        queue_notification(background_tasks, db, "rule_change",
                           "Regla de acceso eliminada",
                           f"El admin {current_admin.username} eliminó la regla '{rule.action} {rule.acl_names}'.")