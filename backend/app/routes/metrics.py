"""Rutas de métricas del proxy en tiempo real."""

from fastapi import APIRouter, Depends, Query
from app.models.admin import Admin
from app.services.auth_service import get_current_admin
from app.services.metrics_service import (
    get_traffic_stats, get_top_users, get_top_domains,
    get_system_metrics, get_traffic_timeline, get_recent_connections,
)

router = APIRouter()


@router.get("/traffic")
async def traffic(
    seconds: int = Query(60, ge=10, le=3600),
    _: Admin = Depends(get_current_admin),
):
    """Estadísticas de tráfico de los últimos N segundos."""
    return get_traffic_stats(seconds)


@router.get("/top-users")
async def top_users(
    limit: int = Query(10, ge=1, le=50),
    _: Admin = Depends(get_current_admin),
):
    """Top usuarios por bytes transferidos."""
    return get_top_users(limit)


@router.get("/top-domains")
async def top_domains(
    limit: int = Query(10, ge=1, le=50),
    denied: bool = Query(False, description="Solo dominios bloqueados"),
    _: Admin = Depends(get_current_admin),
):
    """Top dominios visitados o bloqueados."""
    return get_top_domains(limit, denied_only=denied)


@router.get("/system")
async def system(
    _: Admin = Depends(get_current_admin),
):
    """Métricas del sistema (CPU, RAM, disco)."""
    return get_system_metrics()


@router.get("/timeline")
async def timeline(
    seconds: int = Query(60, ge=10, le=300),
    interval: int = Query(5, ge=1, le=30),
    _: Admin = Depends(get_current_admin),
):
    """Timeline de tráfico para gráficos."""
    return get_traffic_timeline(seconds, interval)


@router.get("/connections")
async def connections(
    limit: int = Query(20, ge=1, le=100),
    _: Admin = Depends(get_current_admin),
):
    """Últimas conexiones registradas."""
    return get_recent_connections(limit)


@router.get("/dashboard")
async def dashboard(
    _: Admin = Depends(get_current_admin),
):
    """Dashboard completo: todas las métricas en una sola llamada."""
    return {
        "traffic": get_traffic_stats(60),
        "top_users": get_top_users(10),
        "top_domains": get_top_domains(10, denied_only=False),
        "top_blocked": get_top_domains(10, denied_only=True),
        "system": get_system_metrics(),
        "timeline": get_traffic_timeline(60, 5),
        "connections": get_recent_connections(10),
    }