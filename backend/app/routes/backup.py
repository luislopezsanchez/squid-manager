"""Rutas de backup, restore e importación de squid.conf."""

import re
import json
import logging
from datetime import datetime
from io import StringIO
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
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
from app.services.auth_service import get_current_admin, get_password_hash
from app.services.config_generator import generate_squid_config

logger = logging.getLogger(__name__)
router = APIRouter()


def _require_admin(admin: Admin = Depends(get_current_admin)) -> Admin:
    """Requiere rol admin o superadmin (no viewer)."""
    if admin.role == "viewer":
        raise HTTPException(status_code=403, detail="Los viewers no pueden realizar cambios")
    return admin


# ============================================
# BACKUP - Exportar toda la configuración a JSON
# ============================================

@router.get("/export")
async def export_backup(
    db: Session = Depends(get_db),
    admin: Admin = Depends(get_current_admin),
):
    """Exportar toda la configuración de SquidManager a un archivo JSON."""
    backup = {
        "metadata": {
            "platform": "SquidManager",
            "version": "0.4.0",
            "exported_at": datetime.utcnow().isoformat(),
            "exported_by": admin.username,
        },
        "squid_settings": [],
        "acls": [],
        "access_rules": [],
        "proxy_users": [],
        "delay_pools": [],
        "ldap_config": None,
    }

    # Settings
    for s in db.query(SquidSetting).all():
        backup["squid_settings"].append({
            "key": s.key, "value": s.value,
            "category": s.category, "description": s.description,
        })

    # ACLs
    for a in db.query(Acl).order_by(Acl.id).all():
        backup["acls"].append({
            "name": a.name, "type": a.type, "value": a.value,
            "description": a.description, "enabled": a.enabled,
        })

    # Access rules (preservando orden)
    for r in db.query(AccessRule).order_by(AccessRule.order).all():
        backup["access_rules"].append({
            "action": r.action, "acl_names": r.acl_names,
            "order": r.order, "description": r.description, "enabled": r.enabled,
        })

    # Proxy users (sin hash de contraseña - se regeneran)
    for u in db.query(ProxyUser).all():
        backup["proxy_users"].append({
            "username": u.username, "enabled": u.enabled,
            "expires_at": u.expires_at.isoformat() if u.expires_at else None,
        })

    # Delay pools
    for dp in db.query(DelayPool).all():
        backup["delay_pools"].append({
            "pool_class": dp.pool_class, "parameters": dp.parameters,
            "acl_name": dp.acl_name, "description": dp.description, "enabled": dp.enabled,
        })

    # LDAP
    ldap = db.query(LdapConfig).first()
    if ldap:
        backup["ldap_config"] = {
            "server_url": ldap.server_url, "bind_dn": ldap.bind_dn,
            "search_base": ldap.search_base, "user_filter": ldap.user_filter,
            "enabled": ldap.enabled,
        }

    json_str = json.dumps(backup, indent=2, ensure_ascii=False)
    filename = f"squidmanager-backup-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.json"

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
    _: Admin = Depends(_require_admin),
):
    """Restaurar configuración desde un archivo JSON de backup de SquidManager."""
    try:
        content = await file.read()
        backup = json.loads(content.decode("utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Archivo JSON inválido")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error leyendo archivo: {e}")

    if "metadata" not in backup or "platform" not in backup["metadata"]:
        raise HTTPException(status_code=400, detail="No es un backup válido de SquidManager")

    results = {"settings": 0, "acls": 0, "rules": 0, "users": 0, "delay_pools": 0, "ldap": False}

    # Restaurar settings (upsert)
    for s in backup.get("squid_settings", []):
        existing = db.query(SquidSetting).filter(SquidSetting.key == s["key"]).first()
        if existing:
            existing.value = s["value"]
        else:
            db.add(SquidSetting(**s))
        results["settings"] += 1

    # Restaurar ACLs (upsert por nombre)
    for a in backup.get("acls", []):
        existing = db.query(Acl).filter(Acl.name == a["name"]).first()
        if existing:
            existing.type = a["type"]
            existing.value = a["value"]
            existing.description = a.get("description")
            existing.enabled = a["enabled"]
        else:
            db.add(Acl(**a))
        results["acls"] += 1

    # Restaurar reglas (reemplazar todas)
    if backup.get("access_rules"):
        db.query(AccessRule).delete()
        for r in backup["access_rules"]:
            db.add(AccessRule(
                action=r["action"], acl_names=r["acl_names"],
                order=r["order"], description=r.get("description"),
                enabled=r["enabled"],
            ))
        results["rules"] = len(backup["access_rules"])

    # Restaurar usuarios (upsert por username) - sin contraseña, marcar para reset
    for u in backup.get("proxy_users", []):
        existing = db.query(ProxyUser).filter(ProxyUser.username == u["username"]).first()
        if not existing:
            # Crear con contraseña temporal - el admin debe resetearla
            temp_hash = get_password_hash("changeme123")
            db.add(ProxyUser(
                username=u["username"], password_hash=temp_hash,
                htpasswd_hash="", enabled=u["enabled"],
                expires_at=datetime.fromisoformat(u["expires_at"]) if u.get("expires_at") else None,
            ))
            results["users"] += 1
        else:
            existing.enabled = u["enabled"]

    # Restaurar delay pools (reemplazar todos)
    if backup.get("delay_pools"):
        db.query(DelayPool).delete()
        for dp in backup["delay_pools"]:
            db.add(DelayPool(**dp))
        results["delay_pools"] = len(backup["delay_pools"])

    # Restaurar LDAP
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
            db.add(LdapConfig(**ldap_data))
        results["ldap"] = True

    db.commit()
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
    filename = f"squid.conf-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"

    return PlainTextResponse(
        config_text,
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ============================================
# IMPORTAR squid.conf tradicional
# ============================================

# Patrones para parsear squid.conf tradicional
ACL_PATTERN = re.compile(
    r'^acl\s+(\S+)\s+(\S+)\s+(.+)$'
)
RULE_PATTERN = re.compile(
    r'^http_access\s+(\S+)\s+(.+)$'
)
DELAY_POOL_PATTERN = re.compile(
    r'^delay_class\s+(\d+)\s+(\d+)$'
)
DELAY_PARAMS_PATTERN = re.compile(
    r'^delay_parameters\s+(\d+)\s+(.+)$'
)
DELAY_ACCESS_PATTERN = re.compile(
    r'^delay_access\s+(\d+)\s+(\S+)\s+(.+)$'
)
SETTING_PATTERNS = {
    "http_port": re.compile(r'^http_port\s+(\S+)', re.MULTILINE),
    "cache_mem": re.compile(r'^cache_mem\s+(\S+\s*\S*)', re.MULTILINE),
    "cache_dir": re.compile(r'^cache_dir\s+(.+)', re.MULTILINE),
    "maximum_object_size": re.compile(r'^maximum_object_size\s+(\S+\s*\S*)', re.MULTILINE),
    "visible_hostname": re.compile(r'^visible_hostname\s+(\S+)', re.MULTILINE),
    "auth_realm": re.compile(r'^auth_realm\s+(.+)', re.MULTILINE),
    "auth_children": re.compile(r'^auth_children\s+(\d+)', re.MULTILINE),
    "refresh_pattern": re.compile(r'^refresh_pattern\s+(.+)', re.MULTILINE),
    "credentialsttl": re.compile(r'^credentialsttl\s+(\S+\s*\S*)', re.MULTILINE),
    "access_log": re.compile(r'^access_log\s+(\S+)', re.MULTILINE),
    "cache_log": re.compile(r'^cache_log\s+(\S+)', re.MULTILINE),
    "cache_store_log": re.compile(r'^cache_store_log\s+(\S+)', re.MULTILINE),
}


@router.post("/import-squid-conf")
async def import_squid_conf(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: Admin = Depends(_require_admin),
):
    """Importar un squid.conf tradicional a SquidManager.

    Parsea ACLs, reglas http_access, delay pools y settings básicos.
    Las configuraciones complejas pueden no importarse perfectamente.
    Los usuarios (htpasswd) NO se importan (están en otro archivo).
    """
    try:
        content = await file.read()
        text = content.decode("utf-8", errors="replace")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error leyendo archivo: {e}")

    results = {"acls": 0, "rules": 0, "delay_pools": 0, "settings": 0, "warnings": []}
    existing_acl_names = set(a.name for a in db.query(Acl).all())

    # Parsear líneas
    for line in text.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # ACLs
        m = ACL_PATTERN.match(line)
        if m:
            name, acl_type, value = m.group(1), m.group(2), m.group(3).strip()
            # Filtrar ACLs internas de SquidManager
            if name in ("all", "localhost", "to_localhost", "SSL_ports", "Safe_ports",
                        "CONNECT", "localnet", "authenticated", "step1", "step2", "step3"):
                continue
            if name.startswith("sni_"):
                continue

            if name not in existing_acl_names:
                db.add(Acl(name=name, type=acl_type, value=value, description=f"Importado de squid.conf", enabled=True))
                existing_acl_names.add(name)
                results["acls"] += 1
            continue

        # Reglas http_access
        m = RULE_PATTERN.match(line)
        if m:
            action, acl_names = m.group(1), m.group(2).strip()
            if action not in ("allow", "deny"):
                continue
            # Filtrar reglas internas
            if "all" == acl_names and action == "deny":
                continue  # deny all del final

            max_order = db.query(AccessRule).count()
            db.add(AccessRule(
                action=action, acl_names=acl_names,
                order=max_order, description="Importado de squid.conf", enabled=True,
            ))
            results["rules"] += 1
            continue

    # Parsear settings con regex
    for key, pattern in SETTING_PATTERNS.items():
        m = pattern.search(text)
        if m:
            value = m.group(1).strip()
            existing = db.query(SquidSetting).filter(SquidSetting.key == key).first()
            if existing:
                existing.value = value
            else:
                db.add(SquidSetting(key=key, value=value, category="imported", description="Importado de squid.conf"))
            results["settings"] += 1

    # Parsear delay pools
    delay_classes = {}
    delay_params = {}
    for line in text.split("\n"):
        line = line.strip()
        m = DELAY_POOL_PATTERN.match(line)
        if m:
            pool_num, pool_class = int(m.group(1)), int(m.group(2))
            delay_classes[pool_num] = pool_class

        m = DELAY_PARAMS_PATTERN.match(line)
        if m:
            pool_num, params = int(m.group(1)), m.group(2).strip()
            delay_params[pool_num] = params

    for pool_num, pool_class in delay_classes.items():
        params = delay_params.get(pool_num, "")
        db.add(DelayPool(
            pool_class=pool_class, parameters=params,
            acl_name="", description=f"Pool {pool_num} importado de squid.conf", enabled=True,
        ))
        results["delay_pools"] += 1

    db.commit()

    # Advertencias
    if results["acls"] == 0 and results["rules"] == 0:
        results["warnings"].append("No se encontraron ACLs o reglas para importar")
    results["warnings"].append("Los usuarios (htpasswd) no se importan. Debes crearlos manualmente.")
    results["warnings"].append("Revisa las ACLs y reglas importadas antes de aplicar cambios.")

    return {"status": "ok", "message": "squid.conf importado", "details": results}