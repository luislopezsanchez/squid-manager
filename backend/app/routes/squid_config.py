"""Rutas de configuración general de Squid."""

import logging
import re
import subprocess
from pathlib import Path

import docker as docker_sdk
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.admin import Admin
from app.models.squid_settings import SquidSetting
from app.services.auth_service import get_current_admin, require_writer
from app.services.config_generator import generate_squid_config
from app.services.squid_service import reload_squid, get_squid_status, restart_squid, write_ldap_aux_files, apply_squid_config
from app.services.notification_service import queue_notification
from app.services.config_state import mark_dirty, mark_clean, is_dirty
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


class SettingUpdate(BaseModel):
    key: str
    value: str
    category: str = "general"
    description: str | None = None


@router.get("/settings")
async def get_settings(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Obtiene toda la configuración de Squid."""
    settings_list = db.query(SquidSetting).all()
    return {s.key: {"value": s.value, "category": s.category, "description": s.description} for s in settings_list}


@router.put("/settings")
async def update_setting(
    data: SettingUpdate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
):
    """Actualiza una configuración de Squid."""
    setting = db.query(SquidSetting).filter(SquidSetting.key == data.key).first()
    if setting:
        setting.value = data.value
        setting.category = data.category
        if data.description:
            setting.description = data.description
    else:
        setting = SquidSetting(key=data.key, value=data.value,
                                category=data.category, description=data.description)
        db.add(setting)
    db.commit()
    mark_dirty()
    return {"status": "ok", "key": data.key, "value": data.value}


@router.post("/apply")
async def apply_config(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
    background_tasks: BackgroundTasks = None,
):
    """Genera el squid.conf, valida y recarga o reinicia Squid.

    Si el http_port de la BD no coincide con el puerto que Docker publica,
    sincroniza el .env y recrea el contenedor con `docker compose up -d squid`,
    de modo que el mapeo de puertos sobreviva a cualquier recreación posterior.
    """
    result = apply_squid_config(db)

    if result["status"] == "error":
        return result

    if background_tasks:
        action = "reinicio con SSL Bump" if result.get("needs_restart") else "reconfigure"
        queue_notification(background_tasks, db, "apply",
                           "Cambios aplicados a Squid",
                           f"El admin {current_admin.username} aplicó cambios ({action}).")

    return result


@router.get("/status")
async def get_status(_: Admin = Depends(get_current_admin)):
    """Estado del servicio Squid."""
    return get_squid_status()


@router.get("/preview")
async def preview_config(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Previsualiza el squid.conf que se generaría."""
    config_text = generate_squid_config(db)
    return {"config": config_text}


@router.get("/pending")
async def pending_changes(
    _: Admin = Depends(get_current_admin),
):
    """Indica si hay cambios en la BD que aún no se han aplicado a Squid."""
    return {"dirty": is_dirty()}


@router.get("/ca-cert")
async def download_ca_cert(_: Admin = Depends(get_current_admin)):
    """Descarga el certificado CA de Squid para instalar en los clientes."""
    from fastapi import Response
    ca_path = "/etc/squid/ssl_cert/squid-ca.crt"
    try:
        with open(ca_path, "r") as f:
            content = f.read()
        return Response(
            content=content,
            media_type="application/x-x509-ca-cert",
            headers={"Content-Disposition": "attachment; filename=squidmanager-ca.crt"},
        )
    except FileNotFoundError:
        raise HTTPException(404, detail="Certificado CA no encontrado. Reinicia el contenedor Squid.")


@router.get("/ca-deploy/install-cert.bat")
async def download_bat_installer(_: Admin = Depends(get_current_admin)):
    """Descarga el instalador .bat (Windows) con el certificado embebido."""
    from fastapi import Response
    from app.services.cert_deploy_service import generate_bat_installer, CaCertNotFound
    try:
        content = generate_bat_installer()
    except CaCertNotFound as e:
        raise HTTPException(404, detail=str(e))
    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={"Content-Disposition": "attachment; filename=install-cert.bat"},
    )


@router.get("/ca-deploy/deploy-gpo.ps1")
async def download_gpo_script(_: Admin = Depends(get_current_admin)):
    """Descarga el script PowerShell para desplegar el certificado vía GPO."""
    from fastapi import Response
    from app.services.cert_deploy_service import generate_gpo_script, CaCertNotFound
    try:
        content = generate_gpo_script()
    except CaCertNotFound as e:
        raise HTTPException(404, detail=str(e))
    return Response(
        content=content,
        media_type="text/plain",
        headers={"Content-Disposition": "attachment; filename=deploy-gpo.ps1"},
    )


@router.get("/ca-deploy/cert.mobileconfig")
async def download_mobileconfig(_: Admin = Depends(get_current_admin)):
    """Descarga el perfil .mobileconfig para iOS/macOS."""
    from fastapi import Response
    from app.services.cert_deploy_service import generate_mobileconfig, CaCertNotFound
    try:
        content = generate_mobileconfig()
    except CaCertNotFound as e:
        raise HTTPException(404, detail=str(e))
    return Response(
        content=content,
        media_type="application/x-apple-aspen-config",
        headers={"Content-Disposition": "attachment; filename=squidmanager-ca.mobileconfig"},
    )