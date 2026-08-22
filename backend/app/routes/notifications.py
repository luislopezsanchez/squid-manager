"""Rutas de configuración y pruebas de notificaciones."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.admin import Admin
from app.models.notification_config import NotificationConfig
from app.services.auth_service import get_current_admin
from app.services.notification_service import test_email, test_telegram

router = APIRouter()


class NotificationConfigIn(BaseModel):
    email_enabled: bool = False
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    email_recipients: str | None = None

    telegram_enabled: bool = False
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None

    notify_on_apply: bool = True
    notify_on_user_change: bool = False
    notify_on_acl_change: bool = False
    notify_on_rule_change: bool = False
    notify_on_security_alert: bool = True


def _get_or_create_config(db: Session) -> NotificationConfig:
    config = db.query(NotificationConfig).first()
    if not config:
        config = NotificationConfig(id=1)
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


def _require_admin(admin: Admin = Depends(get_current_admin)) -> Admin:
    if admin.role == "viewer":
        raise HTTPException(status_code=403, detail="Los viewers no pueden modificar configuraciones")
    return admin


@router.get("/config")
async def get_config(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Obtener configuración de notificaciones (sin secretos completos)."""
    config = _get_or_create_config(db)
    return {
        "email_enabled": config.email_enabled,
        "smtp_host": config.smtp_host,
        "smtp_port": config.smtp_port,
        "smtp_user": config.smtp_user,
        "smtp_password_set": bool(config.smtp_password),
        "smtp_from": config.smtp_from,
        "email_recipients": config.email_recipients,
        "telegram_enabled": config.telegram_enabled,
        "telegram_bot_token_set": bool(config.telegram_bot_token),
        "telegram_chat_id": config.telegram_chat_id,
        "notify_on_apply": config.notify_on_apply,
        "notify_on_user_change": config.notify_on_user_change,
        "notify_on_acl_change": config.notify_on_acl_change,
        "notify_on_rule_change": config.notify_on_rule_change,
        "notify_on_security_alert": config.notify_on_security_alert,
    }


@router.put("/config")
async def update_config(
    data: NotificationConfigIn,
    db: Session = Depends(get_db),
    _: Admin = Depends(_require_admin),
):
    """Actualizar configuración de notificaciones."""
    config = _get_or_create_config(db)

    config.email_enabled = data.email_enabled
    config.smtp_host = data.smtp_host
    config.smtp_port = data.smtp_port
    config.smtp_user = data.smtp_user
    if data.smtp_password is not None and data.smtp_password != "":
        config.smtp_password = data.smtp_password
    config.smtp_from = data.smtp_from
    config.email_recipients = data.email_recipients

    config.telegram_enabled = data.telegram_enabled
    if data.telegram_bot_token is not None and data.telegram_bot_token != "":
        config.telegram_bot_token = data.telegram_bot_token
    config.telegram_chat_id = data.telegram_chat_id

    config.notify_on_apply = data.notify_on_apply
    config.notify_on_user_change = data.notify_on_user_change
    config.notify_on_acl_change = data.notify_on_acl_change
    config.notify_on_rule_change = data.notify_on_rule_change
    config.notify_on_security_alert = data.notify_on_security_alert

    db.commit()
    return {"status": "ok", "message": "Configuración de notificaciones guardada"}


@router.post("/test-email")
async def test_email_endpoint(
    db: Session = Depends(get_db),
    _: Admin = Depends(_require_admin),
):
    """Enviar email de prueba."""
    config = _get_or_create_config(db)
    return test_email(config)


@router.post("/test-telegram")
async def test_telegram_endpoint(
    db: Session = Depends(get_db),
    _: Admin = Depends(_require_admin),
):
    """Enviar mensaje de prueba por Telegram."""
    config = _get_or_create_config(db)
    return test_telegram(config)
