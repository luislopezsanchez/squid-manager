"""Rutas de auditoría: log de cambios realizados en el sistema."""

import csv
import io
import json
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import get_db
from app.models.admin import Admin
from app.models.audit_log import AuditLog
from app.services.auth_service import get_current_admin

router = APIRouter()


@router.get("/")
def list_audit_log(
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


_COLUMNAS_EXPORT = ["id", "timestamp", "admin_username", "action", "entity", "entity_id", "old_value", "new_value"]


def _fila_export(e: AuditLog) -> dict:
    return {
        "id": e.id,
        "timestamp": e.timestamp.isoformat() if e.timestamp else "",
        "admin_username": e.admin_username or "",
        "action": e.action,
        "entity": e.entity,
        "entity_id": e.entity_id if e.entity_id is not None else "",
        "old_value": e.old_value or "",
        "new_value": e.new_value or "",
    }


@router.get("/export")
def export_audit_log(
    format: Literal["csv", "ndjson"] = Query("csv"),
    entity: str | None = Query(None, description="Filtrar por entidad"),
    action: str | None = Query(None, description="Filtrar por acción"),
    desde: str | None = Query(None, description="Fecha inicial YYYY-MM-DD (inclusive)"),
    hasta: str | None = Query(None, description="Fecha final YYYY-MM-DD (inclusive)"),
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Descarga el registro de auditoría con los mismos filtros de la pantalla
    (más un rango de fechas), en streaming: el historial puede tener
    cientos de miles de filas y no se carga entero en memoria.

    - csv: para hoja de cálculo (con BOM UTF-8, para que Excel respete los acentos).
    - ndjson: un objeto JSON por línea, para ingesta en un SIEM o con jq.
    """
    from fastapi import HTTPException
    from datetime import timedelta

    query = db.query(AuditLog)
    if entity:
        query = query.filter(AuditLog.entity == entity)
    if action:
        query = query.filter(AuditLog.action == action)
    try:
        if desde:
            query = query.filter(AuditLog.timestamp >= datetime.strptime(desde, "%Y-%m-%d"))
        if hasta:
            query = query.filter(AuditLog.timestamp < datetime.strptime(hasta, "%Y-%m-%d") + timedelta(days=1))
    except ValueError:
        raise HTTPException(400, detail="Fecha inválida: usa el formato YYYY-MM-DD.")
    query = query.order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())

    stamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")

    if format == "ndjson":
        def _gen_ndjson():
            for e in query.yield_per(1000):
                yield json.dumps(_fila_export(e), ensure_ascii=False) + "\n"
        return StreamingResponse(
            _gen_ndjson(), media_type="application/x-ndjson",
            headers={"Content-Disposition": f"attachment; filename=auditoria-{stamp}.ndjson"},
        )

    def _gen_csv():
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=_COLUMNAS_EXPORT)
        yield "\ufeff"
        w.writeheader()
        yield buf.getvalue()
        for e in query.yield_per(1000):
            buf = io.StringIO()
            csv.DictWriter(buf, fieldnames=_COLUMNAS_EXPORT).writerow(_fila_export(e))
            yield buf.getvalue()

    return StreamingResponse(
        _gen_csv(), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=auditoria-{stamp}.csv"},
    )


@router.get("/stats")
def audit_stats(
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