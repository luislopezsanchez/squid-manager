"""Rutas de configuración y pruebas de notificaciones."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.admin import Admin
from app.models.notification_config import NotificationConfig
from app.services.auth_service import get_current_admin
from app.services.notification_service import test_email, test_telegram, send_email, send_telegram

router = APIRouter()


class NotificationConfigIn(BaseModel):
    email_enabled: bool = False
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_encryption: str = "starttls"  # none, starttls, ssl
    email_recipients: str | None = None

    telegram_enabled: bool = False
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None

    notify_on_apply: bool = True
    notify_on_user_change: bool = False
    notify_on_acl_change: bool = False
    notify_on_rule_change: bool = False
    notify_on_security_alert: bool = True


class TestEmailIn(BaseModel):
    smtp_host: str
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_from: str | None = None
    smtp_encryption: str = "starttls"
    email_recipients: str


class TestTelegramIn(BaseModel):
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None


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
        "smtp_encryption": config.smtp_encryption or "starttls",
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
    config.smtp_encryption = data.smtp_encryption
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
    data: TestEmailIn,
    _: Admin = Depends(_require_admin),
):
    """Enviar email de prueba usando los datos del formulario (no la config guardada).

    Acepta los datos SMTP en el body para probar la configuración actual del formulario,
    sin necesidad de guardar primero.
    """
    # Construir un objeto temporal con los datos recibidos
    class _TmpConfig:
        email_enabled = True

    tmp = _TmpConfig()
    tmp.smtp_host = data.smtp_host
    tmp.smtp_port = data.smtp_port
    tmp.smtp_user = data.smtp_user
    tmp.smtp_password = data.smtp_password
    tmp.smtp_from = data.smtp_from
    tmp.smtp_encryption = data.smtp_encryption
    tmp.email_recipients = data.email_recipients

    return test_email(tmp)


@router.post("/test-telegram")
async def test_telegram_endpoint(
    data: TestTelegramIn,
    db: Session = Depends(get_db),
    _: Admin = Depends(_require_admin),
):
    """Enviar mensaje de prueba por Telegram.

    Usa el token/chat_id del formulario si se proporcionan; si están vacíos,
    usa la configuración guardada en la base de datos.
    """
    saved = _get_or_create_config(db)

    class _TmpConfig:
        telegram_enabled = True

    tmp = _TmpConfig()
    tmp.telegram_bot_token = data.telegram_bot_token or saved.telegram_bot_token
    tmp.telegram_chat_id = data.telegram_chat_id or saved.telegram_chat_id

    return test_telegram(tmp)
