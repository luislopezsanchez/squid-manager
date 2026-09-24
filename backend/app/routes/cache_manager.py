"""Ruta de estadísticas de caché: lo que expone el Cache Manager de Squid.

Solo lectura -no hay nada que escribir aquí-, así que cualquier admin
autenticado puede verla, igual que el dashboard.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.admin import Admin
from app.services.auth_service import get_current_admin
from app.services.cache_manager_service import obtener_estadisticas_cache, obtener_conexiones_activas

router = APIRouter()


@router.get("/stats")
def cache_stats(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Estadísticas de caché de Squid (mgr:info + mgr:storedir), parseadas."""
    return obtener_estadisticas_cache(db)


@router.get("/active-connections")
def active_connections(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Conexiones YA abiertas ahora mismo, por cliente (mgr:client_list).

    A diferencia del resto de las métricas (que salen de access.log, y solo
    existen una vez que una petición termina), esto sale de la memoria viva
    de Squid: cuenta lo que sigue en curso en este instante.
    """
    return obtener_conexiones_activas(db)
