"""Rutas de configuración de Kerberos (autenticación Negotiate contra AD)."""

import io
import logging
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response
from jinja2 import Environment, FileSystemLoader
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.admin import Admin
from app.models.audit_log import AuditLog
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
    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="update", entity="kerberos_config", entity_id=config.id,
        new_value=f"enabled={config.enabled} realm={config.realm} proxy_fqdn={config.proxy_fqdn}",
    ))
    db.commit()
    mark_dirty()

    logger.info("Kerberos %s", "activado" if config.enabled else "desactivado")
    return {"status": "ok"}


# Windows Server bloquea por defecto cualquier .ps1 sin firma digital, se
# haya descargado o copiado por USB ("no se puede cargar el archivo... no
# esta firmado digitalmente"): la primera versión de este endpoint solo
# entregaba el .ps1 y el usuario se topó justo con eso. Un .cmd no tiene esa
# restricción -PowerShell solo la aplica a sus propios .ps1-, así que se
# entrega como lanzador junto al script, dentro de un .zip. No cambia la
# política de ejecución del sistema: el -ExecutionPolicy Bypass de abajo
# aplica solo a este proceso de powershell.exe, una vez.
_LAUNCHER_CMD = """@echo off
REM Lanzador de kerberos-ad-setup.ps1 -- generado por SquidManager.
REM
REM Windows bloquea por defecto cualquier .ps1 sin firma digital (mensaje
REM "no esta firmado digitalmente"), venga de donde venga. Este .cmd no
REM cambia la politica de ejecucion del sistema: el -ExecutionPolicy Bypass
REM de abajo aplica solo a esta ejecucion de powershell.exe, una vez.
REM
REM Revisa el contenido de kerberos-ad-setup.ps1 antes de correr esto, igual
REM que revisarias cualquier script que va a correr con permisos de
REM administrador de dominio.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0kerberos-ad-setup.ps1" %*
pause
"""


@router.get("/ad-setup-script")
async def get_ad_setup_script(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Genera un .zip con el script para preparar el Active Directory y un
    lanzador .cmd, con Realm y FQDN ya completados con lo que hay guardado en
    el panel. Evita dos problemas reales, no hipotéticos: copiar el script de
    la documentación y olvidarse de cambiar el realm/FQDN de ejemplo, y el
    bloqueo por defecto de Windows a cualquier .ps1 sin firma digital (ver
    `_LAUNCHER_CMD` arriba).

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

    # Un nombre fijo y distintivo, no el primer segmento del FQDN
    # (proxy.empresa.com -> "proxy"): un nombre tan genérico como "proxy"
    # choca fácil con algo que ya exista en el AD por otro motivo -visto en
    # una prueba real: "ya existe" al crear, pero ktpass no podía resolverlo
    # después, señal de que ese "proxy" no era la cuenta de servicio que el
    # script esperaba-. Editable con -NombreCuenta al correr el script si el
    # AD del cliente tiene su propia convención (SamAccountName admite hasta
    # 20 caracteres: "svc-squidmanager" deja margen).
    nombre_sugerido = "svc-squidmanager"

    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    template = env.get_template("kerberos_ad_setup.ps1.j2")
    contenido_ps1 = template.render(
        realm=config.realm,
        proxy_fqdn=config.proxy_fqdn,
        nombre_cuenta_sugerido=nombre_sugerido,
        generado_en=utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # Con BOM: PowerShell 5.1 (el que trae Windows Server por defecto)
        # asume la codepage ANSI/OEM del sistema al leer un .ps1 sin BOM, y
        # las tildes/ñ de los comentarios y los Write-Host salen mal en la
        # consola. No afecta la ejecución -son cadenas literales y
        # comentarios-, pero un script para un admin de Windows no debería
        # salir así.
        zf.writestr("kerberos-ad-setup.ps1", contenido_ps1.encode("utf-8-sig"))
        # Sin acentos a propósito: un .cmd interpreta su propio texto con la
        # codepage OEM de la consola, no UTF-8, y una tilde mal traducida
        # ahí sí puede romper una línea de REM en algunas code pages.
        zf.writestr("Ejecutar.cmd", _LAUNCHER_CMD.encode("ascii"))

    return Response(
        buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="kerberos-ad-setup.zip"'},
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
    # Nunca el contenido del keytab -es una credencial de la cuenta de equipo
    # del AD del cliente-, solo el nombre de archivo y el tamaño.
    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="update", entity="kerberos_keytab", entity_id=config.id,
        new_value=f"keytab subido: {file.filename} ({len(data)} bytes)",
    ))
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
    nombre_anterior = config.keytab_filename
    config.keytab_data = None
    config.keytab_filename = None
    config.keytab_uploaded_at = None
    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="delete", entity="kerberos_keytab", entity_id=config.id,
        old_value=f"keytab: {nombre_anterior}",
    ))
    db.commit()
    mark_dirty()
    return {"status": "ok"}
