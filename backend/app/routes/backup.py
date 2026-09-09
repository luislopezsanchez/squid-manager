"""Rutas de backup, restore e importación de squid.conf."""

import json
import logging
from io import StringIO

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse, PlainTextResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.admin import Admin
from app.models.acl import Acl
from app.models.access_rule import AccessRule
from app.models.proxy_user import ProxyUser
from app.models.squid_settings import SquidSetting
from app.models.delay_pool import DelayPool
from app.models.ldap_config import LdapConfig
from app.models.ldap_user import LdapUser
from app.models.user_group import UserGroup, UserGroupMember
from app.models.audit_log import AuditLog
from app.services.auth_service import get_current_admin, require_writer
from app.services.config_generator import generate_squid_config
from app.services.config_state import mark_dirty
from app.services.squid_names import (
    validate_name, validate_acl_type, validate_value, validate_acl_names,
    known_acl_names,
)
from app.utils import utcnow

logger = logging.getLogger(__name__)
router = APIRouter()

BACKUP_VERSION = "0.6.0"
# Un backup de esta herramienta son unos pocos cientos de KB. El límite evita
# que una subida grande se lea entera en memoria.
MAX_UPLOAD_BYTES = 8 * 1024 * 1024


async def _read_upload(file: UploadFile) -> bytes:
    """Lee el fichero subido aplicando un límite de tamaño."""
    chunks = []
    total = 0
    while True:
        chunk = await file.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > MAX_UPLOAD_BYTES:
            raise HTTPException(
                413,
                detail=f"El archivo supera el límite de {MAX_UPLOAD_BYTES // (1024 * 1024)} MB",
            )
        chunks.append(chunk)
    return b"".join(chunks)


# ============================================
# BACKUP - Exportar toda la configuración a JSON
# ============================================

@router.get("/export")
async def export_backup(
    db: Session = Depends(get_db),
    admin: Admin = Depends(require_writer),
):
    """Exportar toda la configuración de SquidManager a un archivo JSON.

    Incluye grupos, miembros y allow-list de LDAP: sin ellos, restaurar dejaba
    reglas apuntando a grupos inexistentes y la configuración no era válida.
    """
    backup = {
        "metadata": {
            "platform": "SquidManager",
            "version": BACKUP_VERSION,
            "exported_at": utcnow().isoformat(),
            "exported_by": admin.username,
        },
        "squid_settings": [
            {"key": s.key, "value": s.value, "category": s.category, "description": s.description}
            for s in db.query(SquidSetting).all()
        ],
        "acls": [
            {"name": a.name, "type": a.type, "value": a.value,
             "description": a.description, "enabled": a.enabled}
            for a in db.query(Acl).order_by(Acl.id).all()
        ],
        "access_rules": [
            {"action": r.action, "acl_names": r.acl_names, "order": r.order,
             "description": r.description, "enabled": r.enabled}
            for r in db.query(AccessRule).order_by(AccessRule.order, AccessRule.id).all()
        ],
        "proxy_users": [
            {"username": u.username, "enabled": u.enabled,
             "expires_at": u.expires_at.isoformat() if u.expires_at else None}
            for u in db.query(ProxyUser).all()
        ],
        "delay_pools": [
            {"pool_class": dp.pool_class, "parameters": dp.parameters,
             "acl_name": dp.acl_name, "description": dp.description, "enabled": dp.enabled}
            for dp in db.query(DelayPool).all()
        ],
        "user_groups": [
            {
                "name": g.name,
                "description": g.description,
                "members": [
                    m.username
                    for m in db.query(UserGroupMember).filter(UserGroupMember.group_id == g.id).all()
                ],
            }
            for g in db.query(UserGroup).order_by(UserGroup.name).all()
        ],
        "ldap_users": [
            {"username": u.username, "display_name": u.display_name,
             "email": u.email, "enabled": u.enabled}
            for u in db.query(LdapUser).order_by(LdapUser.username).all()
        ],
        "ldap_config": None,
    }

    ldap = db.query(LdapConfig).first()
    if ldap:
        # La contraseña de bind no se exporta a propósito.
        backup["ldap_config"] = {
            "server_url": ldap.server_url, "bind_dn": ldap.bind_dn,
            "search_base": ldap.search_base, "user_filter": ldap.user_filter,
            "enabled": ldap.enabled,
        }

    json_str = json.dumps(backup, indent=2, ensure_ascii=False)
    filename = f"squidmanager-backup-{utcnow().strftime('%Y%m%d-%H%M%S')}.json"

    return StreamingResponse(
        StringIO(json_str),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ============================================
# RESTORE - Importar backup JSON
# ============================================

@router.post("/restore")
async def restore_backup(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: Admin = Depends(require_writer),
):
    """Restaurar configuración desde un archivo JSON de backup de SquidManager."""
    content = await _read_upload(file)
    try:
        backup = json.loads(content.decode("utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Archivo JSON inválido")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error leyendo archivo: {e}")

    if "metadata" not in backup or "platform" not in backup["metadata"]:
        raise HTTPException(status_code=400, detail="No es un backup válido de SquidManager")

    results = {
        "settings": 0, "acls": 0, "rules": 0, "users": 0,
        "delay_pools": 0, "groups": 0, "ldap_users": 0, "ldap": False,
        "warnings": [],
    }

    # Mismas reglas que en PUT /settings, y por el mismo motivo: sin esto, un
    # backup manipulado inserta una directiva arbitraria en squid.conf (para el
    # resto de claves) o fija trusted_sources/dns_nameservers/auth_exempt_domains
    # a algo peligroso (por ejemplo 0.0.0.0/0 o "*", que eximiria de
    # autenticarse a cualquiera) sin pasar por sus validadores semanticos.
    # ssl_bump_exclude no necesita validacion propia: config_generator ya la
    # trocea por lineas antes de usarla y un dominio de mas ahi no compromete
    # nada (solo decide si SE descifra o no, no si se exige autenticacion).
    from app.services.dns_service import parsear_lista as parsear_dns, validar_servidores
    from app.services.origenes_service import parsear_lista as parsear_origenes, validar_origenes
    from app.services.auth_exempt_service import parsear_lista as parsear_exentos, validar_dominios

    for s in backup.get("squid_settings", []):
        key = s.get("key")
        # Normalizado ANTES de las ramas de abajo: si el backup no traia la
        # clave "value" en absoluto, sin esto el acceso a s["value"] mas abajo
        # (aqui o en el SquidSetting(**s) del else) reventaria con KeyError.
        s["value"] = s.get("value") or ""
        if key == "dns_nameservers":
            valido, mensaje = validar_servidores(parsear_dns(s.get("value")))
            if not valido:
                raise HTTPException(400, detail=mensaje)
        elif key == "trusted_sources":
            valido, mensaje = validar_origenes(parsear_origenes(s.get("value")))
            if not valido:
                raise HTTPException(400, detail=mensaje)
        elif key == "auth_exempt_domains":
            valido, mensaje = validar_dominios(parsear_exentos(s.get("value")))
            if not valido:
                raise HTTPException(400, detail=mensaje)
        elif key != "ssl_bump_exclude" and s["value"]:
            # Solo se valida un valor NO vacio: uno vacio no puede inyectar
            # nada en squid.conf (no hay contenido que interpretar), asi que
            # rechazarlo aqui solo servia para abortar la restauracion entera
            # de un backup viejo o legitimo que alguna vez guardo un ajuste
            # en blanco, antes de que esta validacion existiera en el PUT.
            s["value"] = validate_value(s["value"], field=f"valor de «{key}»")
        existing = db.query(SquidSetting).filter(SquidSetting.key == s["key"]).first()
        if existing:
            existing.value = s["value"]
        else:
            db.add(SquidSetting(**s))
        results["settings"] += 1

    for a in backup.get("acls", []):
        a["name"] = validate_name(a["name"], "ACL")
        a["type"] = validate_acl_type(a["type"])
        a["value"] = validate_value(a["value"])
        existing = db.query(Acl).filter(Acl.name == a["name"]).first()
        if existing:
            existing.type = a["type"]
            existing.value = a["value"]
            existing.description = a.get("description")
            existing.enabled = a["enabled"]
        else:
            db.add(Acl(**a))
        results["acls"] += 1

    # Sin este flush, una ACL nueva (recien anadida arriba con db.add(), sin
    # id ni fila en la BD todavia porque SessionLocal usa autoflush=False)
    # es invisible para la consulta fresca de known_acl_names() de mas abajo:
    # un backup legitimo con ACLs y reglas nuevas pero SIN grupos (el unico
    # otro sitio que hace flush) se rechazaba entero con "ACL que no existe".
    db.flush()

    # Grupos y miembros: se restauran ANTES que las reglas, porque las reglas
    # los referencian por nombre.
    for g in backup.get("user_groups", []):
        g["name"] = validate_name(g["name"], "grupo")
        group = db.query(UserGroup).filter(UserGroup.name == g["name"]).first()
        if not group:
            group = UserGroup(name=g["name"], description=g.get("description"))
            db.add(group)
            db.flush()
        else:
            group.description = g.get("description")
            db.query(UserGroupMember).filter(UserGroupMember.group_id == group.id).delete()
        for username in g.get("members", []):
            db.add(UserGroupMember(group_id=group.id, username=username))
        results["groups"] += 1

    if backup.get("access_rules"):
        # Se recalcula después de restaurar ACLs y grupos: son quienes definen
        # qué nombres son válidos en una regla.
        nombres_validos = known_acl_names(db)
        db.query(AccessRule).delete()
        for r in backup["access_rules"]:
            if r["action"] not in ("allow", "deny"):
                raise HTTPException(400, detail=f"Acción de regla inválida: '{r['action']}'")
            r["acl_names"] = validate_acl_names(r["acl_names"], nombres_validos)
            db.add(AccessRule(
                action=r["action"], acl_names=r["acl_names"],
                order=r["order"], description=r.get("description"),
                enabled=r["enabled"],
            ))
        results["rules"] = len(backup["access_rules"])

    # Los usuarios se recrean sin contraseña: los hashes no se exportan. Se
    # dejan deshabilitados para que quede claro que hay que asignarles una,
    # en lugar de aparecer activos y no poder autenticarse nunca.
    pending_password = []
    for u in backup.get("proxy_users", []):
        existing = db.query(ProxyUser).filter(ProxyUser.username == u["username"]).first()
        if not existing:
            db.add(ProxyUser(
                username=u["username"],
                password_hash="",
                htpasswd_hash=None,
                enabled=False,
                expires_at=None,
            ))
            pending_password.append(u["username"])
            results["users"] += 1
        else:
            existing.enabled = u["enabled"]

    if pending_password:
        results["warnings"].append(
            "Estos usuarios se han creado sin contraseña y están deshabilitados; "
            "asígnales una con «Resetear contraseña»: " + ", ".join(pending_password)
        )

    for lu in backup.get("ldap_users", []):
        existing = db.query(LdapUser).filter(LdapUser.username == lu["username"]).first()
        if existing:
            existing.display_name = lu.get("display_name")
            existing.email = lu.get("email")
            existing.enabled = lu.get("enabled", False)
        else:
            db.add(LdapUser(
                username=lu["username"], display_name=lu.get("display_name"),
                email=lu.get("email"), enabled=lu.get("enabled", False),
            ))
        results["ldap_users"] += 1

    if backup.get("delay_pools"):
        db.query(DelayPool).delete()
        for dp in backup["delay_pools"]:
            dp["parameters"] = validate_value(dp["parameters"], field="parámetros del delay pool")
            if dp.get("acl_name"):
                dp["acl_name"] = validate_value(dp["acl_name"], field="ACL del delay pool")
            db.add(DelayPool(**dp))
        results["delay_pools"] = len(backup["delay_pools"])

    ldap_data = backup.get("ldap_config")
    if ldap_data:
        existing = db.query(LdapConfig).first()
        if existing:
            existing.server_url = ldap_data["server_url"]
            existing.bind_dn = ldap_data["bind_dn"]
            existing.search_base = ldap_data["search_base"]
            existing.user_filter = ldap_data["user_filter"]
            existing.enabled = ldap_data["enabled"]
        else:
            db.add(LdapConfig(bind_password="", **ldap_data))
            results["warnings"].append(
                "La contraseña de bind de LDAP no viaja en los backups: vuelve a "
                "introducirla en Configuración LDAP."
            )
        results["ldap"] = True

    db.add(AuditLog(
        admin_id=admin.id, admin_username=admin.username,
        action="restore", entity="backup",
        new_value=f"backup de {backup['metadata'].get('exported_at', 'fecha desconocida')}",
    ))
    db.commit()
    # La configuración de Squid en disco sigue siendo la anterior hasta que se
    # pulse «Aplicar cambios».
    mark_dirty()

    results["warnings"].append("Revisa la configuración y pulsa «Aplicar cambios» para activarla.")
    return {"status": "ok", "message": "Backup restaurado correctamente", "details": results}


# ============================================
# DESCARGAR squid.conf generado
# ============================================

@router.get("/squid-conf")
async def download_squid_conf(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Descargar el squid.conf generado por SquidManager.

    Este archivo es un squid.conf estándar válido. Puede usarse en un Squid
    tradicional, pero hay que ajustar rutas, helpers y certificados manualmente.
    """
    config_text = generate_squid_config(db)
    filename = f"squid.conf-{utcnow().strftime('%Y%m%d-%H%M%S')}"

    return PlainTextResponse(
        config_text,
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ============================================
# IMPORTAR squid.conf tradicional (analizar -> revisar -> aplicar)
# ============================================
#
# Un Squid administrado a mano varía demasiado de una instalación a otra
# (include de ACLs en archivos aparte, NTLM/AD, squidGuard, proxy padres con
# opciones propias...) como para que un import de un solo paso sea seguro:
# la versión anterior escribía en la BD directo al subir el archivo, sin
# soporte de `include` (con lo que un squid.conf típico, que separa ACLs y
# reglas en archivos incluidos, importaba "0 ACLs, 0 reglas" sin que nadie
# se enterara de por qué) y sin validar nombres/tipos contra lo que el resto
# del panel exige. Ahora es un análisis (nada se escribe) seguido de una
# aplicación explícita sobre lo ya revisado -ver squid_import_service.py-.
from app.services import squid_import_service as import_svc

MAX_IMPORT_FILES = 20


@router.post("/analyze-squid-conf")
async def analyze_squid_conf(
    files: list[UploadFile] = File(...),
    principal: str = Form(...),
    db: Session = Depends(get_db),
    admin: Admin = Depends(require_writer),
):
    """Analiza uno o más archivos de un squid.conf tradicional SIN escribir
    nada en la base de datos. `principal` es el nombre del archivo que hace
    de punto de entrada (el squid.conf en sí); el resto solo se usan si
    algún `include` los referencia por nombre de archivo.

    Devuelve un informe detallado (qué se importaría, qué no y por qué) más
    un token de corta duración para confirmar con /apply-squid-import sin
    tener que volver a subir los archivos.
    """
    if len(files) > MAX_IMPORT_FILES:
        raise HTTPException(400, detail=f"Como mucho {MAX_IMPORT_FILES} archivos por vez.")

    contenidos: dict[str, str] = {}
    for f in files:
        data = await _read_upload(f)
        contenidos[f.filename or "squid.conf"] = data.decode("utf-8", errors="replace")

    if principal not in contenidos:
        raise HTTPException(400, detail=f"El archivo principal '{principal}' no está entre los subidos.")

    existentes = {a[0] for a in db.query(Acl.name).all()}
    conocidos = import_svc.known_acl_names(db)

    resultado = import_svc.analizar(contenidos, principal, existentes, conocidos)
    token = import_svc.guardar_analisis(resultado)

    def _acl_dict(a):
        return {"name": a.name, "type": a.type, "value": a.value, "estado": a.estado, "motivo": a.motivo}

    def _regla_dict(r):
        return {"action": r.action, "acl_names": r.acl_names, "estado": r.estado, "motivo": r.motivo}

    return {
        "status": "ok",
        "token": token,
        "resumen": resultado.resumen(),
        "acls": [_acl_dict(a) for a in resultado.acls],
        "reglas": [_regla_dict(r) for r in resultado.reglas],
        "settings": [{"key": s.key, "value": s.value} for s in resultado.settings],
        "delay_pools": [{"pool_class": d.pool_class, "parameters": d.parameters} for d in resultado.delay_pools],
        "parent_proxy": (
            {
                "host": resultado.parent_proxy.host, "port": resultado.parent_proxy.port,
                "username": resultado.parent_proxy.username, "estado": resultado.parent_proxy.estado,
                "motivo": resultado.parent_proxy.motivo,
            }
            if resultado.parent_proxy else None
        ),
        "no_soportadas": [
            {"directiva": h.directiva, "archivo": h.archivo, "linea": h.linea, "motivo": h.motivo}
            for h in resultado.no_soportadas
        ],
        "desconocidas": [
            {"directiva": h.directiva, "archivo": h.archivo, "linea": h.linea, "motivo": h.motivo}
            for h in resultado.desconocidas
        ],
        "includes_faltantes": resultado.includes_faltantes,
    }


@router.post("/apply-squid-import")
async def apply_squid_import(
    token: str = Form(...),
    db: Session = Depends(get_db),
    admin: Admin = Depends(require_writer),
):
    """Aplica un análisis previo (por su token de /analyze-squid-conf).

    El token vive en memoria unos minutos y se consume al usarlo: no se
    puede aplicar el mismo análisis dos veces ni reutilizarlo más tarde.
    """
    resultado = import_svc.recuperar_analisis(token)
    if resultado is None:
        raise HTTPException(
            400,
            detail="El análisis expiró o ya se aplicó. Vuelve a subir el archivo y analízalo de nuevo.",
        )

    detalle = import_svc.aplicar(db, resultado)

    db.add(AuditLog(
        admin_id=admin.id, admin_username=admin.username,
        action="import", entity="squid_conf",
        new_value=f"{detalle['acls']} ACLs, {detalle['reglas']} reglas, {detalle['settings']} settings",
    ))
    db.commit()
    mark_dirty()

    detalle["avisos"].append("Revisa la configuración importada y pulsa «Aplicar cambios» para activarla.")
    return {"status": "ok", "message": "Importación aplicada", "details": detalle}
