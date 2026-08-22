"""Rutas de gestión de usuarios del proxy."""

import subprocess
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.admin import Admin
from app.models.proxy_user import ProxyUser
from app.models.audit_log import AuditLog
from app.schemas.proxy_user import (
    ProxyUserCreate, ProxyUserUpdate, ProxyUserResponse,
)
from app.services.auth_service import get_password_hash, get_current_admin
from app.services.squid_service import write_passwd_file, reload_squid
from app.services.notification_service import queue_notification

router = APIRouter()


def _generate_htpasswd_hash(username: str, password: str) -> str:
    """Genera un hash htpasswd usando el comando htpasswd del sistema."""
    try:
        result = subprocess.run(
            ["htpasswd", "-nbB", username, password],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            # htpasswd -nbB devuelve: usuario:$2y$...
            return result.stdout.strip()
    except Exception:
        pass
    return f"{username}:$2y$INVALID"


def _sync_passwd_and_reload(db: Session):
    """Regenera el archivo htpasswd y recarga Squid."""
    users = db.query(ProxyUser).filter(ProxyUser.enabled == True).all()
    # Pasar username + htpasswd_hash al servicio
    user_dicts = [
        {
            "username": u.username,
            "password": None,  # No usamos texto plano
            "htpasswd_hash": u.htpasswd_hash,
            "enabled": u.enabled,
        }
        for u in users
    ]
    _write_htpasswd_file(user_dicts)
    reload_squid()


def _write_htpasswd_file(users: list[dict], path: str = "/etc/squid/squid_passwd") -> bool:
    """Escribe el archivo htpasswd directamente con los hashes ya generados."""
    from pathlib import Path
    try:
        passwd_path = Path(path)
        passwd_path.parent.mkdir(parents=True, exist_ok=True)
        with open(passwd_path, "w") as f:
            for user in users:
                if user.get("enabled", True) and user.get("htpasswd_hash"):
                    f.write(f"{user['htpasswd_hash']}\n")
        return True
    except Exception as e:
        import logging
        logging.error(f"Error escribiendo passwd file: {e}")
        return False


@router.get("/", response_model=list[ProxyUserResponse])
async def list_proxy_users(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Lista todos los usuarios del proxy."""
    return db.query(ProxyUser).order_by(ProxyUser.username).all()


@router.post("/", response_model=ProxyUserResponse, status_code=201)
async def create_proxy_user(
    data: ProxyUserCreate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    background_tasks: BackgroundTasks = None,
):
    """Crea un nuevo usuario del proxy."""
    existing = db.query(ProxyUser).filter(ProxyUser.username == data.username).first()
    if existing:
        raise HTTPException(400, detail="El usuario ya existe")

    # Generar ambos hashes
    bcrypt_hash = get_password_hash(data.password)
    htpasswd_line = _generate_htpasswd_hash(data.username, data.password)

    user = ProxyUser(
        username=data.username,
        password_hash=bcrypt_hash,
        htpasswd_hash=htpasswd_line,
        enabled=data.enabled,
        expires_at=data.expires_at,
    )
    db.add(user)
    db.flush()

    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="create", entity="proxy_user", entity_id=user.id,
        new_value=user.username,
    ))
    db.commit()

    _sync_passwd_and_reload(db)

    if background_tasks:
        queue_notification(background_tasks, db, "user_change",
                           "Usuario de proxy creado",
                           f"El admin {current_admin.username} creó el usuario '{data.username}'.")
    return user


@router.put("/{user_id}", response_model=ProxyUserResponse)
async def update_proxy_user(
    user_id: int,
    data: ProxyUserUpdate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    background_tasks: BackgroundTasks = None,
):
    """Actualiza un usuario del proxy."""
    user = db.query(ProxyUser).filter(ProxyUser.id == user_id).first()
    if not user:
        raise HTTPException(404, detail="Usuario no encontrado")

    if data.password is not None:
        user.password_hash = get_password_hash(data.password)
        user.htpasswd_hash = _generate_htpasswd_hash(user.username, data.password)
    if data.enabled is not None:
        user.enabled = data.enabled
    if data.expires_at is not None:
        user.expires_at = data.expires_at

    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="update", entity="proxy_user", entity_id=user.id,
    ))
    db.commit()

    _sync_passwd_and_reload(db)

    if background_tasks:
        queue_notification(background_tasks, db, "user_change",
                           "Usuario de proxy actualizado",
                           f"El admin {current_admin.username} actualizó el usuario '{user.username}'.")
    return user


@router.delete("/{user_id}", status_code=204)
async def delete_proxy_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    background_tasks: BackgroundTasks = None,
):
    """Elimina un usuario del proxy."""
    user = db.query(ProxyUser).filter(ProxyUser.id == user_id).first()
    if not user:
        raise HTTPException(404, detail="Usuario no encontrado")

    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="delete", entity="proxy_user", entity_id=user.id,
        old_value=user.username,
    ))
    db.delete(user)
    db.commit()

    _sync_passwd_and_reload(db)

    if background_tasks:
        queue_notification(background_tasks, db, "user_change",
                           "Usuario de proxy eliminado",
                           f"El admin {current_admin.username} eliminó el usuario '{user.username}'.")


@router.patch("/{user_id}/toggle", response_model=ProxyUserResponse)
async def toggle_proxy_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
    background_tasks: BackgroundTasks = None,
):
    """Habilita/deshabilita un usuario del proxy."""
    user = db.query(ProxyUser).filter(ProxyUser.id == user_id).first()
    if not user:
        raise HTTPException(404, detail="Usuario no encontrado")

    user.enabled = not user.enabled
    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="toggle", entity="proxy_user", entity_id=user.id,
        new_value=str(user.enabled),
    ))
    db.commit()

    _sync_passwd_and_reload(db)

    if background_tasks:
        estado = "habilitó" if user.enabled else "deshabilitó"
        queue_notification(background_tasks, db, "user_change",
                           "Usuario de proxy modificado",
                           f"El admin {current_admin.username} {estado} el usuario '{user.username}'.")
    return user