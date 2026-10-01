"""Rutas de cuotas de navegación (ver app/services/quota_service.py).

Por nombre de usuario, no por el id de una tabla concreta: sirve igual
para un usuario local (proxy_users) o uno importado de LDAP (ldap_users)
-son la misma cosa desde el punto de vista de "cuánto puede navegar".
"""

from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.admin import Admin
from app.models.audit_log import AuditLog
from app.models.ldap_user import LdapUser
from app.models.navigation_quota import NavigationQuota
from app.models.proxy_user import ProxyUser
from app.services.auth_service import get_current_admin, require_writer
from app.services.notification_service import queue_notification
from app.services.quota_service import ACCIONES_VALIDAS, PERIODOS_VALIDOS, anotar_reinicio, revertir_accion
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
    quota_action_applied: bool
    # Cuándo se restablece el consumo (medianoche / lunes / día 1, hora del servidor).
    quota_next_reset: datetime | None = None

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
    cuotas = db.query(NavigationQuota).order_by(NavigationQuota.username).all()
    for q in cuotas:
        anotar_reinicio(q)
    return cuotas


_PERIODOS_ES = {"daily": "diaria", "weekly": "semanal", "monthly": "mensual"}


def _avisar_cuota(background_tasks, db, admin: str, data: QuotaSet, nombres: list[str]) -> None:
    """Aviso de que se asignó una cuota (a uno o a varios usuarios marcados)."""
    periodo = _PERIODOS_ES.get(data.quota_period, data.quota_period)
    limite = data.quota_bytes / 1048576
    limite_txt = f"{limite / 1024:.1f} GB" if limite >= 1024 else f"{limite:.0f} MB"
    n = len(nombres)
    lista = ", ".join(nombres[:8]) + (f" y {n - 8} más" if n > 8 else "")
    if n == 1:
        msg = f"El administrador «{admin}» asignó al usuario «{lista}» una cuota {periodo} de {limite_txt}."
    else:
        msg = f"El administrador «{admin}» asignó una cuota {periodo} de {limite_txt} a {n} usuarios: {lista}."
    queue_notification(background_tasks, db, "user_change", "Se asignó una cuota de navegación", msg)


@router.put("/{username}", response_model=QuotaResponse)
def set_quota(
    username: str,
    data: QuotaSet,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
):
    """Crea o reemplaza la cuota de un usuario (local o LDAP)."""
    quota = _upsert(db, current_admin, username, data)
    anotar_reinicio(quota)
    _avisar_cuota(background_tasks, db, current_admin.username, data, [username])
    return quota


@router.post("/bulk", response_model=QuotaBulkResult)
def set_quota_bulk(
    data: QuotaBulkSet,
    background_tasks: BackgroundTasks,
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
    for q in aplicadas:
        anotar_reinicio(q)
    if aplicadas:
        _avisar_cuota(background_tasks, db, current_admin.username, data, [q.username for q in aplicadas])
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
