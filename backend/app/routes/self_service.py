"""Portal de autoservicio: un usuario local del proxy gestiona su propia cuenta.

El usuario entra al panel con su usuario y contraseña del proxy (POST
/api/auth/login) y recibe un token de otro tipo que solo abre estas rutas: no
sirve contra la API de administración.
"""

import calendar
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.audit_log import AuditLog
from app.models.navigation_quota import NavigationQuota
from app.models.proxy_user import ProxyUser
from app.models.user_group import UserGroup, UserGroupMember
from app.routes.proxy_users import (
    _generate_digest_ha1, _generate_htpasswd_hash, _revocar, _sync_passwd,
)
from app.services.auth_service import get_current_proxy_user, get_password_hash, verify_password
from app.services import modules_service, rollup_service
from app.services.quota_service import proximo_reinicio
from app.services.squid_service import realm_actual

MIN_PASSWORD_LENGTH = 10


def _portal_habilitado(db: Session = Depends(get_db)):
    """Con el módulo apagado el portal no existe: quien tenía una sesión abierta vuelve al acceso."""
    if not modules_service.is_enabled(db, "autoservicio"):
        raise HTTPException(401, detail="El portal de autoservicio no está disponible.",
                            headers={"WWW-Authenticate": "Bearer"})


router = APIRouter(dependencies=[Depends(_portal_habilitado)])


class SelfMeResponse(BaseModel):
    username: str
    display_name: str | None = None
    email: str | None = None
    expires_at: str | None = None


class SelfPasswordChange(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=100)
    new_password: str = Field(..., min_length=MIN_PASSWORD_LENGTH, max_length=100)


@router.get("/me", response_model=SelfMeResponse)
def me(user: ProxyUser = Depends(get_current_proxy_user)):
    """Datos de la cuenta del usuario conectado."""
    return SelfMeResponse(
        username=user.username,
        display_name=user.display_name,
        email=user.email,
        expires_at=user.expires_at.isoformat() if user.expires_at else None,
    )


def _epoch(dt) -> int | None:
    return calendar.timegm(dt.timetuple()) if dt else None


@router.get("/dashboard")
def dashboard(
    ventana: Literal["7d", "30d"] = Query("7d"),
    db: Session = Depends(get_db),
    user: ProxyUser = Depends(get_current_proxy_user),
):
    """Resumen de navegación del propio usuario: consumo por día, peticiones, bloqueos y cuota.

    Todo se filtra por el nombre del token; la petición no puede pedir los datos de otro usuario.
    """
    dias = 7 if ventana == "7d" else 30
    actividad = rollup_service.actividad_usuario(user.username, dias)

    cuota = db.query(NavigationQuota).filter(NavigationQuota.username == user.username).first()
    cuota_json = None
    if cuota and cuota.quota_bytes > 0:
        cuota_json = {
            "periodo": cuota.quota_period,
            "limite_bytes": cuota.quota_bytes,
            "usado_bytes": cuota.quota_bytes_used,
            "accion": cuota.quota_action,
            "agotada": cuota.quota_bytes_used >= cuota.quota_bytes,
            "proximo_reinicio": _epoch(proximo_reinicio(cuota.quota_period_started_at, cuota.quota_period))
            if cuota.quota_period_started_at else None,
        }

    grupos = [g for (g,) in (
        db.query(UserGroup.name)
        .join(UserGroupMember, UserGroupMember.group_id == UserGroup.id)
        .filter(UserGroupMember.username == user.username)
        .order_by(UserGroup.name).all()
    )]

    return {"ventana": ventana, **actividad, "cuota": cuota_json, "grupos": grupos}


@router.put("/change-password")
def change_password(
    data: SelfPasswordChange,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: ProxyUser = Depends(get_current_proxy_user),
):
    """Cambia la contraseña con la que el usuario navega por el proxy.

    Mismo procedimiento que el reset hecho por el administrador: actualiza los
    tres hashes (panel, htpasswd de Squid y digest), reescribe los ficheros de
    Squid y purga su caché de credenciales para que la contraseña vieja deje de
    valer enseguida.
    """
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(400, detail="Contraseña actual incorrecta")
    if data.new_password == data.current_password:
        raise HTTPException(400, detail="La contraseña nueva debe ser distinta de la actual")

    realm = realm_actual(db)
    user.password_hash = get_password_hash(data.new_password)
    user.htpasswd_hash = _generate_htpasswd_hash(user.username, data.new_password)
    user.digest_ha1 = _generate_digest_ha1(user.username, data.new_password, realm)
    user.digest_ha1_realm = realm

    db.add(AuditLog(
        admin_id=None, admin_username=user.username,
        action="self_change_password", entity="proxy_user", entity_id=user.id,
        new_value=user.username,
    ))
    _sync_passwd(db)
    db.commit()
    _revocar(background_tasks)

    return {
        "status": "ok",
        "message": "Contraseña cambiada. Vuelve a iniciar sesión.",
        "reauth_required": True,
    }
