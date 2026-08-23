"""Rutas de configuración y prueba del reenvío de logs a syslog externo."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.admin import Admin
from app.models.audit_log import AuditLog
from app.models.syslog_config import SyslogConfig
from app.services.auth_service import get_current_admin, require_writer
from app.services.syslog_service import send_test_message

router = APIRouter()


class SyslogConfigIn(BaseModel):
    enabled: bool = False
    host: str | None = None
    port: int = 514
    protocol: str = "udp"       # udp | tcp
    rfc_format: str = "rfc3164"  # rfc3164 | rfc5424
    facility: str = "local0"
    log_format: str = "raw"     # raw | ndjson


class SyslogTestIn(BaseModel):
    host: str
    port: int = 514
    protocol: str = "udp"
    rfc_format: str = "rfc3164"
    facility: str = "local0"
    log_format: str = "raw"


def _get_or_create_config(db: Session) -> SyslogConfig:
    config = db.query(SyslogConfig).first()
    if not config:
        config = SyslogConfig(id=1)
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


@router.get("/config")
async def get_config(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Configuración actual del reenvío a syslog. Apagado por defecto."""
    config = _get_or_create_config(db)
    return {
        "enabled": config.enabled,
        "host": config.host,
        "port": config.port,
        "protocol": config.protocol,
        "rfc_format": config.rfc_format,
        "facility": config.facility,
        "log_format": config.log_format,
    }


@router.put("/config")
async def update_config(
    data: SyslogConfigIn,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
):
    """Guarda la configuración del reenvío a syslog.

    El hilo de fondo la relee sola cada pocos segundos: no hace falta
    reiniciar nada para que un cambio (incluido apagarlo) surta efecto.
    """
    if data.protocol not in ("udp", "tcp"):
        raise HTTPException(400, detail="protocol debe ser 'udp' o 'tcp'")
    if data.rfc_format not in ("rfc3164", "rfc5424"):
        raise HTTPException(400, detail="rfc_format debe ser 'rfc3164' o 'rfc5424'")
    if data.log_format not in ("raw", "ndjson"):
        raise HTTPException(400, detail="log_format debe ser 'raw' o 'ndjson'")
    if data.enabled and not data.host:
        raise HTTPException(400, detail="Hace falta un host de destino para habilitar el reenvío")

    config = _get_or_create_config(db)
    was_enabled = config.enabled
    config.enabled = data.enabled
    config.host = data.host
    config.port = data.port
    config.protocol = data.protocol
    config.rfc_format = data.rfc_format
    config.facility = data.facility
    config.log_format = data.log_format

    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="update", entity="syslog_config",
        new_value=f"{data.host}:{data.port}/{data.protocol}" if data.host else None,
    ))
    db.commit()

    estado = "habilitado" if data.enabled else "deshabilitado"
    aviso = f" ({estado})" if was_enabled != data.enabled else ""
    return {"status": "ok", "message": f"Configuración de syslog guardada{aviso}"}


@router.post("/test")
async def test_syslog(
    data: SyslogTestIn,
    _: Admin = Depends(require_writer),
):
    """Envía un mensaje de prueba al destino indicado, sin necesidad de
    guardar la configuración antes — así se puede probar un host antes de
    activarlo de verdad."""
    ok, message = send_test_message(SyslogConfig(
        host=data.host, port=data.port, protocol=data.protocol,
        rfc_format=data.rfc_format, facility=data.facility, log_format=data.log_format,
    ))
    return {"status": "ok" if ok else "error", "message": message}
