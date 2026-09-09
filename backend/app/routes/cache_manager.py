"""Ruta de estadísticas de caché: lo que expone el Cache Manager de Squid.

Solo lectura -no hay nada que escribir aquí-, así que cualquier admin
autenticado puede verla, igual que el dashboard.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.admin import Admin
from app.services.auth_service import get_current_admin
from app.services.cache_manager_service import obtener_estadisticas_cache

router = APIRouter()


@router.get("/stats")
async def cache_stats(
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Estadísticas de caché de Squid (mgr:info + mgr:storedir), parseadas."""
    return obtener_estadisticas_cache(db)
