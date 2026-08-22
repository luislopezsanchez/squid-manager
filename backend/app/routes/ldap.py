"""Rutas de configuración LDAP/Active Directory."""

import subprocess
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db, SessionLocal
from app.models.admin import Admin
from app.models.ldap_config import LdapConfig
from app.services.auth_service import get_current_admin

logger = logging.getLogger(__name__)
router = APIRouter()


class LdapConfigUpdate(BaseModel):
    server_url: str
    bind_dn: str
    bind_password: str
    search_base: str
    user_filter: str = "(uid=%s)"
    enabled: bool = False


@router.get("/config")
async def get_ldap_config(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Obtiene la configuración LDAP actual."""
    config = db.query(LdapConfig).first()
    if not config:
        return {
            "server_url": "",
            "bind_dn": "",
            "bind_password": "",
            "search_base": "",
            "user_filter": "(uid=%s)",
            "enabled": False,
        }
    return {
        "id": config.id,
        "server_url": config.server_url,
        "bind_dn": config.bind_dn,
        "bind_password": "***" if config.bind_password else "",
        "search_base": config.search_base,
        "user_filter": config.user_filter,
        "enabled": config.enabled,
    }


@router.put("/config")
async def update_ldap_config(
    data: LdapConfigUpdate,
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Actualiza la configuración LDAP."""
    config = db.query(LdapConfig).first()
    if config:
        config.server_url = data.server_url
        config.bind_dn = data.bind_dn
        # No sobrescribir la contraseña si viene ***
        if data.bind_password and data.bind_password != "***":
            config.bind_password = data.bind_password
        config.search_base = data.search_base
        config.user_filter = data.user_filter
        config.enabled = data.enabled
    else:
        config = LdapConfig(
            id=1,
            server_url=data.server_url,
            bind_dn=data.bind_dn,
            bind_password=data.bind_password if data.bind_password != "***" else "",
            search_base=data.search_base,
            user_filter=data.user_filter,
            enabled=data.enabled,
        )
        db.add(config)
    db.commit()
    return {"status": "ok", "message": "Configuración LDAP guardada"}


class LdapTestRequest(BaseModel):
    server_url: str
    bind_dn: str
    bind_password: str
    search_base: str
    username: str
    password: str


@router.post("/test")
async def test_ldap_connection(
    data: LdapTestRequest,
    _: Admin = Depends(get_current_admin),
):
    """Prueba la conexión LDAP y la autenticación de un usuario."""
    results = []

    # 1. Probar conexión con ldapsearch
    try:
        cmd = [
            "ldapsearch", "-x", "-H", data.server_url,
            "-D", data.bind_dn, "-w", data.bind_password,
            "-b", data.search_base,
            "-s", "sub",
            f"(uid={data.username})",
            "dn", "cn", "mail",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            results.append({"step": "Conexión LDAP", "status": "ok", "detail": "Bind exitoso"})
            # Ver si se encontró el usuario
            if "dn:" in result.stdout:
                lines = [l for l in result.stdout.split("\n") if l.startswith("dn:")]
                results.append({
                    "step": "Búsqueda de usuario",
                    "status": "ok",
                    "detail": f"Usuario encontrado: {lines[0].replace('dn: ', '')}"
                })
            else:
                results.append({
                    "step": "Búsqueda de usuario",
                    "status": "error",
                    "detail": f"Usuario '{data.username}' no encontrado en {data.search_base}"
                })
                return {"results": results, "success": False}
        else:
            stderr = result.stderr.strip()
            results.append({"step": "Conexión LDAP", "status": "error", "detail": stderr[:200]})
            return {"results": results, "success": False}
    except FileNotFoundError:
        results.append({"step": "Conexión LDAP", "status": "error", "detail": "ldapsearch no instalado en el contenedor"})
        return {"results": results, "success": False}
    except subprocess.TimeoutExpired:
        results.append({"step": "Conexión LDAP", "status": "error", "detail": "Timeout conectando al servidor LDAP"})
        return {"results": results, "success": False}
    except Exception as e:
        results.append({"step": "Conexión LDAP", "status": "error", "detail": str(e)})
        return {"results": results, "success": False}

    # 2. Probar autenticación del usuario con ldapwhoami
    try:
        # Buscar el DN del usuario primero
        user_dn = None
        for line in result.stdout.split("\n"):
            if line.startswith("dn:"):
                user_dn = line.replace("dn: ", "").strip()
                break

        if not user_dn:
            results.append({"step": "Autenticación", "status": "error", "detail": "No se pudo obtener el DN del usuario"})
            return {"results": results, "success": False}

        cmd = ["ldapwhoami", "-x", "-H", data.server_url, "-D", user_dn, "-w", data.password]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            results.append({"step": "Autenticación", "status": "ok", "detail": f"Usuario autenticado como {result.stdout.strip()}"})
            return {"results": results, "success": True}
        else:
            results.append({"step": "Autenticación", "status": "error", "detail": "Contraseña incorrecta o usuario no válido"})
            return {"results": results, "success": False}
    except Exception as e:
        results.append({"step": "Autenticación", "status": "error", "detail": str(e)})
        return {"results": results, "success": False}