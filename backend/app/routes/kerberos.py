"""Rutas de configuración de Kerberos (autenticación Negotiate contra AD)."""

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import PlainTextResponse
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.admin import Admin
from app.models.kerberos_config import KerberosConfig
from app.services.auth_service import get_current_admin, require_writer
from app.services.config_state import mark_dirty
from app.services.kerberos_service import validar_keytab
from app.services.squid_names import validate_value
from app.utils import utcnow

logger = logging.getLogger(__name__)
router = APIRouter()

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"

# Un keytab real pesa unos pocos KB (una entrada por combinación de principal
# y tipo de cifrado). Este tope solo evita que alguien suba un archivo enorme
# por error o a propósito.
MAX_KEYTAB_BYTES = 256 * 1024


def _obtener_o_crear(db: Session) -> KerberosConfig:
    config = db.query(KerberosConfig).first()
    if not config:
        config = KerberosConfig(id=1)
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


class KerberosConfigIn(BaseModel):
    enabled: bool = False
    realm: str | None = None
    proxy_fqdn: str | None = None


@router.get("/config")
async def get_config(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Configuración actual. El keytab nunca se devuelve, solo si hay uno."""
    config = _obtener_o_crear(db)
    return {
        "enabled": config.enabled,
        "realm": config.realm or "",
        "proxy_fqdn": config.proxy_fqdn or "",
        "keytab_uploaded": bool(config.keytab_data),
        "keytab_filename": config.keytab_filename or "",
        "keytab_uploaded_at": config.keytab_uploaded_at,
    }


@router.put("/config")
async def update_config(
    data: KerberosConfigIn,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
):
    """Guarda realm y FQDN. El keytab se sube aparte, en /keytab.

    No se comprueba aquí que el keytab funcione de verdad: eso solo se puede
    saber en el momento en que un cliente real presenta un ticket. Al aplicar
    se valida al menos que el archivo tenga la forma de un keytab.
    """
    # Ambos van tal cual en la directiva auth_param negotiate (-s HTTP/fqdn@REALM):
    # sin esto, un salto de línea en cualquiera de los dos inyecta una
    # directiva arbitraria en el squid.conf generado.
    realm = validate_value(data.realm, field="realm de Kerberos") if data.realm else None
    proxy_fqdn = validate_value(data.proxy_fqdn, field="FQDN del proxy") if data.proxy_fqdn else None

    if data.enabled and not (realm and proxy_fqdn):
        raise HTTPException(
            400,
            detail="Para activar Kerberos hacen falta el realm y el FQDN del proxy.",
        )

    config = _obtener_o_crear(db)
    config.enabled = data.enabled
    config.realm = realm.upper() if realm else None
    config.proxy_fqdn = proxy_fqdn.lower() if proxy_fqdn else None
    db.commit()
    mark_dirty()

    logger.info("Kerberos %s", "activado" if config.enabled else "desactivado")
    return {"status": "ok"}


@router.get("/ad-setup-script")
async def get_ad_setup_script(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Genera un .ps1 para preparar el Active Directory, con Realm y FQDN ya
    completados con lo que hay guardado en el panel. Evita el error más común
    del setup manual: copiar el script de la documentación y olvidarse de
    cambiar esos dos valores por los propios.

    No incluye ninguna contraseña ni credencial: la cuenta de servicio y el
    keytab se generan en el propio AD al correr el script, y este endpoint no
    sabe ni pregunta nada sobre ellos.
    """
    config = _obtener_o_crear(db)
    if not config.realm or not config.proxy_fqdn:
        raise HTTPException(
            400,
            detail="Completa y guarda Realm y FQDN del proxy antes de generar el script.",
        )

    # Primer segmento del FQDN como nombre de cuenta sugerido (proxy.empresa.com
    # -> "proxy"): un punto de partida razonable, editable con -NombreCuenta al
    # correr el script si el AD del cliente tiene su propia convención.
    nombre_sugerido = config.proxy_fqdn.split(".")[0] or "proxy-squidmanager"

    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template("kerberos_ad_setup.ps1.j2")
    contenido = template.render(
        realm=config.realm,
        proxy_fqdn=config.proxy_fqdn,
        nombre_cuenta_sugerido=nombre_sugerido,
        generado_en=utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    )
    # Con BOM: PowerShell 5.1 (el que trae Windows Server por defecto) asume
    # la codepage ANSI/OEM del sistema al leer un .ps1 sin BOM, y las tildes
    # y la ñ de los comentarios y los Write-Host salen mal en la consola. No
    # afecta la ejecución -son cadenas literales y comentarios-, pero un
    # script pensado para un admin de Windows no debería salir así.
    return PlainTextResponse(
        contenido.encode("utf-8-sig"),
        media_type="application/octet-stream",
        headers={"Content-Disposition": 'attachment; filename="kerberos-ad-setup.ps1"'},
    )


@router.post("/keytab")
async def upload_keytab(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
):
    """Sube el archivo .keytab generado por el administrador del AD del cliente.

    SquidManager no genera este archivo ni pide credenciales de dominio: crear
    la cuenta de equipo en el AD (msktutil o equivalente) es una operación que
    hace el propio cliente, fuera de este panel.
    """
    data = await file.read()
    if len(data) > MAX_KEYTAB_BYTES:
        raise HTTPException(400, detail=f"El archivo supera el máximo de {MAX_KEYTAB_BYTES // 1024} KB.")

    valido, mensaje = validar_keytab(data)
    if not valido:
        raise HTTPException(400, detail=mensaje)

    config = _obtener_o_crear(db)
    config.keytab_data = data
    config.keytab_filename = file.filename
    config.keytab_uploaded_at = utcnow()
    db.commit()
    mark_dirty()

    logger.info("Keytab de Kerberos subido (%s, %d bytes)", file.filename, len(data))
    return {"status": "ok", "message": "Keytab guardado. Pulsa «Aplicar cambios» para activarlo."}


@router.delete("/keytab")
async def delete_keytab(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
):
    """Quita el keytab actual. Kerberos deja de ofrecerse al aplicar cambios."""
    config = _obtener_o_crear(db)
    config.keytab_data = None
    config.keytab_filename = None
    config.keytab_uploaded_at = None
    db.commit()
    mark_dirty()
    return {"status": "ok"}
