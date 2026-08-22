"""Servicio de notificaciones: envío de alertas por email y Telegram."""

import logging
import smtplib
import urllib.parse
import urllib.request
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from types import SimpleNamespace

logger = logging.getLogger(__name__)

# Mapa de eventos a atributos de config
EVENT_CONFIG_MAP = {
    "apply": "notify_on_apply",
    "user_change": "notify_on_user_change",
    "acl_change": "notify_on_acl_change",
    "rule_change": "notify_on_rule_change",
    "security_alert": "notify_on_security_alert",
}


def _snapshot_config(config) -> SimpleNamespace:
    """Crea una copia plana de la config para usarla fuera de la sesión de BD."""
    return SimpleNamespace(
        email_enabled=config.email_enabled,
        smtp_host=config.smtp_host,
        smtp_port=config.smtp_port,
        smtp_user=config.smtp_user,
        smtp_password=config.smtp_password,
        smtp_from=config.smtp_from,
        smtp_encryption=config.smtp_encryption,
        email_recipients=config.email_recipients,
        telegram_enabled=config.telegram_enabled,
        telegram_bot_token=config.telegram_bot_token,
        telegram_chat_id=config.telegram_chat_id,
    )


def queue_notification(background_tasks, db, event_type: str, subject: str, message: str):
    """Encarga el envío de una notificación en segundo plano si está habilitada.

    - Verifica que el evento esté habilitado en la config (notify_on_*).
    - Verifica que al menos un canal (email o Telegram) esté habilitado.
    - Si corresponde, agrega un background task para enviar sin bloquear la petición.
    """
    from app.models.notification_config import NotificationConfig

    config = db.query(NotificationConfig).first()
    if not config:
        return

    attr = EVENT_CONFIG_MAP.get(event_type)
    if attr and not getattr(config, attr, False):
        return

    if not (config.email_enabled or config.telegram_enabled):
        return

    snapshot = _snapshot_config(config)
    background_tasks.add_task(notify, snapshot, subject, message)


def send_email(config, subject: str, body: str) -> tuple[bool, str]:
    """Envía un email usando SMTP configurado.

    Devuelve (ok, mensaje) donde mensaje describe el resultado o el error.
    """
    if not config.email_enabled:
        return False, "Notificaciones por email deshabilitadas"
    if not config.smtp_host:
        return False, "Falta el servidor SMTP (host)"
    if not config.email_recipients:
        return False, "Falta el destinatario (email_recipients)"

    encryption = (config.smtp_encryption or "starttls").lower()

    try:
        msg = MIMEMultipart()
        from_addr = config.smtp_from or config.smtp_user or "squidmanager@localhost"
        msg["From"] = from_addr
        msg["To"] = config.email_recipients
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        recipients = [r.strip() for r in config.email_recipients.split(",") if r.strip()]

        if not recipients:
            return False, "No hay destinatarios válidos"

        # Conexión según el método de cifrado
        if encryption == "ssl":
            # SSL/TLS implícito (puerto 465)
            server = smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, timeout=15)
        elif encryption == "starttls":
            # STARTTLS (puerto 587)
            server = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=15)
            server.ehlo()
            server.starttls()
            server.ehlo()
        else:
            # Sin cifrado
            server = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=15)
            server.ehlo()

        if config.smtp_user:
            server.login(config.smtp_user, config.smtp_password or "")

        server.sendmail(from_addr, recipients, msg.as_string())
        server.quit()
        logger.info(f"Email enviado a {len(recipients)} destinatarios")
        return True, f"Email enviado a {len(recipients)} destinatario(s)"
    except smtplib.SMTPAuthenticationError:
        return False, "Error de autenticación SMTP: usuario o contraseña incorrectos"
    except smtplib.SMTPException as e:
        return False, f"Error SMTP: {e}"
    except Exception as e:
        return False, f"Error de conexión: {e}"


def send_telegram(config, message: str) -> tuple[bool, str]:
    """Envía un mensaje por Telegram usando el bot configurado."""
    if not config.telegram_enabled:
        return False, "Notificaciones por Telegram deshabilitadas"
    if not config.telegram_bot_token or not config.telegram_chat_id:
        return False, "Falta el token del bot o el chat_id de Telegram"

    try:
        url = f"https://api.telegram.org/bot{config.telegram_bot_token}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": config.telegram_chat_id,
            "text": message,
            "parse_mode": "HTML",
        }).encode()
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode()
        logger.info("Mensaje de Telegram enviado")
        # Verificar respuesta de la API de Telegram
        import json
        resp_json = json.loads(body)
        if resp_json.get("ok"):
            return True, "Mensaje de Telegram enviado"
        return False, f"Error de Telegram: {resp_json.get('description', 'respuesta no válida')}"
    except Exception as e:
        return False, f"Error enviando Telegram: {e}"


def notify(config, subject: str, message: str) -> dict:
    """Envía notificación por email y/o Telegram según configuración."""
    results = {"email": False, "telegram": False}

    if config.email_enabled:
        ok, _ = send_email(config, subject, message)
        results["email"] = ok

    if config.telegram_enabled:
        full_message = f"<b>{subject}</b>\n\n{message}"
        ok, _ = send_telegram(config, full_message)
        results["telegram"] = ok

    return results


def test_email(config) -> dict:
    """Prueba el envío de email."""
    ok, message = send_email(
        config,
        "SquidManager - Prueba de notificación",
        "Este es un correo de prueba de SquidManager.\n\nSi recibes esto, la configuración SMTP es correcta.",
    )
    return {"ok": ok, "message": message}


def test_telegram(config) -> dict:
    """Prueba el envío por Telegram."""
    ok, message = send_telegram(
        config,
        "SquidManager - Prueba de notificación\n\nSi recibes esto, la configuración de Telegram es correcta.",
    )
    return {"ok": ok, "message": message}
