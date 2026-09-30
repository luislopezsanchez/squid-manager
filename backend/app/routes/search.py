"""Buscador global de referencias: dónde aparece un valor (un usuario, un
dominio, un nombre de ACL, una IP...) a lo largo de ACLs, reglas de
acceso, grupos y ancho de banda.

Antes, encontrar dónde estaba usado un valor puntual significaba abrir
cada página y leer manualmente -impráctico apenas la lista de ACLs o
reglas crece. squid_names.find_references() ya resolvía esto para UNA
ACL/grupo puntual (al querer borrarla o renombrarla); acá se generaliza a
cualquier término de búsqueda, sobre todas las entidades a la vez.

No busca DENTRO del contenido de una ACL 'file' (puede tener millones de
líneas -ver Acl.source en el modelo-): ahí solo se busca por nombre,
descripción o metadatos, igual que las demás páginas ya hacen. Buscar un
dominio puntual dentro de esas listas queda para una mejora futura, si
hace falta (grep contra el .txt correspondiente).
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session, defer

from app.database import get_db
from app.models.admin import Admin
from app.models.acl import Acl
from app.models.access_rule import AccessRule
from app.models.user_group import UserGroup, UserGroupMember
from app.models.delay_pool import DelayPool
from app.services.auth_service import get_current_admin

router = APIRouter()


def _regla_coincide(acl_names: str, description: str | None, termino: str) -> bool:
    """¿Esta regla es un resultado para `termino`? Sustring simple sobre
    acl_names (no exige palabra completa: buscar "face" sí debería
    encontrar una regla que usa la ACL "block_facebook") y sobre la
    descripción. Separada en una función pura -sin tocar la BD- para poder
    testear la lógica de match sin simular una sesión de SQLAlchemy."""
    return termino in acl_names.lower() or termino in (description or "").lower()


@router.get("/references")
def buscar_referencias(
    q: str = Query(..., min_length=1, max_length=200),
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Busca `q` (sin distinguir mayúsculas) en nombres, valores,
    descripciones y miembros de ACLs, reglas, grupos y delay pools.
    """
    termino = q.strip().lower()
    if not termino:
        return {"acls": [], "rules": [], "groups": [], "delay_pools": []}
    patron = f"%{termino}%"

    acls = (
        db.query(Acl)
        .options(defer(Acl.value))
        .filter(
            or_(
                Acl.name.ilike(patron),
                Acl.value.ilike(patron),
                Acl.description.ilike(patron),
                Acl.display_name.ilike(patron),
            )
        )
        .order_by(Acl.name)
        .limit(50)
        .all()
    )

    # acl_names es una lista separada por espacios en un solo campo de
    # texto: se filtra en Python (ver _regla_coincide) en vez de con un
    # ILIKE de SQL, porque el volumen de reglas es chico por naturaleza
    # (a diferencia de una ACL de archivo, que sí puede tener millones de
    # líneas) y así la lógica de match queda testeable sin simular SQL.
    todas_las_reglas = db.query(AccessRule).order_by(AccessRule.order, AccessRule.id).all()
    rules = [r for r in todas_las_reglas if _regla_coincide(r.acl_names, r.description, termino)][:50]

    grupos_todos = db.query(UserGroup).all()
    miembros_por_grupo: dict[int, list[str]] = {}
    for m in db.query(UserGroupMember).order_by(UserGroupMember.username).all():
        miembros_por_grupo.setdefault(m.group_id, []).append(m.username)

    groups = [
        {
            "id": g.id, "name": g.name, "description": g.description,
            "source": g.source, "matched_member": next(
                (m for m in miembros_por_grupo.get(g.id, []) if termino in m.lower()), None,
            ),
        }
        for g in grupos_todos
        if termino in g.name.lower()
        or termino in (g.description or "").lower()
        or any(termino in m.lower() for m in miembros_por_grupo.get(g.id, []))
        or termino in (g.ldap_group_name or "").lower()
    ][:50]

    pools = (
        db.query(DelayPool)
        .filter(
            or_(
                DelayPool.description.ilike(patron),
                DelayPool.acl_name.ilike(patron),
                DelayPool.acl_names.ilike(patron),
            )
        )
        .limit(50)
        .all()
    )

    return {
        "acls": [
            {"id": a.id, "name": a.name, "type": a.type, "description": a.description,
             "is_category": a.is_category, "source": a.source}
            for a in acls
        ],
        "rules": [
            {"id": r.id, "action": r.action, "acl_names": r.acl_names, "order": r.order,
             "description": r.description, "enabled": r.enabled}
            for r in rules
        ],
        "groups": groups,
        "delay_pools": [
            {"id": p.id, "description": p.description, "acl_name": p.acl_name, "pool_class": p.pool_class}
            for p in pools
        ],
    }
