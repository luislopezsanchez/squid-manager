"""Ruta del formulario de Contacto (Ayuda > Contacto).

Reporta errores o sugerencias sobre SquidManager mismo -no es un canal de
soporte del proxy de la red del admin, es soporte del producto-. El mensaje
se guarda siempre en `contact_messages`; el envío por email es best-effort,
usando el SMTP que el admin ya tenga configurado en Notificaciones.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.database import get_db
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
