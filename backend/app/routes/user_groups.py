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
from app.models.user_group import UserGroup, UserGroupMember
from app.services.auth_service import get_current_admin
from app.services.config_state import mark_dirty
from app.services.squid_service import apply_squid_config

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


def _to_response(group: UserGroup, members: list[str]) -> GroupResponse:
    return GroupResponse(
        id=group.id,
        name=group.name,
        description=group.description,
        members=members,
    )


def _apply_after_member_change(db: Session) -> dict:
    """Aplica la config de Squid tras añadir/quitar un miembro de grupo.

    Los cambios de miembros de grupo se aplican de inmediato (igual que usuarios
    y LDAP), para que la política del grupo surta efecto sin pulsar
    "Aplicar Cambios" manualmente. Si la config resultara inválida, se marca
    "pendiente" como respaldo para reintentar manualmente.
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
    result = []
    for g in db.query(UserGroup).order_by(UserGroup.name).all():
        members = [
            m.username
            for m in db.query(UserGroupMember).filter(UserGroupMember.group_id == g.id).all()
        ]
        result.append(_to_response(g, members))
    return result


@router.post("/", response_model=GroupResponse, status_code=201)
async def create_group(
    data: GroupCreate,
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Crea un nuevo grupo de usuarios."""
    existing = db.query(UserGroup).filter(UserGroup.name == data.name).first()
    if existing:
        raise HTTPException(400, detail="El grupo ya existe")

    group = UserGroup(name=data.name, description=data.description)
    db.add(group)
    db.commit()
    mark_dirty()
    db.refresh(group)
    return _to_response(group, [])


@router.put("/{group_id}", response_model=GroupResponse)
async def update_group(
    group_id: int,
    data: GroupUpdate,
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Actualiza un grupo."""
    group = db.query(UserGroup).filter(UserGroup.id == group_id).first()
    if not group:
        raise HTTPException(404, detail="Grupo no encontrado")

    if data.name is not None:
        group.name = data.name
    if data.description is not None:
        group.description = data.description
    db.commit()
    mark_dirty()

    members = [
        m.username
        for m in db.query(UserGroupMember).filter(UserGroupMember.group_id == group_id).all()
    ]
    return _to_response(group, members)


@router.delete("/{group_id}", status_code=204)
async def delete_group(
    group_id: int,
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Elimina un grupo y sus miembros."""
    group = db.query(UserGroup).filter(UserGroup.id == group_id).first()
    if not group:
        raise HTTPException(404, detail="Grupo no encontrado")

    db.query(UserGroupMember).filter(UserGroupMember.group_id == group_id).delete()
    db.delete(group)
    db.commit()
    mark_dirty()


@router.post("/{group_id}/members", response_model=GroupResponse)
async def add_member(
    group_id: int,
    data: MemberAdd,
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Añade un usuario (local o LDAP) al grupo."""
    group = db.query(UserGroup).filter(UserGroup.id == group_id).first()
    if not group:
        raise HTTPException(404, detail="Grupo no encontrado")

    existing = (
        db.query(UserGroupMember)
        .filter(UserGroupMember.group_id == group_id, UserGroupMember.username == data.username)
        .first()
    )
    if existing:
        raise HTTPException(400, detail="El usuario ya está en el grupo")

    db.add(UserGroupMember(group_id=group_id, username=data.username))
    db.commit()
    _apply_after_member_change(db)

    members = [
        m.username
        for m in db.query(UserGroupMember).filter(UserGroupMember.group_id == group_id).all()
    ]
    return _to_response(group, members)


@router.delete("/{group_id}/members/{username}", response_model=GroupResponse)
async def remove_member(
    group_id: int,
    username: str,
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Elimina un usuario del grupo."""
    group = db.query(UserGroup).filter(UserGroup.id == group_id).first()
    if not group:
        raise HTTPException(404, detail="Grupo no encontrado")

    db.query(UserGroupMember).filter(
        UserGroupMember.group_id == group_id, UserGroupMember.username == username
    ).delete()
    db.commit()
    _apply_after_member_change(db)

    members = [
        m.username
        for m in db.query(UserGroupMember).filter(UserGroupMember.group_id == group_id).all()
    ]
    return _to_response(group, members)
