"""Rutas del proxy padre: salida a Internet a través de otro proxy."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.admin import Admin
from app.models.audit_log import AuditLog
from app.models.parent_proxy import ParentProxy
from app.models.squid_settings import SquidSetting
from app.services.auth_service import get_current_admin, require_writer
from app.services.config_state import mark_dirty
from app.services.parent_proxy_service import (
    probar_padre,
    validar_destino,
    validar_certificado,
    validar_auth_method_compatible,
)
from app.services.squid_names import validate_value

logger = logging.getLogger(__name__)

router = APIRouter()

# La contraseña guardada nunca se devuelve al panel: se envía este marcador, y
# si vuelve tal cual al guardar, se conserva la que ya había. Mismo criterio
# que la contraseña de enlace de LDAP.
MARCADOR = "***"


class ParentProxyIn(BaseModel):
    enabled: bool = False
    host: str | None = None
    port: int = 3128
    username: str | None = None
    password: str | None = None
    never_direct: bool = True
    direct_domains: str | None = None
    ca_cert: str | None = None
    # 'fixed' (login=user:pass, solo Basic) o 'passthru' (login=PASSTHRU
    # connection-auth=on, reenvía las credenciales del cliente tal cual —
    # la única forma de llegar a un padre que exige Digest/NTLM/Negotiate,
    # ver validar_auth_method_compatible).
    auth_method: str = "fixed"


class ParentProxyTest(BaseModel):
    host: str | None = None
    port: int = 3128
    username: str | None = None
    password: str | None = None


def _obtener_o_crear(db: Session) -> ParentProxy:
    config = db.query(ParentProxy).first()
    if not config:
        config = ParentProxy(id=1)
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


@router.get("/config")
async def get_config(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Configuración actual, con la contraseña enmascarada."""
    config = _obtener_o_crear(db)
    return {
        "enabled": config.enabled,
        "host": config.host or "",
        "port": config.port,
        "username": config.username or "",
        "password": MARCADOR if config.password else "",
        "never_direct": config.never_direct,
        "direct_domains": config.direct_domains or "",
        # El certificado no es un secreto: se devuelve entero para poder
        # revisarlo o sustituirlo desde el panel.
        "ca_cert": config.ca_cert or "",
        "auth_method": config.auth_method or "fixed",
    }


@router.put("/config")
async def update_config(
    data: ParentProxyIn,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
):
    """Guarda la configuración.

    No se comprueba aquí que el padre responda: eso se hace al aplicar, que es
    cuando el cambio afecta de verdad al tráfico. Así se puede dejar preparada
    la configuración de un proxy que todavía no esté disponible.
    """
    if data.enabled:
        valido, mensaje = validar_destino(data.host, data.port)
        if not valido:
            return {"status": "error", "message": mensaje}

        valido, mensaje = validar_auth_method_compatible(data.auth_method, db)
        if not valido:
            return {"status": "error", "message": mensaje}
    else:
        # 'none' (sin autenticación local de clientes) depende por completo de
        # que exista un padre habilitado -ver validar_proxy_auth_scheme_none-:
        # apagar el padre con 'none' todavía activo dejaría este Squid como
        # proxy abierto sin que nadie lo pidiera explícitamente.
        esquema = db.query(SquidSetting).filter(SquidSetting.key == "proxy_auth_scheme").first()
        if esquema and (esquema.value or "").strip().lower() == "none":
            return {
                "status": "error",
                "message": (
                    "No se puede desactivar el proxy padre con el esquema de "
                    "autenticación del proxy en 'none': este Squid quedaría "
                    "abierto sin ningún control de acceso. Cambia primero el "
                    "esquema a 'basic' o 'digest' en Configuración."
                ),
            }

    # Un certificado ilegible no rompe el arranque de Squid: solo deja un aviso
    # en su log y no confía en nadie, con lo que el síntoma vuelve a ser la
    # navegación HTTPS caída sin causa aparente. Mejor rechazarlo aquí.
    valido, mensaje = validar_certificado(data.ca_cert)
    if not valido:
        return {"status": "error", "message": mensaje}

    # host, username y password acaban tal cual en la directiva cache_peer del
    # squid.conf (incluida la parte login=usuario:contraseña): sin esto, un
    # salto de línea en cualquiera de los tres inserta una directiva arbitraria.
    try:
        if data.host and data.host.strip():
            validate_value(data.host, field="host del proxy padre")
        if data.username and data.username.strip():
            validate_value(data.username, field="usuario del proxy padre")
        if data.password and data.password != MARCADOR:
            validate_value(data.password, field="contraseña del proxy padre")
    except HTTPException as e:
        return {"status": "error", "message": e.detail}

    config = _obtener_o_crear(db)
    config.enabled = data.enabled
    config.host = (data.host or "").strip() or None
    config.port = data.port
    config.username = (data.username or "").strip() or None
    config.never_direct = data.never_direct
    config.direct_domains = data.direct_domains
    config.ca_cert = (data.ca_cert or "").strip() or None
    config.auth_method = data.auth_method

    # Solo se reescribe si llega una contraseña nueva de verdad.
    if data.password and data.password != MARCADOR:
        config.password = data.password
    elif not data.username:
        # Sin usuario no tiene sentido conservar una contraseña suelta.
        config.password = None

    # Nunca se registra la contraseña, solo si cambio o no -mismo criterio que
    # el resto de credenciales de terceros del proyecto.
    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="update", entity="parent_proxy", entity_id=config.id,
        new_value=(
            f"enabled={config.enabled} host={config.host} port={config.port} "
            f"auth_method={config.auth_method} "
            f"password={'(sin cambios o vacia)' if not (data.password and data.password != MARCADOR) else '(cambiada)'}"
        ),
    ))
    db.commit()
    mark_dirty()

    logger.info(
        "Proxy padre %s", "activado" if config.enabled else "desactivado"
    )
    return {"status": "ok"}


@router.post("/test")
async def test_config(
    data: ParentProxyTest,
    db: Session = Depends(get_db),
    _: Admin = Depends(require_writer),
):
    """Prueba un proxy padre sin guardarlo.

    Permite descubrir aquí que el proxy no responde, o que exige un método de
    autenticación que Squid no puede presentar, en lugar de averiguarlo cuando
    ya nadie puede navegar.
    """
    password = data.password
    if password == MARCADOR:
        guardada = db.query(ParentProxy).first()
        password = guardada.password if guardada else None

    ok, mensaje = probar_padre(
        host=data.host,
        port=data.port,
        username=(data.username or "").strip() or None,
        password=password,
    )
    return {"ok": ok, "message": mensaje}
