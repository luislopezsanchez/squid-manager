"""Rutas de cuotas de navegación (ver app/services/quota_service.py).

Por nombre de usuario, no por el id de una tabla concreta: sirve igual
para un usuario local (proxy_users) o uno importado de LDAP (ldap_users)
-son la misma cosa desde el punto de vista de "cuánto puede navegar".
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.admin import Admin
from app.models.audit_log import AuditLog
from app.models.ldap_user import LdapUser
from app.models.navigation_quota import NavigationQuota
from app.models.proxy_user import ProxyUser
from app.services.auth_service import get_current_admin, require_writer
from app.services.quota_service import ACCIONES_VALIDAS, PERIODOS_VALIDOS, revertir_accion
from app.utils import utcnow

router = APIRouter()


class QuotaSet(BaseModel):
    quota_bytes: int = Field(..., ge=1, description="Límite de bytes por periodo")
    quota_period: str = Field(..., description="'daily', 'weekly' o 'monthly'")
    quota_action: str = Field("cut", description="'cut' (cortar) o 'throttle' (limitar velocidad)")
    quota_throttle_bytes_per_sec: int | None = Field(None, ge=1)


class QuotaBulkSet(QuotaSet):
    usernames: list[str] = Field(..., min_length=1)


class QuotaResponse(BaseModel):
    id: int
    username: str
    quota_bytes: int
    quota_period: str
    quota_action: str
    quota_throttle_bytes_per_sec: int | None
    quota_bytes_used: int
    quota_period_started_at: datetime | None

    class Config:
        from_attributes = True


class QuotaBulkResult(BaseModel):
    aplicadas: list[QuotaResponse]
    errores: list[str]


def _validar(data: QuotaSet) -> None:
    if data.quota_period not in PERIODOS_VALIDOS:
        raise HTTPException(400, detail="El periodo de la cuota debe ser 'daily', 'weekly' o 'monthly'.")
    if data.quota_action not in ACCIONES_VALIDAS:
        raise HTTPException(400, detail="La acción de la cuota debe ser 'cut' o 'throttle'.")
    if data.quota_action == "throttle" and not data.quota_throttle_bytes_per_sec:
        raise HTTPException(400, detail="Falta la velocidad límite para la acción 'limitar velocidad'.")


def _existe_usuario(db: Session, username: str) -> bool:
    return (
        db.query(ProxyUser).filter(ProxyUser.username == username).first() is not None
        or db.query(LdapUser).filter(LdapUser.username == username).first() is not None
    )


def _upsert(db: Session, current_admin: Admin, username: str, data: QuotaSet) -> NavigationQuota:
    _validar(data)
    if not _existe_usuario(db, username):
        raise HTTPException(404, detail=f"'{username}' no es un usuario local ni LDAP conocido.")

    quota = db.query(NavigationQuota).filter(NavigationQuota.username == username).first()
    es_nueva = quota is None
    if es_nueva:
        quota = NavigationQuota(username=username, quota_period_started_at=utcnow())
        db.add(quota)
    elif quota.quota_action_applied:
        # Se deshace ANTES de pisar la configuración -revertir_accion()
        # deshace según la acción que de verdad estaba en efecto (la
        # vieja), no la nueva que se está por guardar. Sin esto, cambiar
        # de "limitar" a "cortar" (o solo re-guardar mientras el consumo
        # seguía por encima del límite) dejaba el pool/corte anterior
        # pegado, porque quota_action_applied ya estaba en True y nunca
        # se reevaluaba.
        revertir_accion(db, quota)
        quota.quota_action_applied = False

    quota.quota_bytes = data.quota_bytes
    quota.quota_period = data.quota_period
    quota.quota_action = data.quota_action
    quota.quota_throttle_bytes_per_sec = data.quota_throttle_bytes_per_sec
    db.flush()
    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="create" if es_nueva else "update", entity="navigation_quota", entity_id=quota.id,
        new_value=f"{username}: {data.quota_bytes} bytes / {data.quota_period} / {data.quota_action}",
    ))
    db.commit()
    return quota


@router.get("/", response_model=list[QuotaResponse])
def list_quotas(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    return db.query(NavigationQuota).order_by(NavigationQuota.username).all()


@router.put("/{username}", response_model=QuotaResponse)
def set_quota(
    username: str,
    data: QuotaSet,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
):
    """Crea o reemplaza la cuota de un usuario (local o LDAP)."""
    return _upsert(db, current_admin, username, data)


@router.post("/bulk", response_model=QuotaBulkResult)
def set_quota_bulk(
    data: QuotaBulkSet,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
):
    """Aplica la misma cuota a varios usuarios de una sola vez -para no
    repetir el mismo formulario uno por uno cuando hay que ponérsela, por
    ejemplo, a 50 usuarios importados de Active Directory. Es "mejor
    esfuerzo": un nombre inválido no aborta a los demás, solo queda
    listado en `errores`."""
    aplicadas: list[NavigationQuota] = []
    errores: list[str] = []
    for username in data.usernames:
        try:
            aplicadas.append(_upsert(db, current_admin, username, data))
        except HTTPException as e:
            errores.append(f"{username}: {e.detail}")
    return {"aplicadas": aplicadas, "errores": errores}


@router.delete("/{username}", status_code=204)
def remove_quota(
    username: str,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
):
    """Quita la cuota de un usuario -si ya estaba cortado o limitado, lo
    revierte en el acto."""
    quota = db.query(NavigationQuota).filter(NavigationQuota.username == username).first()
    if not quota:
        raise HTTPException(404, detail="Ese usuario no tiene ninguna cuota configurada.")
    if quota.quota_action_applied:
        revertir_accion(db, quota)
    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="delete", entity="navigation_quota", entity_id=quota.id,
        old_value=username,
    ))
    db.delete(quota)
    db.commit()
