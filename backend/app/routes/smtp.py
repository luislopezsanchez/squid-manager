"""Ruta de configuración del servidor SMTP (Sistema > SMTP).

Servidor de correo saliente compartido: lo usan Notificaciones (alertas de
Squid) y Contacto (soporte del producto) -antes vivía duplicado dentro de
notification_config, ver migración 0022 y app/models/smtp_config.py.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.admin import Admin
from app.models.audit_log import AuditLog
from app.models.smtp_config import SmtpConfig
from app.services.auth_service import get_current_admin, require_writer
from app.services.notification_service import test_email

router = APIRouter()


class SmtpConfigIn(BaseModel):
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_encryption: str = "starttls"  # none, starttls, ssl


class TestSmtpIn(SmtpConfigIn):
    destinatario_prueba: str


def _get_or_create_config(db: Session) -> SmtpConfig:
    config = db.query(SmtpConfig).first()
    if not config:
        config = SmtpConfig(id=1)
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


@router.get("/config")
async def get_config(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Obtener configuración SMTP (sin la contraseña completa)."""
    config = _get_or_create_config(db)
    return {
        "smtp_host": config.smtp_host,
        "smtp_port": config.smtp_port,
        "smtp_user": config.smtp_user,
        "smtp_password_set": bool(config.smtp_password),
        "smtp_from": config.smtp_from,
        "smtp_encryption": config.smtp_encryption or "starttls",
    }


@router.put("/config")
async def update_config(
    data: SmtpConfigIn,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
):
    """Actualizar la configuración SMTP."""
    config = _get_or_create_config(db)
    password_cambio = bool(data.smtp_password)

    config.smtp_host = data.smtp_host
    config.smtp_port = data.smtp_port
    config.smtp_user = data.smtp_user
    if data.smtp_password is not None and data.smtp_password != "":
        config.smtp_password = data.smtp_password
    config.smtp_from = data.smtp_from
    config.smtp_encryption = data.smtp_encryption

    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="update", entity="smtp_config", entity_id=config.id,
        new_value=(
            f"smtp_host={config.smtp_host} "
            f"smtp_password={'(cambiada)' if password_cambio else '(sin cambios)'}"
        ),
    ))
    db.commit()
    return {"status": "ok", "message": "Configuración SMTP guardada"}


@router.post("/test")
async def test_smtp_endpoint(
    data: TestSmtpIn,
    db: Session = Depends(get_db),
    _: Admin = Depends(require_writer),
):
    """Envía un correo de prueba con los datos del formulario (no hace falta
    guardar antes), al destinatario indicado.

    Si el campo de contraseña llega vacío -lo normal despues de guardar, el
    formulario la limpia y solo muestra "(guardada)"-, se usa la contraseña
    ya guardada en vez de intentar autenticar sin ninguna. Sin esto, probar
    justo despues de guardar fallaba con un error de autenticacion enganoso:
    la config real funcionaba, pero el formulario mandaba una contraseña
    vacia (reportado en vivo por el usuario, 2026-09-12).
    """
    password = data.smtp_password
    if not password:
        guardado = db.query(SmtpConfig).first()
        password = guardado.smtp_password if guardado else None

    class _TmpConfig:
        email_enabled = True

    tmp = _TmpConfig()
    tmp.smtp_host = data.smtp_host
    tmp.smtp_port = data.smtp_port
    tmp.smtp_user = data.smtp_user
    tmp.smtp_password = password
    tmp.smtp_from = data.smtp_from
    tmp.smtp_encryption = data.smtp_encryption
    tmp.email_recipients = data.destinatario_prueba

    return test_email(tmp)
