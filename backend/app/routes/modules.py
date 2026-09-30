"""Módulos opcionales del panel (ver services/modules_service.py)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.admin import Admin
from app.models.audit_log import AuditLog
from app.services import modules_service
from app.services.auth_service import get_current_admin, require_superadmin

router = APIRouter()


class ModuloSet(BaseModel):
    enabled: bool


@router.get("/")
def list_modules(db: Session = Depends(get_db), _: Admin = Depends(get_current_admin)):
    """Estado de cada módulo, con su título y descripción."""
    estado = modules_service.get_all(db)
    return [
        {"key": k, "enabled": estado[k], "default": d[0], "titulo": d[1], "descripcion": d[2]}
        for k, d in modules_service.MODULOS.items()
    ]


@router.put("/{key}")
def set_module(
    key: str, data: ModuloSet,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_superadmin),
):
    """Enciende o apaga un módulo. Solo el superadmin: cambia lo que ven todos."""
    if key not in modules_service.MODULOS:
        raise HTTPException(404, detail="Módulo desconocido")
    anterior = modules_service.get_all(db)[key]
    modules_service.set_enabled(db, key, data.enabled)
    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="update", entity="module", entity_id=None,
        old_value=f"{key}={anterior}", new_value=f"{key}={data.enabled}",
    ))
    db.commit()
    return {"key": key, "enabled": data.enabled}
