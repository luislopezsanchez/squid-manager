"""Rutas de métricas del proxy en tiempo real.

Todas las funciones de este archivo son `def`, no `async def`, a propósito:
cada una hace trabajo bloqueante de verdad -leer y parsear el access.log
(hasta 400.000 líneas en una ventana de 7 días), o una llamada HTTP síncrona
al Cache Manager de Squid (`cache_manager_service`, hasta 10s de timeout)-
y ninguna hace `await` de nada. Uvicorn corre un solo worker (ver
squidmanager.service) con un único event loop: si estas funciones fueran
`async def`, ese trabajo bloqueante se ejecutaría directamente sobre ese
event loop y congelaría el backend ENTERO -para todos los usuarios, en
cualquier pantalla- mientras dura. Con `def` a secas, Starlette las manda
solas a su threadpool y el event loop queda libre para atender todo lo demás
mientras tanto. El dashboard es el caso que más lo sufre: dispara 5 de estas
llamadas en paralelo cada 5 segundos con auto-actualizar activado, así que
cualquier lentitud puntual (Cache Manager lento, ventana de 7 días grande) se
notaba en todo el panel, no solo en la tarjeta que la pidió.
"""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.admin import Admin
from app.services.auth_service import get_current_admin
from app.services.metrics_service import (
    get_realtime_traffic, get_top_users, get_top_domains,
    get_system_metrics, get_traffic_timeline, get_recent_connections,
    get_dashboard, get_top_blocked_users, get_latencia, get_http_errors,
    get_detalle, VENTANAS_SEGUNDOS, get_totales_actividad, get_tendencia_trafico,
    get_volumen_por_periodo, get_ips_compartidas,
)
from app.services.pdf_report_service import generar_pdf_actividad
from app.utils import utcnow

# Traduce la ventana elegida en el filtro global ("1h"/"24h"/"7d") a segundos.
# Cualquier otro valor (incluido None/ausente) preserva el comportamiento
# historico: ultimas 1000 peticiones, sin filtrar por fecha.
def _ventana_a_segundos(ventana: str | None) -> int | None:
    return VENTANAS_SEGUNDOS.get(ventana) if ventana else None

router = APIRouter()


@router.get("/traffic")
def traffic(_: Admin = Depends(get_current_admin)):
    """Tráfico REAL en tiempo real desde Docker network stats."""
    return get_realtime_traffic()


@router.get("/top-users")
def top_users(
    limit: int = Query(10, ge=1, le=50),
    ventana: str | None = Query(None, description="1h, 24h, 7d — vacío = últimas 1000 peticiones"),
    sort_by: str = Query("bytes", pattern="^(bytes|requests)$"),
    _: Admin = Depends(get_current_admin),
):
    """Top usuarios por bytes transferidos o por cantidad de peticiones (desde access.log)."""
    return get_top_users(limit, seconds=_ventana_a_segundos(ventana), sort_by=sort_by)


@router.get("/top-domains")
def top_domains(
    limit: int = Query(10, ge=1, le=50),
    denied: bool = Query(False),
    ventana: str | None = Query(None, description="1h, 24h, 7d — vacío = últimas 1000 peticiones"),
    sort_by: str = Query("requests", pattern="^(bytes|requests)$"),
    _: Admin = Depends(get_current_admin),
):
    """Top dominios visitados o bloqueados (desde access.log)."""
    return get_top_domains(limit, denied_only=denied, seconds=_ventana_a_segundos(ventana), sort_by=sort_by)


@router.get("/top-blocked-users")
def top_blocked_users(
    limit: int = Query(10, ge=1, le=50),
    ventana: str | None = Query(None, description="1h, 24h, 7d — vacío = últimas 1000 peticiones"),
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Usuarios con más peticiones denegadas (desde access.log), cruzado
    contra si la cuenta está realmente deshabilitada o no."""
    return get_top_blocked_users(limit, db=db, seconds=_ventana_a_segundos(ventana))


@router.get("/ips-compartidas")
def ips_compartidas(
    limit: int = Query(10, ge=1, le=50),
    ventana: str | None = Query(None, description="1h, 24h, 7d — vacío = últimas 1000 peticiones"),
    _: Admin = Depends(get_current_admin),
):
    """IPs con más de un usuario autenticado distinto (desde access.log)."""
    return get_ips_compartidas(limit, seconds=_ventana_a_segundos(ventana))


@router.get("/totales-actividad")
def totales_actividad(
    ventana: str | None = Query(None, description="1h, 24h, 7d — vacío = últimas 1000 peticiones"),
    _: Admin = Depends(get_current_admin),
):
    """Totales reales (todos los usuarios/dominios, no solo el top N) para
    el % de concentración y el "Total" de Actividad de red."""
    return get_totales_actividad(seconds=_ventana_a_segundos(ventana))


@router.get("/actividad/export-pdf")
def actividad_export_pdf(
    ventana: str | None = Query(None, description="1h, 24h, 7d — vacío = últimas 1000 peticiones"),
    db: Session = Depends(get_db),
    _: Admin = Depends(get_current_admin),
):
    """Informe ejecutivo en PDF de Actividad de red -mismos datos que ya se
    ven en el panel (top usuarios/dominios/bloqueados + totales reales),
    para adjuntar o imprimir sin depender de una captura de pantalla."""
    pdf_bytes = generar_pdf_actividad(ventana, db=db)
    stamp = utcnow().strftime("%Y%m%d-%H%M%S")
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=actividad-red-{stamp}.pdf"},
    )


@router.get("/detalle")
def detalle(
    user: str | None = Query(None),
    domain: str | None = Query(None),
    ventana: str | None = Query(None, description="1h, 24h, 7d — vacío = últimas 1000 peticiones"),
    limit: int = Query(50, ge=1, le=200),
    _: Admin = Depends(get_current_admin),
):
    """Detalle de peticiones de un usuario o dominio puntual (drill-down
    desde un ranking de Actividad de red)."""
    if not user and not domain:
        return []
    return get_detalle(user=user, domain=domain, seconds=_ventana_a_segundos(ventana), limit=limit)


@router.get("/tendencia-trafico")
def tendencia_trafico(
    user: str | None = Query(None),
    domain: str | None = Query(None),
    ventana: str | None = Query(None, description="1h, 24h, 7d — vacío = últimas 1000 peticiones"),
    buckets: int = Query(20, ge=2, le=100),
    _: Admin = Depends(get_current_admin),
):
    """Evolución en el tiempo (bytes/peticiones) de un usuario o dominio
    puntual, para el gráfico de Tendencias."""
    if not user and not domain:
        return {"points": [], "user": None, "domain": None}
    return get_tendencia_trafico(user=user, domain=domain, seconds=_ventana_a_segundos(ventana), buckets=buckets)


@router.get("/volumen-por-periodo")
def volumen_por_periodo(
    ventana: str | None = Query(None, description="1h, 24h, 7d, 30d — vacío = últimas 1000 peticiones"),
    _: Admin = Depends(get_current_admin),
):
    """Volumen de tráfico en baldes que se adaptan a la ventana elegida
    (minutos/horas/días), para Panorama."""
    return get_volumen_por_periodo(seconds=_ventana_a_segundos(ventana))


@router.get("/latencia")
def latencia(
    limit: int = Query(10, ge=1, le=50),
    ventana: str | None = Query(None, description="1h, 24h, 7d — vacío = últimas 1000 peticiones"),
    _: Admin = Depends(get_current_admin),
):
    """Latencia general (media/p50/p95) y dominios más lentos (desde access.log)."""
    return get_latencia(limit, seconds=_ventana_a_segundos(ventana))


@router.get("/errores-http")
def errores_http(
    limit: int = Query(10, ge=1, le=50),
    ventana: str | None = Query(None, description="1h, 24h, 7d — vacío = últimas 1000 peticiones"),
    _: Admin = Depends(get_current_admin),
):
    """Códigos de error HTTP más frecuentes y qué dominios los generan (desde access.log)."""
    return get_http_errors(limit, seconds=_ventana_a_segundos(ventana))


@router.get("/system")
def system(_: Admin = Depends(get_current_admin)):
    """Métricas del sistema (CPU, RAM, disco) desde Docker stats."""
    return get_system_metrics()


@router.get("/timeline")
def timeline(_: Admin = Depends(get_current_admin)):
    """Timeline de tráfico REAL desde buffer de Docker network stats."""
    return get_traffic_timeline()


@router.get("/connections")
def connections(
    limit: int = Query(20, ge=1, le=100),
    _: Admin = Depends(get_current_admin),
):
    """Últimas conexiones registradas (desde access.log)."""
    return get_recent_connections(limit)


@router.get("/dashboard")
def dashboard_all(db: Session = Depends(get_db), _: Admin = Depends(get_current_admin)):
    """Dashboard completo: todas las métricas en una sola llamada."""
    return get_dashboard(db=db)