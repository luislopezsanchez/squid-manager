"""Terminar la conexión ya abierta de un cliente contra Squid.

No es una operación de Squid en sí (no hay ninguna directiva de squid.conf
para esto, confirmado contra la lista squid-users -ver docs/project-log.md):
opera sobre la tabla de conexiones del kernel, por eso vive en el adaptador
de runtime (app/services/runtime/) en vez de en squid_service.py.
"""

import ipaddress

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.admin import Admin
from app.models.audit_log import AuditLog
from app.services.auth_service import require_writer

router = APIRouter()


class DisconnectRequest(BaseModel):
    ip: str


@router.post("/disconnect")
def disconnect_client(
    data: DisconnectRequest,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
):
    """Corta las conexiones TCP ya abiertas de un cliente, por IP.

    Solo afecta a lo que ya está en curso: no bloquea peticiones futuras de
    ese cliente -para eso hace falta además deshabilitarlo (ProxyUser) o una
    regla de acceso que lo excluya.
    """
    try:
        ipaddress.ip_address(data.ip)
    except ValueError:
        raise HTTPException(400, detail=f"'{data.ip}' no es una dirección IP válida.")

    from app.services.runtime import get_runtime

    ok, mensaje = get_runtime().disconnect_client(data.ip)

    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="disconnect", entity="network", new_value=data.ip,
        old_value=mensaje if not ok else None,
    ))
    db.commit()

    if not ok:
        raise HTTPException(500, detail=mensaje)
    return {"status": "ok", "message": mensaje}
