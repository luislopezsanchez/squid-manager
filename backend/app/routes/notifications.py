"""Rutas de configuración y pruebas de notificaciones."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.admin import Admin
from app.models.audit_log import AuditLog
from app.models.notification_config import NotificationConfig
from app.models.smtp_config import SmtpConfig
from app.services.auth_service import get_current_admin, require_writer
from app.services.notification_service import test_email, test_telegram, send_email, send_telegram

router = APIRouter()


class NotificationConfigIn(BaseModel):
    email_enabled: bool = False
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
    # El servidor SMTP se usa de la config ya guardada en Sistema > SMTP
    # -acá solo se prueba a qué destinatario llega, sin volver a pedir host
    # ni contraseña.
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


@router.get("/config")
async def get_config(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Obtener configuración de notificaciones (sin secretos completos)."""
    config = _get_or_create_config(db)
    return {
        "email_enabled": config.email_enabled,
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
    current_admin: Admin = Depends(require_writer),
):
    """Actualizar configuración de notificaciones."""
    config = _get_or_create_config(db)
    telegram_token_cambio = bool(data.telegram_bot_token)

    config.email_enabled = data.email_enabled
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

    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="update", entity="notification_config", entity_id=config.id,
        new_value=(
            f"email_enabled={config.email_enabled} "
            f"telegram_enabled={config.telegram_enabled} "
            f"telegram_bot_token={'(cambiado)' if telegram_token_cambio else '(sin cambios)'}"
        ),
    ))
    db.commit()
    return {"status": "ok", "message": "Configuración de notificaciones guardada"}


@router.post("/test-email")
async def test_email_endpoint(
    data: TestEmailIn,
    db: Session = Depends(get_db),
    _: Admin = Depends(require_writer),
):
    """Enviar email de prueba al destinatario indicado, usando el servidor
    SMTP ya guardado en Sistema > SMTP (no hay campos SMTP en este formulario
    desde que el servidor se separó a su propia sección -ver SmtpConfig)."""
    smtp = db.query(SmtpConfig).first()
    if not smtp or not smtp.smtp_host:
        return {"ok": False, "message": "No hay un servidor SMTP configurado en Sistema > SMTP"}

    class _TmpConfig:
        email_enabled = True

    tmp = _TmpConfig()
    tmp.smtp_host = smtp.smtp_host
    tmp.smtp_port = smtp.smtp_port
    tmp.smtp_user = smtp.smtp_user
    tmp.smtp_password = smtp.smtp_password
    tmp.smtp_from = smtp.smtp_from
    tmp.smtp_encryption = smtp.smtp_encryption
    tmp.email_recipients = data.email_recipients

    return test_email(tmp)


@router.post("/test-telegram")
async def test_telegram_endpoint(
    data: TestTelegramIn,
    db: Session = Depends(get_db),
    _: Admin = Depends(require_writer),
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
