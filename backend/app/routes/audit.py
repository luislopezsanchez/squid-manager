"""Rutas de auditoría: log de cambios realizados en el sistema."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import get_db
from app.models.admin import Admin
from app.models.audit_log import AuditLog
from app.services.auth_service import get_current_admin

router = APIRouter()


@router.get("/")
async def list_audit_log(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    entity: str | None = Query(None, description="Filtrar por entidad"),
    action: str | None = Query(None, description="Filtrar por acción"),
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Lista el log de auditoría con paginación y filtros opcionales."""
    query = db.query(AuditLog)

    if entity:
        query = query.filter(AuditLog.entity == entity)
    if action:
        query = query.filter(AuditLog.action == action)

    total = query.count()
    entries = query.order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit).all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "entries": [
            {
                "id": e.id,
                "admin_id": e.admin_id,
                "admin_username": e.admin_username,
                "action": e.action,
                "entity": e.entity,
                "entity_id": e.entity_id,
                "old_value": e.old_value,
                "new_value": e.new_value,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            }
            for e in entries
        ],
    }


@router.get("/stats")
async def audit_stats(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Estadísticas del log de auditoría."""
    total = db.query(AuditLog).count()

    # Conteos por entidad
    from sqlalchemy import func
    by_entity = db.query(AuditLog.entity, func.count(AuditLog.id)).group_by(AuditLog.entity).all()
    by_action = db.query(AuditLog.action, func.count(AuditLog.id)).group_by(AuditLog.action).all()

    return {
        "total": total,
        "by_entity": {entity: count for entity, count in by_entity},
        "by_action": {action: count for action, count in by_action},
    }