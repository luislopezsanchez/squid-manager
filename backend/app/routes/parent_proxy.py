"""Rutas del proxy padre: salida a Internet a través de otro proxy."""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.admin import Admin
from app.models.parent_proxy import ParentProxy
from app.services.auth_service import get_current_admin, require_writer
from app.services.config_state import mark_dirty
from app.services.parent_proxy_service import (
    probar_padre,
    validar_destino,
    validar_certificado,
)

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

    # Un certificado ilegible no rompe el arranque de Squid: solo deja un aviso
    # en su log y no confía en nadie, con lo que el síntoma vuelve a ser la
    # navegación HTTPS caída sin causa aparente. Mejor rechazarlo aquí.
    valido, mensaje = validar_certificado(data.ca_cert)
    if not valido:
        return {"status": "error", "message": mensaje}

    config = _obtener_o_crear(db)
    config.enabled = data.enabled
    config.host = (data.host or "").strip() or None
    config.port = data.port
    config.username = (data.username or "").strip() or None
    config.never_direct = data.never_direct
    config.direct_domains = data.direct_domains
    config.ca_cert = (data.ca_cert or "").strip() or None

    # Solo se reescribe si llega una contraseña nueva de verdad.
    if data.password and data.password != MARCADOR:
        config.password = data.password
    elif not data.username:
        # Sin usuario no tiene sentido conservar una contraseña suelta.
        config.password = None

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
