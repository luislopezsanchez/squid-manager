"""Ruta del formulario de Contacto (Ayuda > Contacto).

Reporta errores o sugerencias sobre SquidManager mismo -no es un canal de
soporte del proxy de la red del admin, es soporte del producto-. El mensaje
se guarda siempre en `contact_messages`; el envío por email es best-effort,
usando el SMTP que el admin ya tenga configurado en Notificaciones.
"""

import re
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.database import get_db
from app.utils import utcnow
from app.models.admin import Admin
from app.models.contact_message import ContactMessage
from app.models.smtp_config import SmtpConfig
from app.services.auth_service import get_current_admin
from app.services.notification_service import send_contact_message

router = APIRouter()

CATEGORIAS_VALIDAS = {"error", "sugerencia", "otro"}


class ContactoIn(BaseModel):
    categoria: str = Field(..., description="error | sugerencia | otro")
    mensaje: str = Field(..., min_length=1, max_length=5000)
    email_respuesta: str | None = None


@router.post("")
def enviar_contacto(datos: ContactoIn, db: Session = Depends(get_db), admin: Admin = Depends(get_current_admin)):
    categoria = datos.categoria if datos.categoria in CATEGORIAS_VALIDAS else "otro"
    if datos.email_respuesta and not re.fullmatch(r"[^\s@<>\",;]{1,64}@[^\s@<>\",;]{1,255}", datos.email_respuesta):
        raise HTTPException(400, detail="El email de respuesta no es válido.")
    # Tope sencillo contra el envío en bucle (cada mensaje dispara un correo): 5 cada 10 minutos por administrador.
    desde = utcnow() - timedelta(minutes=10)
    recientes = db.query(ContactMessage).filter(
        ContactMessage.admin_username == admin.username, ContactMessage.created_at >= desde).count()
    if recientes >= 5:
        raise HTTPException(429, detail="Has enviado varios mensajes seguidos. Espera unos minutos antes de enviar otro.")

    config = db.query(SmtpConfig).first()
    asunto = f"[SquidManager] Contacto ({categoria}) de {admin.username}"
    cuerpo = (
        f"Categoría: {categoria}\n"
        f"Administrador: {admin.username}\n"
        f"Email de respuesta: {datos.email_respuesta or '(no indicado)'}\n\n"
        f"{datos.mensaje}"
    )
    enviado, detalle = send_contact_message(config, asunto, cuerpo, reply_to=datos.email_respuesta)

    registro = ContactMessage(
        admin_username=admin.username,
        categoria=categoria,
        mensaje=datos.mensaje,
        email_respuesta=datos.email_respuesta,
        enviado_por_email=enviado,
        detalle_envio=detalle,
    )
    db.add(registro)
    db.commit()

    return {"guardado": True, "enviado_por_email": enviado, "detalle": detalle}


_INICIO = None
_INFO_CACHE: dict = {}


@router.get("/info")
def informacion_de_la_instalacion(_: Admin = Depends(get_current_admin)):
    """Datos técnicos NO sensibles de esta instalación (versión, modo de despliegue, versión de Squid,
    sistema operativo) para adjuntarlos a un reporte: quien da soporte siempre los pide primero.
    Nunca incluye direcciones, nombres de usuario, rutas internas ni claves."""
    import os
    import platform
    import subprocess
    import time

    from app.config import settings

    global _INICIO
    if _INICIO is None:
        _INICIO = time.time()
    if "squid" not in _INFO_CACHE:
        try:
            salida = subprocess.run(["squid", "-v"], capture_output=True, text=True, timeout=5).stdout.splitlines()
            _INFO_CACHE["squid"] = salida[0].replace("Squid Cache: Version ", "") if salida else "—"
        except Exception:
            _INFO_CACHE["squid"] = "—"
        so = platform.system()
        try:
            for linea in open("/etc/os-release", encoding="utf-8"):
                if linea.startswith("PRETTY_NAME="):
                    so = linea.split("=", 1)[1].strip().strip('"')
        except OSError:
            pass
        _INFO_CACHE["so"] = so
    return {
        "app_version": settings.APP_VERSION,
        "deploy_mode": os.environ.get("DEPLOY_MODE", "docker"),
        "squid_version": _INFO_CACHE["squid"],
        "sistema": _INFO_CACHE["so"],
        "python": platform.python_version(),
        "panel_activo_desde_horas": round((time.time() - _INICIO) / 3600, 1),
    }
