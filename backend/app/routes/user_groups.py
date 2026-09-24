"""Rutas de gestión de grupos de usuarios (políticas por grupo).

Dos orígenes posibles (`source`):
  - 'local' (el único que existía hasta ahora): miembros propios, se
    mapean a una ACL `proxy_auth` fija en el squid.conf:
      acl <grupo> proxy_auth user1 user2 ...
  - 'ldap': la pertenencia se consulta en vivo contra el directorio, sin
    sincronizar nada a la base propia, vía una ACL externa:
      acl <grupo> external ldap_group_helper <nombre_en_el_directorio> <direct|nested>
    Ver squid/ldap_group_helper.py y config_generator.py.

Los dos se usan igual desde afuera: en las reglas de acceso (http_access)
se referencia el nombre del grupo como si fuera una ACL cualquiera.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.database import get_db
from app.models.admin import Admin
from app.models.audit_log import AuditLog
from app.models.ldap_config import LdapConfig
from app.models.squid_settings import SquidSetting
from app.models.user_group import UserGroup, UserGroupMember
from app.services.auth_service import get_current_admin, require_writer
from app.services.config_state import mark_dirty
from app.services.squid_service import apply_squid_config, purge_credentials
from app.services.squid_names import validate_name, ensure_not_referenced

router = APIRouter()

FUENTES_VALIDAS = ("local", "ldap")


class GroupCreate(BaseModel):
    name: str
    description: str | None = None
    no_bump: bool = False
    source: str = "local"
    ldap_group_name: str | None = Field(None, max_length=255)
    ldap_group_nested: bool = False


class GroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    no_bump: bool | None = None
    source: str | None = None
    ldap_group_name: str | None = Field(None, max_length=255)
    ldap_group_nested: bool | None = None


class MemberAdd(BaseModel):
    username: str


class GroupResponse(BaseModel):
    id: int
    name: str
    description: str | None
    no_bump: bool = False
    source: str = "local"
    ldap_group_name: str | None = None
    ldap_group_nested: bool = False
    members: list[str] = []

    class Config:
        from_attributes = True


def _members(db: Session, group_id: int) -> list[str]:
    return [
        m.username
        for m in db.query(UserGroupMember)
        .filter(UserGroupMember.group_id == group_id)
        .order_by(UserGroupMember.username)
        .all()
    ]


def _to_response(group: UserGroup, members: list[str]) -> GroupResponse:
    return GroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        no_bump=bool(getattr(group, "no_bump", False)),
        source=getattr(group, "source", "local"),
        ldap_group_name=getattr(group, "ldap_group_name", None),
        ldap_group_nested=bool(getattr(group, "ldap_group_nested", False)),
        members=members,
    )


def _validar_origen_ldap(db: Session, source: str, ldap_group_name: str | None) -> None:
    if source not in FUENTES_VALIDAS:
        raise HTTPException(400, detail="El origen del grupo debe ser 'local' o 'ldap'.")
    if source != "ldap":
        return
    if not (ldap_group_name or "").strip():
        raise HTTPException(400, detail="Falta el nombre del grupo en el directorio LDAP.")
    config = db.query(LdapConfig).first()
    if not config or not config.enabled:
        raise HTTPException(
            400,
            detail=(
                "LDAP no está activado: activalo en LDAP / Active Directory "
                "antes de crear un grupo que dependa del directorio."
            ),
        )


async def _apply_after_member_change(db: Session) -> dict:
    """Aplica la config de Squid tras añadir/quitar un miembro de grupo.

    Los cambios de miembros se aplican de inmediato para que la política surta
    efecto sin pulsar «Aplicar Cambios». Si la configuración resultante no es
    válida, se marca «pendiente» y se informa del error en lugar de dejarlo
    pasar en silencio.

    Se delega al threadpool: apply_squid_config es sincrono y bloqueante, y
    llamarlo directo desde una ruta async congelaria el event loop -y con el,
    todo el panel- para todos los admins mientras dura el apply.
    """
    result = await run_in_threadpool(apply_squid_config, db)
    if result["status"] == "error":
        mark_dirty()
    return result


@router.get("/", response_model=list[GroupResponse])
def list_groups(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Lista todos los grupos con sus miembros.

    Una sola consulta de miembros, agrupada en memoria por group_id, en vez
    de una consulta por grupo -el numero de grupos es chico por naturaleza,
    pero el patron N+1 crece si alguien lo copia a una entidad con mas filas
    (auditoria 2026-09-09, hallazgo 09-002).
    """
    grupos = db.query(UserGroup).order_by(UserGroup.name).all()
    miembros_por_grupo: dict[int, list[str]] = {}
    for m in db.query(UserGroupMember).order_by(UserGroupMember.username).all():
        miembros_por_grupo.setdefault(m.group_id, []).append(m.username)
    return [
        _to_response(g, miembros_por_grupo.get(g.id, []))
        for g in grupos
    ]


@router.post("/", response_model=GroupResponse, status_code=201)
def create_group(
    data: GroupCreate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
):
    """Crea un nuevo grupo de usuarios."""
    name = validate_name(data.name, "grupo")

    # Los grupos son ACLs `proxy_auth`: sin ningún auth_param declarado (que
    # es justo lo que hace proxy_auth_scheme='none'), Squid aborta el
    # arranque en cuanto una regla nombre esa ACL.
    esquema = db.query(SquidSetting).filter(SquidSetting.key == "proxy_auth_scheme").first()
    if esquema and (esquema.value or "").strip().lower() == "none":
        raise HTTPException(
            400,
            detail=(
                "No se pueden crear grupos de usuarios con el esquema de "
                "autenticación del proxy en 'none': los grupos dependen de "
                "la autenticación local, que está desactivada. Cambia el "
                "esquema a 'basic' o 'digest' en Configuración antes de "
                "crear grupos."
            ),
        )

    if db.query(UserGroup).filter(UserGroup.name == name).first():
        raise HTTPException(400, detail="El grupo ya existe")

    _validar_origen_ldap(db, data.source, data.ldap_group_name)
    if data.source == "ldap" and data.no_bump:
        raise HTTPException(
            400,
            detail="La excepción de SSL Bump por grupo todavía no está disponible para grupos de LDAP.",
        )

    group = UserGroup(
        name=name, description=data.description, no_bump=data.no_bump,
        source=data.source, ldap_group_name=(data.ldap_group_name or "").strip() or None,
        ldap_group_nested=data.ldap_group_nested,
    )
    db.add(group)
    db.flush()
    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="create", entity="user_group", entity_id=group.id, new_value=name,
    ))
    db.commit()
    mark_dirty()
    db.refresh(group)
    return _to_response(group, [])


@router.put("/{group_id}", response_model=GroupResponse)
def update_group(
    group_id: int,
    data: GroupUpdate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
):
    """Actualiza un grupo."""
    group = db.query(UserGroup).filter(UserGroup.id == group_id).first()
    if not group:
        raise HTTPException(404, detail="Grupo no encontrado")

    old_name = group.name
    if data.name is not None and data.name != group.name:
        # Renombrar deja huérfanas las reglas que citan el nombre anterior.
        ensure_not_referenced(db, group.name, "renombrar")
        new_name = validate_name(data.name, "grupo")
        if db.query(UserGroup).filter(UserGroup.name == new_name, UserGroup.id != group_id).first():
            raise HTTPException(400, detail="Ya existe un grupo con ese nombre")
        group.name = new_name
    if data.description is not None:
        group.description = data.description
    if data.no_bump is not None:
        group.no_bump = data.no_bump
    if data.source is not None or data.ldap_group_name is not None or data.ldap_group_nested is not None:
        nuevo_source = data.source if data.source is not None else group.source
        nuevo_ldap_name = data.ldap_group_name if data.ldap_group_name is not None else group.ldap_group_name
        _validar_origen_ldap(db, nuevo_source, nuevo_ldap_name)
        if nuevo_source == "ldap" and group.no_bump:
            raise HTTPException(
                400,
                detail="La excepción de SSL Bump por grupo todavía no está disponible para grupos de LDAP.",
            )
        # Cambiar de 'ldap' a 'local' (o viceversa) empieza sin miembros:
        # un grupo local recién convertido de LDAP no tiene por qué heredar
        # una lista vacía como si fuera intencional, y uno LDAP no usa
        # UserGroupMember en absoluto (ver docstring del archivo).
        if group.source == "ldap" and nuevo_source == "local":
            db.query(UserGroupMember).filter(UserGroupMember.group_id == group.id).delete()
        group.source = nuevo_source
        group.ldap_group_name = (nuevo_ldap_name or "").strip() or None if nuevo_source == "ldap" else None
        if data.ldap_group_nested is not None:
            group.ldap_group_nested = data.ldap_group_nested

    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="update", entity="user_group", entity_id=group.id,
        old_value=old_name, new_value=group.name,
    ))
    db.commit()
    mark_dirty()

    return _to_response(group, _members(db, group_id))


@router.delete("/{group_id}", status_code=204)
def delete_group(
    group_id: int,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
):
    """Elimina un grupo y sus miembros."""
    group = db.query(UserGroup).filter(UserGroup.id == group_id).first()
    if not group:
        raise HTTPException(404, detail="Grupo no encontrado")

    ensure_not_referenced(db, group.name, "eliminar")

    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="delete", entity="user_group", entity_id=group.id, old_value=group.name,
    ))
    # Los miembros caen por la clave foránea en cascada; se borran aquí también
    # para que funcione igual en bases creadas antes de la migración.
    db.query(UserGroupMember).filter(UserGroupMember.group_id == group_id).delete()
    db.delete(group)
    db.commit()
    mark_dirty()


@router.post("/{group_id}/members", response_model=GroupResponse)
async def add_member(
    group_id: int,
    data: MemberAdd,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
):
    """Añade un usuario (local o LDAP) al grupo."""
    group = db.query(UserGroup).filter(UserGroup.id == group_id).first()
    if not group:
        raise HTTPException(404, detail="Grupo no encontrado")
    if group.source == "ldap":
        raise HTTPException(
            400,
            detail="Este grupo consulta la pertenencia en el directorio LDAP: no tiene miembros propios que agregar.",
        )

    username = (data.username or "").strip()
    if not username or any(c.isspace() for c in username):
        raise HTTPException(400, detail="Nombre de usuario inválido")

    existing = (
        db.query(UserGroupMember)
        .filter(UserGroupMember.group_id == group_id, UserGroupMember.username == username)
        .first()
    )
    if existing:
        raise HTTPException(400, detail="El usuario ya está en el grupo")

    db.add(UserGroupMember(group_id=group_id, username=username))
    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="add_member", entity="user_group", entity_id=group_id,
        new_value=f"{group.name}: +{username}",
    ))
    db.commit()
    await _apply_after_member_change(db)

    return _to_response(group, _members(db, group_id))


@router.delete("/{group_id}/members/{username}", response_model=GroupResponse)
async def remove_member(
    group_id: int,
    username: str,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
):
    """Elimina un usuario del grupo."""
    group = db.query(UserGroup).filter(UserGroup.id == group_id).first()
    if not group:
        raise HTTPException(404, detail="Grupo no encontrado")

    db.query(UserGroupMember).filter(
        UserGroupMember.group_id == group_id, UserGroupMember.username == username
    ).delete()
    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="remove_member", entity="user_group", entity_id=group_id,
        old_value=f"{group.name}: -{username}",
    ))
    db.commit()
    await _apply_after_member_change(db)
    # Salir de un grupo puede quitar permisos: sin purgar, las credenciales ya
    # validadas siguen sirviendo con la política anterior.
    purge_credentials()

    return _to_response(group, _members(db, group_id))
