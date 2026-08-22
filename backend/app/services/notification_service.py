"""Servicio de notificaciones: envío de alertas por email y Telegram."""

import logging
import smtplib
import urllib.parse
import urllib.request
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)


def send_email(config, subject: str, body: str) -> bool:
    """Envía un email usando SMTP configurado."""
    if not config.email_enabled:
        return False
    if not config.smtp_host or not config.email_recipients:
        logger.warning("Email no enviado: falta smtp_host o recipients")
        return False

    try:
        msg = MIMEMultipart()
        msg["From"] = config.smtp_from or config.smtp_user
        msg["To"] = config.email_recipients
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        recipients = [r.strip() for r in config.email_recipients.split(",") if r.strip()]

        server = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=10)
        server.ehlo()
        if config.smtp_user:
            server.starttls()
            server.login(config.smtp_user, config.smtp_password or "")
        server.sendmail(msg["From"], recipients, msg.as_string())
        server.quit()
        logger.info(f"Email enviado a {len(recipients)} destinatarios")
        return True
    except Exception as e:
        logger.error(f"Error enviando email: {e}")
        return False


def send_telegram(config, message: str) -> bool:
    """Envía un mensaje por Telegram usando el bot configurado."""
    if not config.telegram_enabled:
        return False
    if not config.telegram_bot_token or not config.telegram_chat_id:
        logger.warning("Telegram no enviado: falta bot_token o chat_id")
        return False

    try:
        url = f"https://api.telegram.org/bot{config.telegram_bot_token}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": config.telegram_chat_id,
            "text": message,
            "parse_mode": "HTML",
        }).encode()
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
        logger.info("Mensaje de Telegram enviado")
        return True
    except Exception as e:
        logger.error(f"Error enviando Telegram: {e}")
        return False


def notify(config, subject: str, message: str) -> dict:
    """Envía notificación por email y/o Telegram según configuración.

    Devuelve un dict con el resultado de cada canal.
    """
    results = {"email": False, "telegram": False}

    if config.email_enabled:
        results["email"] = send_email(config, subject, message)

    if config.telegram_enabled:
        # Telegram usa el asunto como parte del mensaje
        full_message = f"<b>{subject}</b>\n\n{message}"
        results["telegram"] = send_telegram(config, full_message)

    return results


def test_email(config) -> dict:
    """Prueba el envío de email."""
    ok = send_email(config, "SquidManager - Prueba de notificación",
                    "Este es un correo de prueba de SquidManager.\n\nSi recibes esto, la configuración SMTP es correcta.")
    return {"ok": ok, "message": "Email de prueba enviado" if ok else "Error enviando email. Revisa los logs."}


def test_telegram(config) -> dict:
    """Prueba el envío por Telegram."""
    ok = send_telegram(config, "SquidManager - Prueba de notificación\n\nSi recibes esto, la configuración de Telegram es correcta.")
    return {"ok": ok, "message": "Mensaje de prueba enviado" if ok else "Error enviando Telegram. Revisa los logs."}
