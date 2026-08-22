"""Rutas de configuración LDAP/Active Directory."""

import subprocess
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.admin import Admin
from app.models.ldap_config import LdapConfig
from app.models.ldap_user import LdapUser
from app.services.auth_service import get_current_admin
from app.services.squid_service import write_ldap_aux_files, reload_squid

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

    # Escribir archivos auxiliares (ldap_helper.conf) y recargar Squid
    allowed = [u.username for u in db.query(LdapUser).filter(LdapUser.enabled == True).all()]
    write_ldap_aux_files(config, allowed)
    reload_squid()

    return {"status": "ok", "message": "Configuración LDAP guardada"}


class LdapTestRequest(BaseModel):
    server_url: str
    bind_dn: str
    bind_password: str
    search_base: str
    user_filter: str = "(uid=%s)"
    username: str
    password: str


@router.post("/test")
async def test_ldap_connection(
    data: LdapTestRequest,
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Prueba la conexión LDAP y la autenticación de un usuario usando ldap3.

    Pasos:
      1. Conectar al servidor y hacer bind con la cuenta de servicio (bind_dn).
      2. Buscar el usuario con el filtro configurado (user_filter).
      3. Autenticar como el usuario encontrado (con su contraseña).
    """
    from ldap3 import Server, Connection, SUBTREE

    results = []

    # Si la contraseña de bind viene enmascarada, usar la guardada en BD
    bind_password = data.bind_password
    if bind_password == "***":
        saved = db.query(LdapConfig).first()
        if saved:
            bind_password = saved.bind_password

    # 1. Conectar al servidor
    try:
        server = Server(data.server_url, connect_timeout=10)
    except Exception as e:
        results.append({"step": "Conexión LDAP", "status": "error",
                        "detail": f"URL de servidor inválida: {e}"})
        return {"results": results, "success": False}

    # 2. Bind con la cuenta de servicio
    try:
        conn = Connection(server, user=data.bind_dn, password=bind_password,
                          auto_bind=True, receive_timeout=10)
    except Exception as e:
        results.append({"step": "Conexión LDAP", "status": "error",
                        "detail": f"Error de conexión o bind: {e}"})
        return {"results": results, "success": False}

    if not conn.bound:
        results.append({"step": "Conexión LDAP", "status": "error",
                        "detail": "Bind fallido: revisa el servidor, bind_dn y la contraseña"})
        return {"results": results, "success": False}

    results.append({"step": "Conexión LDAP", "status": "ok",
                    "detail": "Conexión y bind con la cuenta de servicio exitosos"})

    # 3. Buscar el usuario con el filtro configurado
    search_filter = data.user_filter.replace("%s", data.username) if "%s" in data.user_filter else data.user_filter
    try:
        conn.search(search_base=data.search_base, search_filter=search_filter,
                    search_scope=SUBTREE, attributes=["cn", "mail", "sAMAccountName", "uid", "userPrincipalName"])
    except Exception as e:
        results.append({"step": "Búsqueda de usuario", "status": "error",
                        "detail": f"Error en la búsqueda: {e}"})
        conn.unbind()
        return {"results": results, "success": False}

    if not conn.entries:
        results.append({"step": "Búsqueda de usuario", "status": "error",
                        "detail": f"Usuario '{data.username}' no encontrado con filtro '{search_filter}' en {data.search_base}"})
        conn.unbind()
        return {"results": results, "success": False}

    user_dn = conn.entries[0].entry_dn
    results.append({"step": "Búsqueda de usuario", "status": "ok",
                    "detail": f"Usuario encontrado: {user_dn}"})

    # 4. Autenticar como el usuario
    try:
        user_conn = Connection(server, user=user_dn, password=data.password,
                               auto_bind=True, receive_timeout=10)
        if user_conn.bound:
            results.append({"step": "Autenticación", "status": "ok",
                            "detail": f"Usuario autenticado correctamente como {user_dn}"})
            user_conn.unbind()
            conn.unbind()
            return {"results": results, "success": True}
        else:
            results.append({"step": "Autenticación", "status": "error",
                            "detail": "Contraseña de usuario incorrecta"})
            conn.unbind()
            return {"results": results, "success": False}
    except Exception as e:
        results.append({"step": "Autenticación", "status": "error",
                        "detail": f"Contraseña incorrecta o error de autenticación: {e}"})
        conn.unbind()
        return {"results": results, "success": False}


# ============================================================
# Gestión de usuarios LDAP (allow-list estricto)
# ============================================================

class LdapUserResponse(BaseModel):
    id: int
    username: str
    display_name: str | None
    email: str | None
    enabled: bool

    class Config:
        from_attributes = True


def _sync_ldap_files(db: Session):
    """Escribe los archivos auxiliares de LDAP y recarga Squid."""
    config = db.query(LdapConfig).first()
    allowed = [u.username for u in db.query(LdapUser).filter(LdapUser.enabled == True).all()]
    write_ldap_aux_files(config, allowed)
    reload_squid()


@router.get("/users", response_model=list[LdapUserResponse])
async def list_ldap_users(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Lista los usuarios LDAP sincronizados (allow-list)."""
    return db.query(LdapUser).order_by(LdapUser.username).all()


@router.post("/sync")
async def sync_ldap_users(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """Sincroniza los usuarios desde LDAP/Active Directory.

    - Importa (upsert) todos los usuarios del directorio a la tabla ldap_users.
    - Los usuarios nuevos se crean con enabled=False (allow-list estricto).
    - NO almacena contraseñas; solo username, nombre y email.
    """
    config = db.query(LdapConfig).first()
    if not config or not config.enabled:
        raise HTTPException(400, detail="LDAP no está configurado o está deshabilitado")

    from ldap3 import Server, Connection, SUBTREE

    try:
        server = Server(config.server_url, connect_timeout=10)
        conn = Connection(server, user=config.bind_dn, password=config.bind_password,
                          auto_bind=True, receive_timeout=15)
    except Exception as e:
        raise HTTPException(400, detail=f"Error conectando a LDAP: {e}")

    try:
        conn.search(search_base=config.search_base,
                    search_filter="(objectClass=user)",
                    search_scope=SUBTREE,
                    attributes=["sAMAccountName", "uid", "cn", "mail"])
    except Exception as e:
        conn.unbind()
        raise HTTPException(400, detail=f"Error buscando usuarios: {e}")

    synced = 0
    for entry in conn.entries:
        # En AD el login es sAMAccountName; en OpenLDAP suele ser uid
        sam = entry.sAMAccountName.value if entry.sAMAccountName else None
        uid = entry.uid.value if entry.uid else None
        username = sam or uid
        if not username:
            continue
        # Omitir cuentas de máquina (acaban en $) y cuentas del sistema
        if username.endswith("$") or username.lower() in ("krbtgt", "guest", "invitado"):
            continue

        cn = entry.cn.value if entry.cn else None
        mail = entry.mail.value if entry.mail else None

        existing = db.query(LdapUser).filter(LdapUser.username == username).first()
        if existing:
            existing.display_name = cn
            existing.email = mail
        else:
            # allow-list estricto: nuevos usuarios deshabilitados por defecto
            db.add(LdapUser(username=username, display_name=cn, email=mail, enabled=False))
        synced += 1

    conn.unbind()
    db.commit()

    _sync_ldap_files(db)

    return {"status": "ok", "synced": synced}


@router.patch("/users/{user_id}/toggle", response_model=LdapUserResponse)
async def toggle_ldap_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """Habilita/deshabilita un usuario LDAP (controla la allow-list)."""
    user = db.query(LdapUser).filter(LdapUser.id == user_id).first()
    if not user:
        raise HTTPException(404, detail="Usuario LDAP no encontrado")

    user.enabled = not user.enabled
    db.commit()

    _sync_ldap_files(db)

    return user