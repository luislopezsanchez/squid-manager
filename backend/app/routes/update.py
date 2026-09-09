"""Rutas de "Actualizaciones": comprobar, aprobar/programar y cancelar una

actualización de SquidManager contra su propio repositorio de GitHub. Solo
instalación nativa -ver la nota de diseño al principio de
app/services/update_service.py-. Las acciones que pueden terminar
disparando un cambio de código y un reinicio de servicios (aprobar,
cancelar, forzar comprobación, activar/desactivar el chequeo) quedan
reservadas a superadmin, igual que Administradores: es la acción de mayor
alcance que puede pedir el panel, no corresponde dejarla en manos de un
admin común.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.admin import Admin
from app.models.update_config import UpdateConfig
from app.services.auth_service import get_current_admin, require_superadmin
from app.services.update_service import (
    UpdateServiceError,
    aprobar_actualizacion,
    cancelar_actualizacion,
    comprobar_actualizacion,
    estado_actual,
)
from app.utils import as_naive_utc

router = APIRouter()


class AprobarIn(BaseModel):
    # None = ahora. Con fecha, queda programada para que el temporizador la
    # aplique cuando llegue -ver autoupdate-check.sh-.
    scheduled_at: datetime | None = None


def _obtener_o_crear_config(db: Session) -> UpdateConfig:
    config = db.query(UpdateConfig).first()
    if not config:
        config = UpdateConfig(id=1)
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


@router.get("/estado")
async def get_estado(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Cualquier admin puede consultar el estado -incluida una cuenta de

    solo lectura-: es informativo, no cambia nada.
    """
    config = _obtener_o_crear_config(db)
    estado = await run_in_threadpool(estado_actual)
    return {
        "es_nativo": settings.DEPLOY_MODE.strip().lower() == "native",
        "version_actual": settings.APP_VERSION,
        "check_enabled": config.check_enabled,
        **estado,
    }


@router.post("/comprobar")
async def post_comprobar(
    db: Session = Depends(get_db),
    _: Admin = Depends(require_superadmin),
):
    """Fuerza una comprobación inmediata contra GitHub, sin esperar al

    próximo ciclo del hilo de fondo (cada 6 h).
    """
    _obtener_o_crear_config(db)
    try:
        estado = await run_in_threadpool(comprobar_actualizacion)
    except UpdateServiceError as e:
        raise HTTPException(400, detail=str(e))
    return estado


@router.put("/config")
async def put_config(
    data: dict,
    db: Session = Depends(get_db),
    _: Admin = Depends(require_superadmin),
):
    config = _obtener_o_crear_config(db)
    if "check_enabled" in data:
        config.check_enabled = bool(data["check_enabled"])
    db.commit()
    return {"status": "ok"}


@router.post("/aprobar")
async def post_aprobar(
    data: AprobarIn,
    current_admin: Admin = Depends(require_superadmin),
):
    """Aprueba la actualización disponible: para ahora (sin `scheduled_at`)

    o programada para una fecha futura. Ver la nota de diseño en
    update_service.py sobre por qué esto nunca ejecuta nada con privilegios
    directamente.
    """
    programado = as_naive_utc(data.scheduled_at)
    try:
        estado = await run_in_threadpool(aprobar_actualizacion, current_admin.username, programado)
    except UpdateServiceError as e:
        raise HTTPException(400, detail=str(e))
    return estado


@router.post("/cancelar")
async def post_cancelar(
    _: Admin = Depends(require_superadmin),
):
    try:
        estado = await run_in_threadpool(cancelar_actualizacion)
    except UpdateServiceError as e:
        raise HTTPException(400, detail=str(e))
    return estado
