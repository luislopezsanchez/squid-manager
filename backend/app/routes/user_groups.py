"""Rutas de gestión de grupos de usuarios (políticas por grupo).

Los grupos se mapean a ACLs `proxy_auth` en el squid.conf:
  acl <grupo> proxy_auth user1 user2 ...

Luego se pueden usar en las reglas de acceso (http_access) referenciando
el nombre del grupo como si fuera una ACL.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.admin import Admin
from app.models.audit_log import AuditLog
from app.models.user_group import UserGroup, UserGroupMember
from app.services.auth_service import get_current_admin, require_writer
from app.services.config_state import mark_dirty
from app.services.squid_service import apply_squid_config, purge_credentials
from app.services.squid_names import validate_name, ensure_not_referenced

router = APIRouter()


class GroupCreate(BaseModel):
    name: str
    description: str | None = None


class GroupUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class MemberAdd(BaseModel):
    username: str


class GroupResponse(BaseModel):
    id: int
    name: str
    description: str | None
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
        members=members,
    )


def _apply_after_member_change(db: Session) -> dict:
    """Aplica la config de Squid tras añadir/quitar un miembro de grupo.

    Los cambios de miembros se aplican de inmediato para que la política surta
    efecto sin pulsar «Aplicar Cambios». Si la configuración resultante no es
    válida, se marca «pendiente» y se informa del error en lugar de dejarlo
    pasar en silencio.
    """
    result = apply_squid_config(db, force_reconfigure=True)
    if result["status"] == "error":
        mark_dirty()
    return result


@router.get("/", response_model=list[GroupResponse])
async def list_groups(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Lista todos los grupos con sus miembros."""
    return [
        _to_response(g, _members(db, g.id))
        for g in db.query(UserGroup).order_by(UserGroup.name).all()
    ]


@router.post("/", response_model=GroupResponse, status_code=201)
async def create_group(
    data: GroupCreate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(require_writer),
):
    """Crea un nuevo grupo de usuarios."""
    name = validate_name(data.name, "grupo")

    if db.query(UserGroup).filter(UserGroup.name == name).first():
        raise HTTPException(400, detail="El grupo ya existe")

    group = UserGroup(name=name, description=data.description)
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
async def update_group(
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

    db.add(AuditLog(
        admin_id=current_admin.id, admin_username=current_admin.username,
        action="update", entity="user_group", entity_id=group.id,
        old_value=old_name, new_value=group.name,
    ))
    db.commit()
    mark_dirty()

    return _to_response(group, _members(db, group_id))


@router.delete("/{group_id}", status_code=204)
async def delete_group(
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
    _apply_after_member_change(db)

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
    _apply_after_member_change(db)
    # Salir de un grupo puede quitar permisos: sin purgar, las credenciales ya
    # validadas siguen sirviendo con la política anterior.
    purge_credentials()

    return _to_response(group, _members(db, group_id))
