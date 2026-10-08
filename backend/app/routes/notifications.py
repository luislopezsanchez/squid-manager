"""Rutas de configuración y pruebas de notificaciones."""

import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.database import get_db
from app.models.admin import Admin
from app.models.audit_log import AuditLog
from app.models.notification_config import NotificationConfig
from app.models.smtp_config import SmtpConfig
from app.services.auth_service import get_current_admin, require_writer
from app.services.daily_report_service import condiciones, guardar_idioma, enviar as enviar_reporte
from app.services.notification_service import test_email, test_telegram, test_xmpp, send_email, send_telegram

router = APIRouter()


class NotificationConfigIn(BaseModel):
    email_enabled: bool = False
    email_recipients: str | None = None

    telegram_enabled: bool = False
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None

    xmpp_enabled: bool = False
    xmpp_host: str | None = Field(None, max_length=255)
    xmpp_port: int = Field(5222, ge=1, le=65535)
    xmpp_jid: str | None = Field(None, max_length=255)
    xmpp_password: str | None = None
    xmpp_encryption: str = Field("starttls", pattern=r"^(none|starttls|ssl)$")
    xmpp_verify_cert: bool = True
    xmpp_recipients: str | None = Field(None, max_length=500)
    xmpp_room: str | None = Field(None, max_length=255)

    notify_on_apply: bool = True
    notify_on_user_change: bool = False
    notify_on_acl_change: bool = False
    notify_on_rule_change: bool = False
    notify_on_security_alert: bool = True
    notify_on_node_down: bool = True
    notify_on_quota_reached: bool = True
    notify_on_blocked_access: bool = False
    blocked_threshold: int = Field(10, ge=3, le=1000)

    daily_report_enabled: bool = False
    daily_report_time: str = Field("23:55", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    # Idioma del panel al guardar: el reporte se redacta en ese idioma.
    idioma: str | None = None


class TestEmailIn(BaseModel):
    # El servidor SMTP se usa de la config ya guardada en Sistema > SMTP
    # -acá solo se prueba a qué destinatario llega, sin volver a pedir host
    # ni contraseña.
    email_recipients: str


class TestTelegramIn(BaseModel):
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None


class TestXmppIn(BaseModel):
    # Lo que el formulario tenga a la vista; lo que falte (p. ej. la contraseña ya guardada) sale de la config guardada.
    xmpp_host: str | None = None
    xmpp_port: int | None = Field(None, ge=1, le=65535)
    xmpp_jid: str | None = None
    xmpp_password: str | None = None
    xmpp_encryption: str | None = Field(None, pattern=r"^(none|starttls|ssl)$")
    xmpp_verify_cert: bool | None = None
    xmpp_recipients: str | None = None
    xmpp_room: str | None = None


# usuario@dominio (o sala@conference.dominio): sin espacios ni barras; el recurso no hace falta.
_JID = re.compile(r"^[^\s@/<>&'\"]+@[A-Za-z0-9._-]+$")


def _validar_xmpp(host, jid, recipients, room) -> str | None:
    """Devuelve el motivo del rechazo, o None si los datos son válidos."""
    if host and not re.fullmatch(r"[A-Za-z0-9._:-]+", host.strip()):
        return "El servidor XMPP debe ser un nombre de host o una IP"
    if jid and not _JID.match(jid.strip()):
        return "La cuenta XMPP (JID) debe tener la forma usuario@dominio"
    for r in [x.strip() for x in (recipients or "").split(",") if x.strip()]:
        if not _JID.match(r):
            return f"Destinatario XMPP no válido: {r}"
    if room and not _JID.match(room.strip()):
        return "La sala XMPP debe tener la forma sala@conference.dominio"
    return None


def _get_or_create_config(db: Session) -> NotificationConfig:
    config = db.query(NotificationConfig).first()
    if not config:
        config = NotificationConfig(id=1)
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


@router.get("/config")
def get_config(
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
        "xmpp_enabled": config.xmpp_enabled,
        "xmpp_host": config.xmpp_host,
        "xmpp_port": config.xmpp_port,
        "xmpp_jid": config.xmpp_jid,
        "xmpp_password_set": bool(config.xmpp_password),
        "xmpp_encryption": config.xmpp_encryption or "starttls",
        "xmpp_verify_cert": config.xmpp_verify_cert,
        "xmpp_recipients": config.xmpp_recipients,
        "xmpp_room": config.xmpp_room,
        "notify_on_apply": config.notify_on_apply,
        "notify_on_user_change": config.notify_on_user_change,
        "notify_on_acl_change": config.notify_on_acl_change,
        "notify_on_rule_change": config.notify_on_rule_change,
        "notify_on_security_alert": config.notify_on_security_alert,
        "notify_on_node_down": config.notify_on_node_down,
        "notify_on_quota_reached": config.notify_on_quota_reached,
        "notify_on_blocked_access": config.notify_on_blocked_access,
        "blocked_threshold": config.blocked_threshold,
        "daily_report_enabled": config.daily_report_enabled,
        "daily_report_time": config.daily_report_time,
        # Qué falta para poder activar el reporte diario (la pantalla lo explica).
        "daily_report_requisitos": condiciones(db),
    }


@router.put("/config")
def update_config(
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

    motivo = _validar_xmpp(data.xmpp_host, data.xmpp_jid, data.xmpp_recipients, data.xmpp_room)
    if motivo:
        raise HTTPException(400, motivo)
    xmpp_clave_cambio = bool(data.xmpp_password)
    config.xmpp_enabled = data.xmpp_enabled
    config.xmpp_host = (data.xmpp_host or "").strip() or None
    config.xmpp_port = data.xmpp_port
    config.xmpp_jid = (data.xmpp_jid or "").strip() or None
    if data.xmpp_password:
        config.xmpp_password = data.xmpp_password
    config.xmpp_encryption = data.xmpp_encryption
    config.xmpp_verify_cert = data.xmpp_verify_cert
    config.xmpp_recipients = (data.xmpp_recipients or "").strip() or None
    config.xmpp_room = (data.xmpp_room or "").strip() or None

    config.notify_on_apply = data.notify_on_apply
    config.notify_on_user_change = data.notify_on_user_change
    config.notify_on_acl_change = data.notify_on_acl_change
    config.notify_on_rule_change = data.notify_on_rule_change
    config.notify_on_security_alert = data.notify_on_security_alert
    config.notify_on_node_down = data.notify_on_node_down
    config.notify_on_quota_reached = data.notify_on_quota_reached
    config.notify_on_blocked_access = data.notify_on_blocked_access
    config.blocked_threshold = data.blocked_threshold
    if data.daily_report_enabled and not condiciones(db)["ok"]:
        raise HTTPException(
            400,
            "Para activar el reporte diario hace falta un servidor SMTP configurado y un correo en la cuenta de administrador.",
        )
    config.daily_report_enabled = data.daily_report_enabled
    config.daily_report_time = data.daily_report_time
    if data.idioma:
        guardar_idioma(db, data.idioma)

    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="update", entity="notification_config", entity_id=config.id,
        new_value=(
            f"email_enabled={config.email_enabled} "
            f"telegram_enabled={config.telegram_enabled} "
            f"telegram_bot_token={'(cambiado)' if telegram_token_cambio else '(sin cambios)'} "
            f"xmpp_enabled={config.xmpp_enabled} xmpp_host={config.xmpp_host} xmpp_jid={config.xmpp_jid} "
            f"xmpp_password={'(cambiada)' if xmpp_clave_cambio else '(sin cambios)'}"
        ),
    ))
    db.commit()
    return {"status": "ok", "message": "Configuración de notificaciones guardada"}


@router.post("/test-email")
def test_email_endpoint(
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
def test_telegram_endpoint(
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


@router.post("/test-xmpp")
def test_xmpp_endpoint(
    data: TestXmppIn,
    db: Session = Depends(get_db),
    _: Admin = Depends(require_writer),
):
    """Enviar un mensaje de prueba por XMPP.

    Usa los datos del formulario si vienen; lo que falte (típicamente la contraseña
    ya guardada) sale de la configuración guardada.
    """
    saved = _get_or_create_config(db)

    def _o(nuevo, guardado):
        return nuevo if nuevo not in (None, "") else guardado

    host = _o(data.xmpp_host, saved.xmpp_host)
    jid = _o(data.xmpp_jid, saved.xmpp_jid)
    recipients = _o(data.xmpp_recipients, saved.xmpp_recipients)
    room = _o(data.xmpp_room, saved.xmpp_room)
    motivo = _validar_xmpp(host, jid, recipients, room)
    if motivo:
        return {"ok": False, "message": motivo}

    class _TmpConfig:
        xmpp_enabled = True

    tmp = _TmpConfig()
    tmp.xmpp_host = host
    tmp.xmpp_port = _o(data.xmpp_port, saved.xmpp_port) or 5222
    tmp.xmpp_jid = jid
    tmp.xmpp_password = _o(data.xmpp_password, saved.xmpp_password)
    tmp.xmpp_encryption = _o(data.xmpp_encryption, saved.xmpp_encryption) or "starttls"
    tmp.xmpp_verify_cert = saved.xmpp_verify_cert if data.xmpp_verify_cert is None else data.xmpp_verify_cert
    tmp.xmpp_recipients = recipients
    tmp.xmpp_room = room
    return test_xmpp(tmp)


@router.post("/daily-report/send-now")
def enviar_reporte_ahora(
    db: Session = Depends(get_db),
    _: Admin = Depends(require_writer),
):
    """Manda el reporte diario ahora mismo (las últimas 24 h) para ver cómo queda."""
    r = enviar_reporte(db)
    if not r["ok"] and r["message"].startswith("Falta configurar"):
        raise HTTPException(400, r["message"])  # así se traduce al idioma del panel
    return r
