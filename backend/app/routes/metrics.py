"""Rutas de métricas del proxy en tiempo real."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.admin import Admin
from app.services.auth_service import get_current_admin
from app.services.metrics_service import (
    get_realtime_traffic, get_top_users, get_top_domains,
    get_system_metrics, get_traffic_timeline, get_recent_connections,
    get_dashboard, get_top_blocked_users,
)

router = APIRouter()


@router.get("/traffic")
async def traffic(_: Admin = Depends(get_current_admin)):
    """Tráfico REAL en tiempo real desde Docker network stats."""
    return get_realtime_traffic()


@router.get("/top-users")
async def top_users(
    limit: int = Query(10, ge=1, le=50),
    _: Admin = Depends(get_current_admin),
):
    """Top usuarios por bytes transferidos (desde access.log)."""
    return get_top_users(limit)


@router.get("/top-domains")
async def top_domains(
    limit: int = Query(10, ge=1, le=50),
    denied: bool = Query(False),
    _: Admin = Depends(get_current_admin),
):
    """Top dominios visitados o bloqueados (desde access.log)."""
    return get_top_domains(limit, denied_only=denied)


@router.get("/top-blocked-users")
async def top_blocked_users(
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Usuarios con más peticiones denegadas (desde access.log), cruzado
    contra si la cuenta está realmente deshabilitada o no."""
    return get_top_blocked_users(limit, db=db)


@router.get("/system")
async def system(_: Admin = Depends(get_current_admin)):
    """Métricas del sistema (CPU, RAM, disco) desde Docker stats."""
    return get_system_metrics()


@router.get("/timeline")
async def timeline(_: Admin = Depends(get_current_admin)):
    """Timeline de tráfico REAL desde buffer de Docker network stats."""
    return get_traffic_timeline()


@router.get("/connections")
async def connections(
    limit: int = Query(20, ge=1, le=100),
    _: Admin = Depends(get_current_admin),
):
    """Últimas conexiones registradas (desde access.log)."""
    return get_recent_connections(limit)


@router.get("/dashboard")
async def dashboard_all(db: Session = Depends(get_db), _: Admin = Depends(get_current_admin)):
    """Dashboard completo: todas las métricas en una sola llamada."""
    return get_dashboard(db=db)