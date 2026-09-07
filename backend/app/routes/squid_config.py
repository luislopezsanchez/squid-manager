"""Rutas de configuración general de Squid."""

import logging
import re
import subprocess
from pathlib import Path

import docker as docker_sdk
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.i18n import idioma_de_cabecera, traducir
from app.models.admin import Admin
from app.models.squid_settings import SquidSetting
from app.services.auth_service import get_current_admin, require_writer
from app.services.config_generator import generate_squid_config
from app.services.squid_service import reload_squid, get_squid_status, restart_squid, write_ldap_aux_files, apply_squid_config
from app.services.notification_service import queue_notification
from app.services.config_state import mark_dirty, mark_clean, is_dirty
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


class SettingUpdate(BaseModel):
    key: str
    value: str
    category: str = "general"
    description: str | None = None


@router.get("/settings")
async def get_settings(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Obtiene toda la configuración de Squid."""
    settings_list = db.query(SquidSetting).all()
    return {s.key: {"value": s.value, "category": s.category, "description": s.description} for s in settings_list}


@router.put("/settings")
async def update_setting(
    data: SettingUpdate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
):
    """Actualiza una configuración de Squid."""
    # Los servidores DNS tienen que ser direcciones IP: Squid pregunta a esa
    # lista sin poder resolver nada antes. Se rechaza al guardar, no al
    # aplicar, para que el error salga junto al campo que lo provoca.
    if data.key == "dns_nameservers":
        from app.services.dns_service import parsear_lista, validar_servidores

        valido, mensaje = validar_servidores(parsear_lista(data.value))
        if not valido:
            raise HTTPException(400, detail=mensaje)

    # Los orígenes de confianza eximen de autenticarse: un valor mal escrito
    # aquí no da un error visible, deja pasar (o deja fuera) a quien no toca.
    if data.key == "trusted_sources":
        from app.services.origenes_service import parsear_lista, validar_origenes

        valido, mensaje = validar_origenes(parsear_lista(data.value))
        if not valido:
            raise HTTPException(400, detail=mensaje)

    # Igual que trusted_sources pero por dominio de destino: exime de
    # autenticarse sin importar quién pida ese dominio.
    if data.key == "auth_exempt_domains":
        from app.services.auth_exempt_service import parsear_lista, validar_dominios

        valido, mensaje = validar_dominios(parsear_lista(data.value))
        if not valido:
            raise HTTPException(400, detail=mensaje)

    # Digest solo sabe autenticar usuarios LOCALES: el helper nunca ve la
    # contraseña en claro del cliente, solo el HA1 ya calculado, y ese HA1 no
    # existe para nadie que entre por LDAP. Activarlo con LDAP habilitado
    # dejaría a esos usuarios sin poder navegar, sin ningún aviso hasta que
    # alguien reportara el problema.
    if data.key == "proxy_auth_scheme" and data.value.strip().lower() not in ("basic", "digest"):
        raise HTTPException(400, detail='El esquema de autenticación debe ser "basic" o "digest".')

    if data.key == "proxy_auth_scheme" and data.value.strip().lower() == "digest":
        from app.models.ldap_config import LdapConfig

        ldap = db.query(LdapConfig).first()
        if ldap and ldap.enabled:
            raise HTTPException(
                400,
                detail=(
                    "No se puede activar Digest con LDAP habilitado: Digest solo "
                    "autentica usuarios locales del proxy, no hay forma estándar de "
                    "guardar el hash que necesita en un directorio LDAP/Active "
                    "Directory. Desactiva LDAP en Configuración LDAP antes de activar "
                    "Digest, o mantén Basic si necesitas los dos."
                ),
            )

    # true/false explícito: sin esto un typo ("flase", "verdadero") pasaba la
    # sanitización genérica y el generador lo interpretaba como "true" (activa
    # la interceptación de HTTPS) por defecto silenciosamente — justo lo
    # contrario de lo que alguien escribiendo "false" a mano querría.
    if data.key == "ssl_bump_enabled" and data.value.strip().lower() not in ("true", "false"):
        raise HTTPException(400, detail='El valor de «ssl_bump_enabled» debe ser "true" o "false".')

    # El resto de valores se interpolan tal cual en squid.conf (visible_hostname,
    # cache_dir, refresh_pattern, auth_realm, access_log, etc.): sin esto, un
    # salto de línea en el valor inserta una directiva arbitraria en el fichero.
    # dns_nameservers, trusted_sources, auth_exempt_domains y ssl_bump_exclude
    # quedan fuera porque ya tienen su propio parseo por líneas más arriba o en
    # el generador.
    if data.key not in ("dns_nameservers", "trusted_sources", "auth_exempt_domains", "ssl_bump_exclude"):
        from app.services.squid_names import validate_value

        data.value = validate_value(data.value, field=f"valor de «{data.key}»")

    setting = db.query(SquidSetting).filter(SquidSetting.key == data.key).first()
    if setting:
        setting.value = data.value
        setting.category = data.category
        if data.description:
            setting.description = data.description
    else:
        setting = SquidSetting(key=data.key, value=data.value,
                                category=data.category, description=data.description)
        db.add(setting)
    db.commit()
    mark_dirty()
    return {"status": "ok", "key": data.key, "value": data.value}


@router.post("/apply")
async def apply_config(
    request: Request,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
    background_tasks: BackgroundTasks = None,
):
    """Genera el squid.conf, valida y recarga o reinicia Squid.

    Si el http_port de la BD no coincide con el puerto que Docker publica,
    sincroniza el .env y recrea el contenedor con `docker compose up -d squid`,
    de modo que el mapeo de puertos sobreviva a cualquier recreación posterior.

    apply_squid_config es sincrono y bloqueante (subprocess, red, disco): se
    delega al threadpool de Starlette para no congelar el unico hilo del
    event loop. Sin esto, mientras un apply tarda (probado en vivo: hasta 33s
    con sondeos de DNS/proxy padre incluidos) TODO el panel queda sin
    respuesta para TODOS los administradores conectados, no solo para quien
    lo pidio.
    """
    result = await run_in_threadpool(apply_squid_config, db)

    # Esta respuesta no es una excepcion, asi que no pasa por el manejador que
    # traduce los errores: hay que traducir su mensaje aqui.
    idioma = idioma_de_cabecera(request.headers.get("accept-language"))
    if isinstance(result.get("message"), str):
        result["message"] = traducir(result["message"], idioma)

    if result["status"] == "error":
        return result

    if background_tasks:
        action = "reinicio con SSL Bump" if result.get("needs_restart") else "reconfigure"
        queue_notification(background_tasks, db, "apply",
                           "Cambios aplicados a Squid",
                           f"El admin {current_admin.username} aplicó cambios ({action}).")

    return result


class DnsTest(BaseModel):
    servers: str


@router.post("/dns/test")
async def test_dns(
    data: DnsTest,
    _: Admin = Depends(require_writer),
):
    """Comprueba unos servidores DNS sin llegar a guardarlos.

    Permite verificar el servidor antes de aplicarlo, en lugar de descubrir que
    no responde cuando ya nadie puede navegar.
    """
    from app.services.dns_service import parsear_lista, validar_servidores, probar_servidores

    servidores = parsear_lista(data.servers)
    if not servidores:
        return {
            "ok": True,
            "message": "Sin servidores: Squid usará la resolución del sistema.",
        }

    valido, mensaje = validar_servidores(servidores)
    if not valido:
        return {"ok": False, "message": mensaje}

    ok, mensaje = probar_servidores(servidores)
    return {"ok": ok, "message": mensaje}


@router.get("/status")
async def get_status(_: Admin = Depends(get_current_admin)):
    """Estado del servicio Squid."""
    return get_squid_status()


@router.get("/preview")
async def preview_config(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Previsualiza el squid.conf que se generaría."""
    config_text = generate_squid_config(db)
    return {"config": config_text}


@router.get("/pending")
async def pending_changes(
    _: Admin = Depends(get_current_admin),
):
    """Indica si hay cambios en la BD que aún no se han aplicado a Squid."""
    return {"dirty": is_dirty()}


@router.get("/ca-cert")
async def download_ca_cert(_: Admin = Depends(get_current_admin)):
    """Descarga el certificado CA de Squid para instalar en los clientes."""
    from fastapi import Response
    ca_path = "/etc/squid/ssl_cert/squid-ca.crt"
    try:
        with open(ca_path, "r") as f:
            content = f.read()
        return Response(
            content=content,
            media_type="application/x-x509-ca-cert",
            headers={"Content-Disposition": "attachment; filename=squidmanager-ca.crt"},
        )
    except FileNotFoundError:
        # Quien genera la CA es distinto en cada despliegue: el arranque del
        # contenedor en uno, el instalador en el otro. Decir el remedio
        # equivocado manda a dar vueltas.
        from app.services.runtime import get_runtime

        if get_runtime().name == "native":
            remedio = "Vuelve a ejecutar install-nativo.sh para regenerarla."
        else:
            remedio = "Reinicia el contenedor Squid."
        raise HTTPException(404, detail=f"Certificado CA no encontrado. {remedio}")


@router.get("/ca-deploy/install-cert.bat")
async def download_bat_installer(_: Admin = Depends(get_current_admin)):
    """Descarga el instalador .bat (Windows) con el certificado embebido."""
    from fastapi import Response
    from app.services.cert_deploy_service import generate_bat_installer, CaCertNotFound
    try:
        content = generate_bat_installer()
    except CaCertNotFound as e:
        raise HTTPException(404, detail=str(e))
    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={"Content-Disposition": "attachment; filename=install-cert.bat"},
    )


@router.get("/ca-deploy/deploy-gpo.ps1")
async def download_gpo_script(_: Admin = Depends(get_current_admin)):
    """Descarga el script PowerShell para desplegar el certificado vía GPO."""
    from fastapi import Response
    from app.services.cert_deploy_service import generate_gpo_script, CaCertNotFound
    try:
        content = generate_gpo_script()
    except CaCertNotFound as e:
        raise HTTPException(404, detail=str(e))
    return Response(
        content=content,
        media_type="text/plain",
        headers={"Content-Disposition": "attachment; filename=deploy-gpo.ps1"},
    )


@router.get("/ca-deploy/cert.mobileconfig")
async def download_mobileconfig(_: Admin = Depends(get_current_admin)):
    """Descarga el perfil .mobileconfig para iOS/macOS."""
    from fastapi import Response
    from app.services.cert_deploy_service import generate_mobileconfig, CaCertNotFound
    try:
        content = generate_mobileconfig()
    except CaCertNotFound as e:
        raise HTTPException(404, detail=str(e))
    return Response(
        content=content,
        media_type="application/x-apple-aspen-config",
        headers={"Content-Disposition": "attachment; filename=squidmanager-ca.mobileconfig"},
    )