"""Rutas de gestión de usuarios del proxy."""

import hashlib
import re
import secrets
import string
import subprocess

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, File, Form, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.admin import Admin
from app.models.proxy_user import ProxyUser
from app.models.ldap_user import LdapUser
from app.models.audit_log import AuditLog
from app.models.user_group import UserGroupMember
from app.schemas.proxy_user import (
    ProxyUserCreate, ProxyUserUpdate, ProxyUserResponse,
)
from app.services.auth_service import get_password_hash, get_current_admin, require_writer
from app.services.squid_service import (
    write_passwd_file, write_digest_file, reload_squid, purge_credentials, active_proxy_users,
    realm_actual,
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


def _validate_email(email: str | None) -> str | None:
    """Correo opcional: vacío -> None; si viene, formato razonable."""
    email = (email or "").strip()
    if not email:
        return None
    from app.services.user_import_service import EMAIL_PATTERN

    if len(email) > 255 or not EMAIL_PATTERN.match(email):
        raise HTTPException(400, detail="Correo electrónico inválido.")
    return email


def _revocar(background_tasks: BackgroundTasks | None) -> None:
    """Purga la caché de credenciales de Squid (reinicia Squid: unos segundos).

    Se hace DESPUÉS de responder cuando hay `background_tasks`: el cambio ya
    está guardado y el htpasswd escrito, así que lo único pendiente es que
    Squid deje de confiar en validaciones viejas. Antes el admin esperaba el
    reinicio completo mirando un botón «Aplicando…».
    """
    if background_tasks is not None:
        background_tasks.add_task(purge_credentials)
    else:
        purge_credentials()


def _generate_digest_ha1(username: str, password: str, realm: str) -> str:
    """HA1 = MD5(usuario:realm:password), tal como lo espera digest_file_auth.

    MD5 aquí no es una elección de seguridad nuestra: es el algoritmo que fija
    RFC 2617 para HTTP Digest Auth, y Squid no ofrece variante. Nunca se
    guarda la contraseña en claro para esto: se calcula una sola vez, en el
    momento en que el backend ya la recibió para el htpasswd de Basic.
    """
    return hashlib.md5(f"{username}:{realm}:{password}".encode("utf-8")).hexdigest()


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
    # La sesión tiene autoflush=False: sin este flush, active_proxy_users()
    # (que write_passwd_file llama por dentro) vería el enabled/expires_at
    # VIEJO de cualquier cambio pendiente en esta misma sesión, y un usuario
    # recién deshabilitado o borrado se quedaría en el htpasswd hasta el
    # siguiente cambio. Antes esto se pegaba a mano en cada ruta que llama a
    # esta función; vivía aquí una sola vez, ningún call site (presente o
    # futuro) puede olvidarlo.
    db.flush()
    write_passwd_file(db)
    write_digest_file(db, realm_actual(db))


@router.get("/", response_model=list[ProxyUserResponse])
def list_proxy_users(
    limit: int = Query(1000, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Lista los usuarios del proxy, paginados.

    limit por defecto en 1000 -generoso a proposito, para no romper a los
    consumidores actuales de la API que no mandan estos parametros- pero
    ya no "todos sin tope": con miles de usuarios (auditoria 2026-09-09,
    hallazgo 09-001) la respuesta sin paginar tarda y el frontend renderiza
    de mas.
    """
    active_ids = {u.id for u in active_proxy_users(db)}
    users = (
        db.query(ProxyUser).order_by(ProxyUser.username)
        .offset(offset).limit(limit).all()
    )
    # `active` distingue «habilitado» de «puede navegar ahora»: un usuario
    # habilitado pero caducado no puede.
    for u in users:
        u.active = u.id in active_ids
    return users


@router.post("/", response_model=ProxyUserResponse, status_code=201)
def create_proxy_user(
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
    realm = realm_actual(db)

    user = ProxyUser(
        username=username,
        display_name=(data.display_name or "").strip() or None,
        email=_validate_email(data.email),
        password_hash=get_password_hash(data.password),
        htpasswd_hash=htpasswd_line,
        digest_ha1=_generate_digest_ha1(username, data.password, realm),
        digest_ha1_realm=realm,
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
                           "Se creó un usuario del proxy",
                           f"El administrador «{current_admin.username}» creó el usuario «{username}».")
    return user


@router.put("/{user_id}", response_model=ProxyUserResponse)
def update_proxy_user(
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
    if data.display_name is not None:
        user.display_name = data.display_name.strip() or None
    if data.email is not None:
        user.email = _validate_email(data.email)
    if data.password is not None:
        realm = realm_actual(db)
        user.password_hash = get_password_hash(data.password)
        user.htpasswd_hash = _generate_htpasswd_hash(user.username, data.password)
        user.digest_ha1 = _generate_digest_ha1(user.username, data.password, realm)
        user.digest_ha1_realm = realm
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
        _revocar(background_tasks)

    user.active = user.id in {u.id for u in active_proxy_users(db)}

    if background_tasks:
        queue_notification(background_tasks, db, "user_change",
                           "Se modificó un usuario del proxy",
                           f"El administrador «{current_admin.username}» modificó al usuario «{user.username}».")
    return user


@router.delete("/{user_id}", status_code=204)
def delete_proxy_user(
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

    _revocar(background_tasks)
    if removed:
        mark_dirty()

    if background_tasks:
        queue_notification(background_tasks, db, "user_change",
                           "Se eliminó un usuario del proxy",
                           f"El administrador «{current_admin.username}» eliminó al usuario «{username}».")


@router.patch("/{user_id}/toggle", response_model=ProxyUserResponse)
def toggle_proxy_user(
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
        _revocar(background_tasks)

    user.active = user.id in {u.id for u in active_proxy_users(db)}

    if background_tasks:
        if user.enabled:
            queue_notification(background_tasks, db, "user_change", "Se habilitó un usuario del proxy",
                               f"El administrador «{current_admin.username}» habilitó al usuario «{user.username}»: ya puede navegar.")
        else:
            queue_notification(background_tasks, db, "user_change", "Se deshabilitó un usuario del proxy",
                               f"El administrador «{current_admin.username}» deshabilitó al usuario «{user.username}»: ya no puede navegar.")
    return user


@router.post("/sync")
def sync_passwd_endpoint(
    db: Session = Depends(get_db),
    _: Admin = Depends(require_writer),
):
    """Regenera el fichero de contraseñas y recarga Squid.

    Aplica las caducidades que hayan vencido desde la última escritura.
    """
    count = write_passwd_file(db)
    write_digest_file(db, realm_actual(db))
    ok, message = reload_squid()
    return {
        "status": "ok" if ok else "warning",
        "message": f"{count} usuarios activos. {message}",
        "active_users": count,
    }


@router.post("/{user_id}/reset-password")
def reset_password(
    user_id: int,
    background_tasks: BackgroundTasks,
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
    realm = realm_actual(db)

    user.password_hash = get_password_hash(new_password)
    user.htpasswd_hash = _generate_htpasswd_hash(user.username, new_password)
    user.digest_ha1 = _generate_digest_ha1(user.username, new_password, realm)
    user.digest_ha1_realm = realm

    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="reset_password", entity="proxy_user", entity_id=user.id,
        new_value=user.username,
    ))
    _sync_passwd(db)
    db.commit()

    _revocar(background_tasks)

    return {
        "status": "ok",
        "message": f"Contraseña de '{user.username}' reseteada. El usuario deberá re-autenticarse.",
        "new_password": new_password,
    }


# ---------------------------------------------------------------------------
# Acciones en bloque, importar y exportar (carga masiva)
# ---------------------------------------------------------------------------

def _contrasena_aleatoria(largo: int = 16) -> str:
    alfabeto = string.ascii_letters + string.digits
    return "".join(secrets.choice(alfabeto) for _ in range(largo))


def _hashes(username: str, password: str, realm: str) -> tuple[str, str, str]:
    """(password_hash, línea htpasswd, HA1 digest) con UNA sola pasada de
    bcrypt. `htpasswd -B` (el camino de un usuario suelto) y bcrypt de
    Python producen el mismo hash con distinta etiqueta ($2y$ vs $2b$), y
    Squid acepta las dos -ver squid/auth_helper.py-. Con el coste 12 por
    defecto son ~250 ms por hash: el camino suelto (bcrypt + subproceso
    htpasswd) tardaba el doble, y una carga de mil usuarios eran minutos."""
    pw_hash = get_password_hash(password)
    return (
        pw_hash,
        f"{username}:{pw_hash.replace('$2b$', '$2y$', 1)}",
        _generate_digest_ha1(username, password, realm),
    )


def _hashes_en_paralelo(items: list[tuple[str, str]], realm: str) -> dict[str, tuple[str, str, str]]:
    """{username: hashes}. bcrypt suelta el GIL: los hilos sí aprovechan varios núcleos."""
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=4) as ex:
        resultados = list(ex.map(lambda it: _hashes(it[0], it[1], realm), items))
    return {u: r for (u, _), r in zip(items, resultados)}


class BulkAction(BaseModel):
    action: Literal["enable", "disable", "delete", "reset_password"]
    usernames: list[str] = Field(..., min_length=1, max_length=2000)


_VERBOS_MASIVOS = {
    "enable": "habilitó",
    "disable": "deshabilitó",
    "delete": "eliminó",
    "reset_password": "generó nuevas credenciales para",
}


def _avisar_masivo(background_tasks, db, admin: str, accion: str, nombres: list[str]) -> None:
    """Aviso (correo/Telegram) de una acción aplicada a varios usuarios a la vez."""
    verbo = _VERBOS_MASIVOS.get(accion, "modificó")
    n = len(nombres)
    lista = ", ".join(nombres[:8]) + (f" y {n - 8} más" if n > 8 else "")
    # «generó nuevas credenciales para …» lleva «para», el resto lleva «a»: la frase tiene que sonar bien.
    a = "" if accion == "reset_password" else "a "
    el = "el" if accion == "reset_password" else "al"
    if n == 1:
        msg = f"El administrador «{admin}» {verbo} {el} usuario «{lista}»."
    else:
        msg = f"El administrador «{admin}» {verbo} {a}{n} usuarios: {lista}."
    queue_notification(background_tasks, db, "user_change", "Acción sobre varios usuarios", msg)


@router.post("/bulk")
def bulk_action(
    data: BulkAction,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
):
    """Aplica una acción a varios usuarios de una vez (los seleccionados de
    la tabla de Usuarios, locales y LDAP mezclados).

    - enable / disable: locales y LDAP.
    - delete / reset_password: solo locales; un usuario LDAP vive en el
      directorio, aquí solo se habilita o deshabilita (se informa en `omitidos`).

    Todo el lote escribe el htpasswd UNA vez y purga la caché de credenciales
    UNA vez (un reinicio de Squid), en vez de uno por usuario.
    """
    nombres = list(dict.fromkeys(u.strip() for u in data.usernames if u.strip()))
    locales = {u.username: u for u in db.query(ProxyUser).filter(ProxyUser.username.in_(nombres)).all()}
    ldap = {u.username: u for u in db.query(LdapUser).filter(LdapUser.username.in_(nombres)).all()}

    ok: list[str] = []
    omitidos: list[dict] = []
    credenciales: list[dict] = []
    revocar = False
    hubo_ldap = False
    hubo_local = False
    quitados_de_grupos = 0

    if data.action == "reset_password":
        realm = realm_actual(db)
        pendientes = [(n, _contrasena_aleatoria()) for n in nombres if n in locales]
        hashes = _hashes_en_paralelo(pendientes, realm) if pendientes else {}
        for n, clave in pendientes:
            u = locales[n]
            u.password_hash, u.htpasswd_hash, u.digest_ha1 = hashes[n]
            u.digest_ha1_realm = realm
            credenciales.append({"usuario": n, "password": clave})
            ok.append(n)
            hubo_local = True
            revocar = True
            db.add(AuditLog(admin_id=current_admin.id, admin_username=current_admin.username,
                            action="reset_password", entity="proxy_user", entity_id=u.id, new_value=n))

    for n in nombres:
        if data.action == "reset_password":
            if n in locales:
                continue
            omitidos.append({"usuario": n, "motivo": "Solo se puede generar credenciales de usuarios locales." if n in ldap else "No existe."})
            continue

        u_local, u_ldap = locales.get(n), ldap.get(n)
        if u_local is None and u_ldap is None:
            omitidos.append({"usuario": n, "motivo": "No existe."})
            continue

        if data.action in ("enable", "disable"):
            nuevo = data.action == "enable"
            for u, entidad in ((u_local, "proxy_user"), (u_ldap, "ldap_user")):
                if u is None or u.enabled == nuevo:
                    continue
                u.enabled = nuevo
                db.add(AuditLog(admin_id=current_admin.id, admin_username=current_admin.username,
                                action="toggle", entity=entidad, entity_id=u.id, new_value=str(nuevo)))
                if entidad == "proxy_user":
                    hubo_local = True
                else:
                    hubo_ldap = True
                if not nuevo:
                    revocar = True
            ok.append(n)

        elif data.action == "delete":
            if u_local is None:
                omitidos.append({"usuario": n, "motivo": "Un usuario LDAP se gestiona en el directorio: aquí solo se puede deshabilitar."})
                continue
            db.add(AuditLog(admin_id=current_admin.id, admin_username=current_admin.username,
                            action="delete", entity="proxy_user", entity_id=u_local.id, old_value=n))
            quitados_de_grupos += db.query(UserGroupMember).filter(UserGroupMember.username == n).delete()
            db.delete(u_local)
            ok.append(n)
            hubo_local = True
            revocar = True

    if hubo_local:
        _sync_passwd(db)
    db.commit()
    if hubo_ldap:
        from app.routes.ldap import _sync_ldap_files
        _sync_ldap_files(db)
    if quitados_de_grupos:
        mark_dirty()
    if revocar:
        _revocar(background_tasks)

    # Una operación sobre varios usuarios marcados se avisa UNA vez, con la lista.
    if ok:
        _avisar_masivo(background_tasks, db, current_admin.username, data.action, ok)

    return {"status": "ok", "action": data.action, "ok": ok, "omitidos": omitidos, "credenciales": credenciales}


@router.get("/export")
def export_users(
    format: Literal["csv", "xlsx"] = Query("csv"),
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Lista de usuarios (locales y LDAP) en CSV o Excel. Sin contraseñas:
    no se guardan en claro. El mismo archivo sirve de base para volver a
    importar los locales en otro SquidManager (recibirán contraseña nueva)."""
    from app.services import user_import_service as svc

    filas = []
    for u in db.query(ProxyUser).order_by(ProxyUser.username).all():
        filas.append([u.username, u.display_name or "", u.email or "", "local",
                      "si" if u.enabled else "no", u.expires_at.strftime("%Y-%m-%d") if u.expires_at else ""])
    for u in db.query(LdapUser).order_by(LdapUser.username).all():
        filas.append([u.username, u.display_name or "", u.email or "", "ldap",
                      "si" if u.enabled else "no", ""])
    datos = svc.exportar(format, filas)
    tipo = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if format == "xlsx" else "text/csv; charset=utf-8"
    stamp = utcnow().strftime("%Y%m%d-%H%M%S")
    return Response(datos, media_type=tipo,
                    headers={"Content-Disposition": f"attachment; filename=usuarios-{stamp}.{format}"})


@router.get("/import-template")
def import_template(
    format: Literal["csv", "xlsx"] = Query("csv"),
    _: Admin = Depends(get_current_admin),
):
    """Plantilla con los encabezados y dos filas de ejemplo."""
    from app.services import user_import_service as svc

    tipo = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if format == "xlsx" else "text/csv; charset=utf-8"
    return Response(svc.plantilla(format), media_type=tipo,
                    headers={"Content-Disposition": f"attachment; filename=plantilla-usuarios.{format}"})


@router.post("/import")
def import_users(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    modo: Literal["crear", "crear_o_actualizar"] = Form("crear"),
    simular: bool = Form(True),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
):
    """Carga masiva de usuarios locales desde CSV / Excel / TXT.

    `simular=true` (por defecto) solo valida y devuelve el informe de lo que
    haría, sin tocar nada: el admin lo revisa y recién ahí confirma con
    `simular=false`. Las filas con errores se reportan y se omiten, el resto
    se importa. A los usuarios nuevos sin contraseña en el archivo se les
    genera una, y se devuelve UNA sola vez en `credenciales`.
    """
    from app.services import user_import_service as svc

    datos = file.file.read(svc.MAX_BYTES + 1)
    try:
        filas, errores = svc.parse_archivo(file.filename or "", datos)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
    except Exception as e:  # archivo corrupto (xlsx roto, etc.)
        raise HTTPException(400, detail=f"No se pudo leer el archivo: {e}")

    existentes = {u.username.lower(): u for u in db.query(ProxyUser).all()}
    ldap_nombres = {u.username.lower() for u in db.query(LdapUser).all()}

    a_crear, a_actualizar, omitidos = [], [], []
    for f in filas:
        clave = f["username"].lower()
        if clave in ldap_nombres and clave not in existentes:
            errores.append({"fila": f["fila"], "usuario": f["username"], "motivo": "Ya existe un usuario LDAP con ese nombre."})
        elif clave in existentes:
            if modo == "crear_o_actualizar":
                a_actualizar.append((existentes[clave], f))
            else:
                omitidos.append({"fila": f["fila"], "usuario": f["username"], "motivo": "Ya existe (usa «crear o actualizar» para modificarlo)."})
        else:
            a_crear.append(f)

    informe = {
        "simulacion": simular, "modo": modo, "total_filas": len(filas) + len(errores),
        "a_crear": len(a_crear), "a_actualizar": len(a_actualizar),
        "omitidos": omitidos, "errores": errores, "credenciales": [],
        "creados": 0, "actualizados": 0,
    }
    if simular or (not a_crear and not a_actualizar):
        return informe

    realm = realm_actual(db)
    con_clave: list[tuple[str, str]] = []
    generadas: dict[str, str] = {}
    for f in a_crear:
        if not f["password"]:
            f["password"] = _contrasena_aleatoria()
            generadas[f["username"]] = f["password"]
        con_clave.append((f["username"], f["password"]))
    for _, f in a_actualizar:
        if f["password"]:
            con_clave.append((f["username"], f["password"]))
    hashes = _hashes_en_paralelo(con_clave, realm) if con_clave else {}

    revocar = False
    for f in a_crear:
        ph, hl, ha1 = hashes[f["username"]]
        u = ProxyUser(
            username=f["username"], display_name=f["display_name"], email=f["email"],
            password_hash=ph, htpasswd_hash=hl, digest_ha1=ha1, digest_ha1_realm=realm,
            enabled=True if f["enabled"] is None else f["enabled"],
            expires_at=f["expires_at"],
        )
        db.add(u)
    for u, f in a_actualizar:
        if f["display_name"] is not None:
            u.display_name = f["display_name"]
        if f["email"] is not None:
            u.email = f["email"]
        if f["enabled"] is not None:
            if u.enabled and not f["enabled"]:
                revocar = True
            u.enabled = f["enabled"]
        if f["expires_at"] is not None:
            u.expires_at = f["expires_at"]
        if f["password"]:
            u.password_hash, u.htpasswd_hash, u.digest_ha1 = hashes[f["username"]]
            u.digest_ha1_realm = realm
            revocar = True
    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="import", entity="proxy_user", entity_id=None,
        new_value=f"{len(a_crear)} creados, {len(a_actualizar)} actualizados ({file.filename})",
    ))
    _sync_passwd(db)
    db.commit()
    if revocar:
        _revocar(background_tasks)

    queue_notification(background_tasks, db, "user_change",
                       "Importación masiva de usuarios",
                       f"El administrador «{current_admin.username}» importó usuarios desde un archivo: {len(a_crear)} nuevos y {len(a_actualizar)} actualizados.")
    informe.update({
        "creados": len(a_crear), "actualizados": len(a_actualizar),
        "credenciales": [{"usuario": u, "password": p} for u, p in generadas.items()],
    })
    return informe
