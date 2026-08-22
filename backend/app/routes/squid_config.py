"""Rutas de configuración general de Squid."""

import logging
import re
import subprocess
from pathlib import Path

import docker as docker_sdk
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.admin import Admin
from app.models.squid_settings import SquidSetting
from app.services.auth_service import get_current_admin
from app.services.config_generator import generate_squid_config, validate_squid_config
from app.services.squid_service import reload_squid, get_squid_status, restart_squid
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
    _: Admin = Depends(get_current_admin),
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
    return {"status": "ok", "key": data.key, "value": data.value}


@router.post("/apply")
async def apply_config(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Genera el squid.conf, valida y recarga o reinicia Squid.

    Si el puerto http_port de la BD no coincide con el puerto que Docker
    tiene publicado actualmente, recrea el contenedor con docker compose up -d
    para actualizar el mapeo de puertos.
    """
    # 1. Generar configuración desde la BD
    config_text = generate_squid_config(db)

    # 2. Extraer el puerto nuevo del config generado
    new_port_match = re.search(r'^http_port\s+(\d+)', config_text, re.MULTILINE)
    new_port = new_port_match.group(1) if new_port_match else None

    # 3. Comparar con el puerto que Docker tiene publicado actualmente
    needs_restart = False
    if new_port:
        try:
            client = docker_sdk.from_env()
            container = client.containers.get(settings.SQUID_CONTAINER_NAME)
            container.reload()
            published_ports = container.attrs.get("NetworkSettings", {}).get("Ports", {})
            for port_key, bindings in published_ports.items():
                if bindings and isinstance(bindings, list):
                    for binding in bindings:
                        published = binding.get("HostPort")
                        if published and published != new_port:
                            needs_restart = True
                            logger.info(f"Puerto cambió: Docker publica {published}, BD dice {new_port}. Recreando contenedor.")
                            break
        except Exception as e:
            logger.warning(f"No se pudo comparar puertos con Docker: {e}")

    # 4. Escribir archivo squid.conf
    config_path = settings.SQUID_CONFIG_PATH
    with open(config_path, "w") as f:
        f.write(config_text)

    # 5. Validar sintaxis
    valid, msg = validate_squid_config(config_path)
    if not valid:
        return {"status": "error", "message": f"Configuración inválida: {msg}"}

    # 5b. Si el config tiene ssl-bump, necesita reinicio completo (no reconfigure)
    if "ssl-bump" in config_text:
        try:
            client = docker_sdk.from_env()
            container = client.containers.get(settings.SQUID_CONTAINER_NAME)
            container.restart(timeout=10)
            # Esperar a que arranque
            import time
            time.sleep(5)
            # Regenerar usuarios
            from app.database import SessionLocal
            from app.models.proxy_user import ProxyUser
            db2 = SessionLocal()
            try:
                users = db2.query(ProxyUser).filter(ProxyUser.enabled == True).all()
                passwd_path = Path("/etc/squid/squid_passwd")
                with open(passwd_path, "w") as f:
                    for u in users:
                        if u.htpasswd_hash:
                            f.write(f"{u.htpasswd_hash}\n")
                # Reconfigure para leer passwd
                container.exec_run(["squid", "-k", "reconfigure"])
            finally:
                db2.close()
            return {
                "status": "ok",
                "message": "Squid reiniciado con SSL Bump (configuración aplicada)",
                "needs_restart": True,
                "config_preview": config_text[:500] + "..." if len(config_text) > 500 else config_text,
            }
        except Exception as e:
            return {
                "status": "warning",
                "message": f"Config escrito pero error reiniciando: {e}",
                "needs_restart": True,
                "config_preview": config_text[:500] + "..." if len(config_text) > 500 else config_text,
            }

    # 5a. Si no tiene ssl-bump, reconfigure normal
    success, reload_msg = reload_squid()
    action = "reconfigurado"

    return {
        "status": "ok" if success else "warning",
        "message": f"Squid {action}: {reload_msg}",
        "needs_restart": needs_restart,
        "config_preview": config_text[:500] + "..." if len(config_text) > 500 else config_text,
    }


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