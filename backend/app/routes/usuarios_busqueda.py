"""Búsqueda ligera de usuarios (locales + LDAP) para los selectores del panel.

Los selectores de Grupos, Cuotas y Delay pools sólo necesitan unos nombres para autocompletar; descargar los miles de usuarios completos
para eso era lento con directorios grandes (auditoría 09-002). Aquí se busca en el servidor y se devuelven pocos resultados.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.admin import Admin
from app.models.ldap_user import LdapUser
from app.models.proxy_user import ProxyUser
from app.services.auth_service import get_current_admin

router = APIRouter()


def _patron(q: str) -> str:
    """Contiene `q`, sin que % ni _ escritos por el usuario actúen como comodines."""
    q = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{q}%"


@router.get("/buscar")
def buscar_usuarios(
    q: str = Query("", max_length=100),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Nombres de usuario (locales y LDAP) que contienen `q`, ordenados, hasta `limit`. Con `q` vacío, los primeros."""
    q = q.strip()
    filas: list[dict] = []
    for modelo, origen in ((ProxyUser, "local"), (LdapUser, "ldap")):
        consulta = db.query(modelo.username)
        if q:
            consulta = consulta.filter(modelo.username.ilike(_patron(q), escape="\\"))
        filas += [{"username": n, "origen": origen} for (n,) in consulta.order_by(modelo.username).limit(limit).all()]
    # Un mismo nombre puede existir en las dos listas: se ofrece una sola vez.
    vistos, unicos = set(), []
    for f in sorted(filas, key=lambda f: f["username"].lower()):
        if f["username"] not in vistos:
            vistos.add(f["username"])
            unicos.append(f)
    return {"usuarios": unicos[:limit], "hay_mas": len(unicos) > limit}


@router.get("/resumen")
def resumen_usuarios(db: Session = Depends(get_db), _: Admin = Depends(get_current_admin)):
    """Cuántos usuarios hay, sin descargarlos."""
    return {
        "local": db.query(func.count(ProxyUser.id)).scalar() or 0,
        "ldap": db.query(func.count(LdapUser.id)).scalar() or 0,
        "ldap_ausentes": db.query(func.count(LdapUser.id)).filter(LdapUser.en_directorio == False).scalar() or 0,  # noqa: E712
    }
