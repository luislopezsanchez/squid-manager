"""Rutas de cuotas de navegación por GRUPO (pool compartido) -ver
app/services/quota_service.py y el docstring de GroupQuota sobre por qué
solo admite grupos locales.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.admin import Admin
from app.models.audit_log import AuditLog
from app.models.group_quota import GroupQuota
from app.models.user_group import UserGroup
from app.services.auth_service import get_current_admin, require_writer
from app.services.quota_service import ACCIONES_VALIDAS, PERIODOS_VALIDOS, revertir_accion_grupo
from app.utils import utcnow

router = APIRouter()


class GroupQuotaSet(BaseModel):
    quota_bytes: int = Field(..., ge=1, description="Límite de bytes por periodo, compartido por todo el grupo")
    quota_period: str = Field(..., description="'daily', 'weekly' o 'monthly'")
    quota_action: str = Field("cut", description="'cut' (cortar) o 'throttle' (limitar velocidad)")
    quota_throttle_bytes_per_sec: int | None = Field(None, ge=1)


class GroupQuotaResponse(BaseModel):
    id: int
    group_name: str
    quota_bytes: int
    quota_period: str
    quota_action: str
    quota_throttle_bytes_per_sec: int | None
    quota_bytes_used: int
    quota_period_started_at: datetime | None
    quota_action_applied: bool

    class Config:
        from_attributes = True


def _validar(data: GroupQuotaSet) -> None:
    if data.quota_period not in PERIODOS_VALIDOS:
        raise HTTPException(400, detail="El periodo de la cuota debe ser 'daily', 'weekly' o 'monthly'.")
    if data.quota_action not in ACCIONES_VALIDAS:
        raise HTTPException(400, detail="La acción de la cuota debe ser 'cut' o 'throttle'.")
    if data.quota_action == "throttle" and not data.quota_throttle_bytes_per_sec:
        raise HTTPException(400, detail="Falta la velocidad límite para la acción 'limitar velocidad'.")


def _grupo_local(db: Session, group_name: str) -> UserGroup:
    grupo = db.query(UserGroup).filter(UserGroup.name == group_name).first()
    if not grupo:
        raise HTTPException(404, detail=f"No existe ningún grupo llamado '{group_name}'.")
    if grupo.source != "local":
        raise HTTPException(
            400,
            detail=(
                "El pool compartido solo admite grupos locales: un grupo de LDAP no tiene "
                "una lista de miembros que este panel pueda leer directo -se resuelve en vivo "
                "contra el directorio, no hay de dónde sumar el consumo de cada uno."
            ),
        )
    return grupo


@router.get("/", response_model=list[GroupQuotaResponse])
def list_group_quotas(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    return db.query(GroupQuota).order_by(GroupQuota.group_name).all()


@router.put("/{group_name}", response_model=GroupQuotaResponse)
def set_group_quota(
    group_name: str,
    data: GroupQuotaSet,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
):
    """Crea o reemplaza el pool compartido de un grupo local."""
    _validar(data)
    _grupo_local(db, group_name)

    quota = db.query(GroupQuota).filter(GroupQuota.group_name == group_name).first()
    es_nueva = quota is None
    if es_nueva:
        quota = GroupQuota(group_name=group_name, quota_period_started_at=utcnow())
        db.add(quota)
    elif quota.quota_action_applied:
        # Mismo motivo que _upsert() en quotas.py: se deshace ANTES de
        # pisar la configuración, según la acción vieja, no la nueva.
        revertir_accion_grupo(db, quota)
        quota.quota_action_applied = False

    quota.quota_bytes = data.quota_bytes
    quota.quota_period = data.quota_period
    quota.quota_action = data.quota_action
    quota.quota_throttle_bytes_per_sec = data.quota_throttle_bytes_per_sec
    db.flush()
    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="create" if es_nueva else "update", entity="group_quota", entity_id=quota.id,
        new_value=f"{group_name}: {data.quota_bytes} bytes / {data.quota_period} / {data.quota_action}",
    ))
    db.commit()
    return quota


@router.delete("/{group_name}", status_code=204)
def remove_group_quota(
    group_name: str,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
):
    """Quita el pool compartido de un grupo -si ya estaba cortado o
    limitado, lo revierte en el acto (reactiva a los miembros o borra el
    delay pool, según corresponda)."""
    quota = db.query(GroupQuota).filter(GroupQuota.group_name == group_name).first()
    if not quota:
        raise HTTPException(404, detail="Ese grupo no tiene ningún pool compartido configurado.")
    if quota.quota_action_applied:
        revertir_accion_grupo(db, quota)
    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="delete", entity="group_quota", entity_id=quota.id,
        old_value=group_name,
    ))
    db.delete(quota)
    db.commit()
