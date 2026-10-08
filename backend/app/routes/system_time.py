"""Zona horaria de la instalación (Sistema → Configuración)."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.admin import Admin
from app.models.audit_log import AuditLog
from app.services import timezone_service as tzs
from app.services.auth_service import get_current_admin, require_writer

router = APIRouter()


class ZonaIn(BaseModel):
    # None o "" = usar la zona del sistema operativo.
    zona: str | None = None


def _estado() -> dict:
    ahora = tzs.ahora_local()
    return {
        "zona": tzs.nombre_configurado(),
        "zona_sistema": tzs.nombre_sistema(),
        "zona_efectiva": str(tzs.get_tz()),
        "hora_actual": ahora.strftime("%Y-%m-%d %H:%M:%S"),
        "desfase": ahora.strftime("%z"),
        "zonas": tzs.zonas(),
    }


@router.get("")
def obtener(_: Admin = Depends(get_current_admin)):
    return _estado()


@router.put("")
def cambiar(data: ZonaIn, db: Session = Depends(get_db), admin: Admin = Depends(require_writer)):
    zona = (data.zona or "").strip() or None
    if zona and not tzs.es_valida(zona):
        raise HTTPException(400, "Zona horaria no válida")
    antes = tzs.nombre_configurado()
    tzs.guardar(zona)
    db.add(AuditLog(admin_id=admin.id, admin_username=admin.username, action="update", entity="timezone",
                    entity_id=None, old_value=antes or "(sistema)", new_value=zona or "(sistema)"))
    db.commit()
    return _estado()
