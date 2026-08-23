"""Rutas de logs de Squid: listado, filtros y exportación CSV."""

import csv
import io
from app.utils import utcnow
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.admin import Admin
from app.services.auth_service import get_current_admin
from app.services.log_service import get_logs, get_log_stats, get_recent_entries

router = APIRouter()


@router.get("/access")
async def access_logs(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user: str | None = Query(None),
    status: int | None = Query(None),
    domain: str | None = Query(None),
    ip: str | None = Query(None),
    denied: bool = Query(False),
    _: Admin = Depends(get_current_admin),
):
    """Listar logs de acceso con filtros y paginación."""
    return get_logs(
        limit=limit, offset=offset, user=user,
        status=status, domain=domain, ip=ip, denied_only=denied,
    )


@router.get("/stats")
async def log_stats(_: Admin = Depends(get_current_admin)):
    """Estadísticas para los filtros del logs viewer."""
    return get_log_stats()


@router.get("/security-alerts")
async def security_alerts(
    minutes: int = Query(10, ge=1, le=60),
    threshold: int = Query(5, ge=1, le=100),
    _: Admin = Depends(get_current_admin),
):
    """Detectar intentos de autenticación fallidos repetidos por IP.

    Escanea los logs recientes en busca de IPs con >= `threshold` respuestas 407
    (Proxy Authentication Required, es decir, credenciales inválidas o ausentes)
    en los últimos `minutes` minutos.
    """
    from collections import Counter

    # Solo se recorre la ventana pedida, no el histórico completo.
    entries = get_recent_entries(minutes * 60)

    auth_failures = Counter()
    for e in entries:
        if e["status"] == 407:
            auth_failures[e["client_ip"]] += 1

    # Filtrar IPs que superan el umbral
    suspicious = [
        {"ip": ip, "failed_attempts": count}
        for ip, count in auth_failures.items()
        if count >= threshold
    ]
    suspicious.sort(key=lambda x: x["failed_attempts"], reverse=True)

    return {
        "window_minutes": minutes,
        "threshold": threshold,
        "alerts": suspicious,
        "total_suspicious_ips": len(suspicious),
    }


@router.get("/export")
async def export_logs(
    user: str | None = Query(None),
    status: int | None = Query(None),
    domain: str | None = Query(None),
    ip: str | None = Query(None),
    denied: bool = Query(False),
    _: Admin = Depends(get_current_admin),
):
    """Exportar logs filtrados a CSV."""
    result = get_logs(limit=50000, offset=0, user=user, status=status, domain=domain, ip=ip, denied_only=denied)
    entries = result["entries"]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["timestamp", "time", "client_ip", "action", "status", "bytes", "method", "url", "domain", "user", "content_type", "denied"])

    for e in entries:
        writer.writerow([
            e["timestamp"], e["time"], e["client_ip"], e["action"], e["status"],
            e["bytes"], e["method"], e["url"], e["domain"], e["user"],
            e["content_type"], "yes" if e["denied"] else "no",
        ])

    output.seek(0)
    filename = f"squid-logs-{utcnow().strftime('%Y%m%d-%H%M%S')}.csv"

    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
