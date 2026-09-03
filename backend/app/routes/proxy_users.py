"""Rutas de gestión de usuarios del proxy."""

import re
import secrets
import string
import subprocess

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.admin import Admin
from app.models.proxy_user import ProxyUser
from app.models.audit_log import AuditLog
from app.models.user_group import UserGroupMember
from app.schemas.proxy_user import (
    ProxyUserCreate, ProxyUserUpdate, ProxyUserResponse,
)
from app.services.auth_service import get_password_hash, get_current_admin, require_writer
from app.services.squid_service import (
    write_passwd_file, reload_squid, purge_credentials, active_proxy_users,
)
from app.services.notification_service import queue_notification
from app.services.config_state import mark_dirty
from app.utils import utcnow, as_naive_utc

router = APIRouter()

USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def _validate_username(username: str) -> str:
    """El nombre acaba en el fichero htpasswd y en las ACLs proxy_auth."""
    username = (username or "").strip()
    if not USERNAME_PATTERN.match(username):
        raise HTTPException(
            400,
            detail=(
                "Nombre de usuario inválido: usa entre 1 y 64 caracteres, solo "
                "letras, números, punto, guion y guion bajo."
            ),
        )
    return username


def _generate_htpasswd_hash(username: str, password: str) -> str:
    """Genera la línea htpasswd (usuario:hash) para el fichero de Squid.

    El coste de bcrypt se toma de la configuración: htpasswd usa 5 por
    defecto, muy por debajo de lo recomendado.
    """
    try:
        result = subprocess.run(
            ["htpasswd", "-nbBC", str(settings.BCRYPT_COST), username, password],
            capture_output=True, text=True, timeout=15,
        )
    except FileNotFoundError:
        # El remedio depende del despliegue, y decir el equivocado hace perder
        # el tiempo: en una instalación nativa no hay ninguna imagen que
        # reconstruir, hay que instalar el paquete que trae htpasswd.
        from app.services.runtime import get_runtime

        if get_runtime().name == "native":
            remedio = "Instala el paquete apache2-utils: sudo apt install apache2-utils"
        else:
            remedio = "Reconstruye la imagen del backend."
        raise HTTPException(
            500,
            detail=f"No se encontró el comando htpasswd en el backend. {remedio}",
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(500, detail="htpasswd tardó demasiado en responder.")

    if result.returncode != 0 or ":" not in result.stdout:
        # Antes se guardaba '$2y$INVALID' y el usuario aparecía creado pero
        # no podía autenticarse nunca, sin ningún aviso.
        raise HTTPException(
            500,
            detail=f"No se pudo generar la contraseña del proxy: {result.stderr.strip() or 'error desconocido'}",
        )
    return result.stdout.strip()


def _sync_passwd(db: Session):
    """Regenera el archivo htpasswd. No recarga Squid, y no hace falta.

    El helper de autenticación (`squid/auth_helper.py`) abre este fichero en
    cada petición, así que un usuario nuevo puede entrar en cuanto se escribe:
    comprobado añadiendo una línea a mano y navegando sin tocar Squid.

    Antes esto llamaba a `reload_squid()`, y ese `squid -k reconfigure` reinicia
    los helpers de autenticación: unos 200 ms en los que el proxy rechaza
    conexiones. El síntoma era desconcertante —crear el primer usuario y que la
    primera navegación fallara con «Failed to connect», funcionando al
    reintentar— y no servía para nada.

    Tampoco aportaba nada al quitar acceso a alguien: `reconfigure` **no** purga
    la caché de credenciales de Squid (medido: un usuario borrado del htpasswd
    sigue navegando después de un reconfigure, y solo deja de hacerlo tras el
    reinicio completo). De eso se encarga `purge_credentials()`, que reinicia
    Squid a propósito y que estas rutas ya llaman cuando toca.
    """
    write_passwd_file(db)


@router.get("/", response_model=list[ProxyUserResponse])
async def list_proxy_users(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Lista todos los usuarios del proxy."""
    active_ids = {u.id for u in active_proxy_users(db)}
    users = db.query(ProxyUser).order_by(ProxyUser.username).all()
    # `active` distingue «habilitado» de «puede navegar ahora»: un usuario
    # habilitado pero caducado no puede.
    for u in users:
        u.active = u.id in active_ids
    return users


@router.post("/", response_model=ProxyUserResponse, status_code=201)
async def create_proxy_user(
    data: ProxyUserCreate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
    background_tasks: BackgroundTasks = None,
):
    """Crea un nuevo usuario del proxy."""
    username = _validate_username(data.username)

    existing = db.query(ProxyUser).filter(ProxyUser.username == username).first()
    if existing:
        raise HTTPException(400, detail="El usuario ya existe")

    htpasswd_line = _generate_htpasswd_hash(username, data.password)

    user = ProxyUser(
        username=username,
        password_hash=get_password_hash(data.password),
        htpasswd_hash=htpasswd_line,
        enabled=data.enabled,
        expires_at=as_naive_utc(data.expires_at),
    )
    db.add(user)
    db.flush()

    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="create", entity="proxy_user", entity_id=user.id,
        new_value=user.username,
    ))
    # Se escribe el htpasswd ANTES de comprometer el commit: si la escritura
    # falla (disco lleno, permisos), la excepción aborta la petición y la
    # sesión se descarta sin persistir un usuario que Squid nunca vería.
    _sync_passwd(db)
    db.commit()

    user.active = True

    if background_tasks:
        queue_notification(background_tasks, db, "user_change",
                           "Usuario de proxy creado",
                           f"El admin {current_admin.username} creó el usuario '{username}'.")
    return user


@router.put("/{user_id}", response_model=ProxyUserResponse)
async def update_proxy_user(
    user_id: int,
    data: ProxyUserUpdate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
    background_tasks: BackgroundTasks = None,
):
    """Actualiza un usuario del proxy."""
    user = db.query(ProxyUser).filter(ProxyUser.id == user_id).first()
    if not user:
        raise HTTPException(404, detail="Usuario no encontrado")

    revoke = False
    if data.password is not None:
        user.password_hash = get_password_hash(data.password)
        user.htpasswd_hash = _generate_htpasswd_hash(user.username, data.password)
        revoke = True
    if data.enabled is not None and data.enabled != user.enabled:
        user.enabled = data.enabled
        if not data.enabled:
            revoke = True
    if data.expires_at is not None:
        user.expires_at = as_naive_utc(data.expires_at)
        if user.expires_at <= utcnow():
            revoke = True

    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="update", entity="proxy_user", entity_id=user.id,
        new_value=user.username,
    ))
    _sync_passwd(db)
    db.commit()

    # Squid guarda las credenciales validadas en caché (credentialsttl): sin
    # purgarlas, quitarle el acceso a alguien no surte efecto hasta dos horas.
    if revoke:
        purge_credentials()

    user.active = user.id in {u.id for u in active_proxy_users(db)}

    if background_tasks:
        queue_notification(background_tasks, db, "user_change",
                           "Usuario de proxy actualizado",
                           f"El admin {current_admin.username} actualizó el usuario '{user.username}'.")
    return user


@router.delete("/{user_id}", status_code=204)
async def delete_proxy_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
    background_tasks: BackgroundTasks = None,
):
    """Elimina un usuario del proxy."""
    user = db.query(ProxyUser).filter(ProxyUser.id == user_id).first()
    if not user:
        raise HTTPException(404, detail="Usuario no encontrado")

    username = user.username
    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="delete", entity="proxy_user", entity_id=user.id,
        old_value=username,
    ))
    # Quitarlo también de los grupos: si no, seguía apareciendo en las ACLs
    # proxy_auth del squid.conf y un usuario nuevo con el mismo nombre
    # heredaba su pertenencia.
    removed = db.query(UserGroupMember).filter(UserGroupMember.username == username).delete()
    db.delete(user)
    _sync_passwd(db)
    db.commit()

    purge_credentials()
    if removed:
        mark_dirty()

    if background_tasks:
        queue_notification(background_tasks, db, "user_change",
                           "Usuario de proxy eliminado",
                           f"El admin {current_admin.username} eliminó el usuario '{username}'.")


@router.patch("/{user_id}/toggle", response_model=ProxyUserResponse)
async def toggle_proxy_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
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
    _sync_passwd(db)
    db.commit()

    if not user.enabled:
        purge_credentials()

    user.active = user.id in {u.id for u in active_proxy_users(db)}

    if background_tasks:
        estado = "habilitó" if user.enabled else "deshabilitó"
        queue_notification(background_tasks, db, "user_change",
                           "Usuario de proxy modificado",
                           f"El admin {current_admin.username} {estado} el usuario '{user.username}'.")
    return user


@router.post("/sync")
async def sync_passwd_endpoint(
    db: Session = Depends(get_db),
    _: Admin = Depends(require_writer),
):
    """Regenera el fichero de contraseñas y recarga Squid.

    Aplica las caducidades que hayan vencido desde la última escritura.
    """
    count = write_passwd_file(db)
    ok, message = reload_squid()
    return {
        "status": "ok" if ok else "warning",
        "message": f"{count} usuarios activos. {message}",
        "active_users": count,
    }


@router.post("/{user_id}/reset-password")
async def reset_password(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
):
    """Resetea la contraseña de un usuario (fuerza re-autenticación real).

    Genera una contraseña nueva, actualiza squid_passwd y reinicia Squid
    para purgar la caché de credenciales. Así el navegador del usuario,
    al reintentar con la contraseña vieja, será rechazado (407) y le
    pedirá las credenciales nuevas.
    """
    user = db.query(ProxyUser).filter(ProxyUser.id == user_id).first()
    if not user:
        raise HTTPException(404, detail="Usuario no encontrado")

    alphabet = string.ascii_letters + string.digits
    new_password = "".join(secrets.choice(alphabet) for _ in range(16))

    user.password_hash = get_password_hash(new_password)
    user.htpasswd_hash = _generate_htpasswd_hash(user.username, new_password)

    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="reset_password", entity="proxy_user", entity_id=user.id,
        new_value=user.username,
    ))
    _sync_passwd(db)
    db.commit()

    purge_credentials()

    return {
        "status": "ok",
        "message": f"Contraseña de '{user.username}' reseteada. El usuario deberá re-autenticarse.",
        "new_password": new_password,
    }
