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
from app.services.auth_service import get_current_admin, require_writer
from app.services.notification_service import queue_notification
from app.services.config_state import mark_dirty
from app.services.squid_names import validate_acl_names, known_acl_names

router = APIRouter()


class ReorderRequest(BaseModel):
    rule_ids: list[int]


@router.get("/", response_model=list[AccessRuleResponse])
def list_access_rules(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Lista todas las reglas de acceso ordenadas."""
    return db.query(AccessRule).order_by(AccessRule.order, AccessRule.id).all()


@router.post("/", response_model=AccessRuleResponse, status_code=201)
def create_access_rule(
    data: AccessRuleCreate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
    background_tasks: BackgroundTasks = None,
):
    """Crea una nueva regla de acceso."""
    # Se comprueba que todas las ACLs citadas existan: una regla que nombra una
    # ACL inexistente hace que Squid rechace el fichero de configuración entero.
    acl_names = validate_acl_names(data.acl_names, known_acl_names(db))

    rule = AccessRule(
        action=data.action, acl_names=acl_names,
        order=data.order, description=data.description, enabled=data.enabled,
    )
    db.add(rule)
    db.flush()
    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="create", entity="access_rule", entity_id=rule.id,
        new_value=f"{data.action} {acl_names}",
    ))
    db.commit()
    mark_dirty()

    if background_tasks:
        queue_notification(background_tasks, db, "rule_change",
                           "Regla de acceso creada",
                           f"El admin {current_admin.username} creó la regla '{data.action} {acl_names}'.")
    return rule


# IMPORTANTE: /reorder debe ir ANTES de /{rule_id} para que no sea capturado
@router.put("/reorder", response_model=list[AccessRuleResponse])
def reorder_rules(
    data: ReorderRequest,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
    background_tasks: BackgroundTasks = None,
):
    """Reordena las reglas de acceso. Recibe una lista de IDs en el nuevo orden."""
    # Bugs reales encontrados en la auditoría QA 2026-09-20: una lista vacía
    # devolvía 200 sin avisar que no hizo nada (probablemente un bug del
    # frontend, no una operación intencional), y un ID inexistente se
    # ignoraba en silencio (`if rule:`) sin que el llamador se enterara.
    if not data.rule_ids:
        raise HTTPException(400, detail="La lista de reglas a reordenar no puede estar vacía.")

    reglas = {
        r.id: r
        for r in db.query(AccessRule).filter(AccessRule.id.in_(data.rule_ids)).all()
    }
    faltantes = [rid for rid in data.rule_ids if rid not in reglas]
    if faltantes:
        raise HTTPException(
            400,
            detail=f"No existen reglas con id: {', '.join(str(i) for i in faltantes)}.",
        )

    before = [
        f"{r.action} {r.acl_names}"
        for r in db.query(AccessRule).order_by(AccessRule.order, AccessRule.id).all()
    ]

    for new_order, rule_id in enumerate(data.rule_ids):
        reglas[rule_id].order = new_order

    after = [
        f"{r.action} {r.acl_names}"
        for r in db.query(AccessRule).order_by(AccessRule.order, AccessRule.id).all()
    ]
    # El orden de las reglas ES la política: cambiarlo se audita como cualquier
    # otra modificación.
    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="reorder", entity="access_rule",
        old_value=" | ".join(before), new_value=" | ".join(after),
    ))
    db.commit()
    mark_dirty()

    if background_tasks:
        queue_notification(background_tasks, db, "rule_change",
                           "Reglas de acceso reordenadas",
                           f"El admin {current_admin.username} reordenó {len(data.rule_ids)} reglas de acceso.")
    return db.query(AccessRule).order_by(AccessRule.order, AccessRule.id).all()


@router.put("/{rule_id}", response_model=AccessRuleResponse)
def update_access_rule(
    rule_id: int,
    data: AccessRuleUpdate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
    background_tasks: BackgroundTasks = None,
):
    """Actualiza una regla de acceso."""
    rule = db.query(AccessRule).filter(AccessRule.id == rule_id).first()
    if not rule:
        raise HTTPException(404, detail="Regla no encontrada")

    old_value = f"{rule.action} {rule.acl_names}"
    changes = data.model_dump(exclude_unset=True)
    if changes.get("acl_names"):
        changes["acl_names"] = validate_acl_names(changes["acl_names"], known_acl_names(db))

    for field, value in changes.items():
        setattr(rule, field, value)

    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="update", entity="access_rule", entity_id=rule.id,
        old_value=old_value, new_value=f"{rule.action} {rule.acl_names}",
    ))
    db.commit()
    mark_dirty()

    if background_tasks:
        queue_notification(background_tasks, db, "rule_change",
                           "Regla de acceso actualizada",
                           f"El admin {current_admin.username} actualizó la regla '{rule.action} {rule.acl_names}'.")
    return rule


@router.delete("/{rule_id}", status_code=204)
def delete_access_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
    background_tasks: BackgroundTasks = None,
):
    """Elimina una regla de acceso."""
    rule = db.query(AccessRule).filter(AccessRule.id == rule_id).first()
    if not rule:
        raise HTTPException(404, detail="Regla no encontrada")

    descripcion = f"{rule.action} {rule.acl_names}"
    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="delete", entity="access_rule", entity_id=rule.id,
        old_value=rule.acl_names,
    ))
    db.delete(rule)
    db.commit()
    mark_dirty()

    if background_tasks:
        queue_notification(background_tasks, db, "rule_change",
                           "Regla de acceso eliminada",
                           f"El admin {current_admin.username} eliminó la regla '{descripcion}'.")
