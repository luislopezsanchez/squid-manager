"""Rutas de logs de Squid: listado, filtros y exportación."""

import csv
import io
import json
from typing import Literal
from app.utils import utcnow
from fastapi import APIRouter, Depends, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.admin import Admin
from app.services.auth_service import get_current_admin
from app.services.log_service import get_logs, get_log_stats, get_recent_entries
from app.services.historical_log_service import (
    list_months, get_month_index, get_historical_entries, iter_historical_lines,
)

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
    # get_logs escanea el access.log desde disco (hasta 50.000 líneas si el
    # filtro no encuentra nada antes): al threadpool, para no congelar el
    # panel para todos los admins durante ese escaneo (cacheado unos segundos
    # en log_service, pero el primer polling tras cambiar un filtro sí paga
    # el costo real).
    return await run_in_threadpool(
        get_logs,
        limit=limit, offset=offset, user=user,
        status=status, domain=domain, ip=ip, denied_only=denied,
    )


@router.get("/stats")
async def log_stats(_: Admin = Depends(get_current_admin)):
    """Estadísticas para los filtros del logs viewer."""
    return await run_in_threadpool(get_log_stats)


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
    entries = await run_in_threadpool(get_recent_entries, minutes * 60)

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
    format: Literal["csv", "ndjson", "raw"] = Query("csv"),
    user: str | None = Query(None),
    status: int | None = Query(None),
    domain: str | None = Query(None),
    ip: str | None = Query(None),
    denied: bool = Query(False),
    _: Admin = Depends(get_current_admin),
):
    """Exportar logs filtrados, en tres formatos pensados para audiencias distintas.

    - csv: para abrir en una hoja de cálculo o pegar en un informe.
    - ndjson: un objeto JSON por línea, el formato estándar para ingesta en
      herramientas externas (Splunk, ELK/Logstash, jq, cualquier SIEM) — cada
      línea se procesa de forma independiente, sin cargar el archivo entero.
    - raw: las líneas tal cual las escribió Squid, sin tocar. Sirve para
      herramientas ya hechas para el formato nativo de Squid (módulo Squid de
      Splunk/ELK, AWStats, SARG), que no saben interpretar CSV ni JSON.
    """
    result = await run_in_threadpool(
        get_logs, limit=50000, offset=0, user=user, status=status, domain=domain, ip=ip, denied_only=denied,
    )
    entries = result["entries"]
    stamp = utcnow().strftime("%Y%m%d-%H%M%S")

    if format == "raw":
        content = "\n".join(e["raw_line"] for e in entries) + ("\n" if entries else "")
        return StreamingResponse(
            iter([content]),
            media_type="text/plain",
            headers={"Content-Disposition": f"attachment; filename=squid-logs-{stamp}.log"},
        )

    if format == "ndjson":
        def _gen():
            for e in entries:
                # raw_line es un detalle interno del backend, no un dato del log.
                yield json.dumps({k: v for k, v in e.items() if k != "raw_line"}, ensure_ascii=False) + "\n"
        return StreamingResponse(
            _gen(),
            media_type="application/x-ndjson",
            headers={"Content-Disposition": f"attachment; filename=squid-logs-{stamp}.ndjson"},
        )

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

    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=squid-logs-{stamp}.csv"}
    )


# ============================================
# HISTÓRICO — meses ya consolidados en frío (archive/historical/AAAA/MM/).
# Separado a propósito del resto de este router: estos endpoints no forman
# parte de ningún polling del panel, se consultan solo cuando el admin abre
# la pestaña de histórico.
# ============================================

@router.get("/historical/months")
async def historical_months(_: Admin = Depends(get_current_admin)):
    """Lista los meses con log consolidado, con su resumen de index.json."""
    return await run_in_threadpool(list_months)


@router.get("/historical/{year}/{month}")
async def historical_month_summary(
    year: int, month: int,
    _: Admin = Depends(get_current_admin),
):
    """El index.json de un mes concreto."""
    indice = await run_in_threadpool(get_month_index, year, month)
    if indice is None:
        from fastapi import HTTPException
        raise HTTPException(404, detail=f"No hay log consolidado para {year}-{month:02d}")
    return indice


@router.get("/historical/{year}/{month}/entries")
async def historical_entries(
    year: int, month: int,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    user: str | None = Query(None),
    status: int | None = Query(None),
    domain: str | None = Query(None),
    ip: str | None = Query(None),
    denied: bool = Query(False),
    _: Admin = Depends(get_current_admin),
):
    """Líneas de un mes histórico, filtradas y paginadas.

    A diferencia de /access (que cachea unos segundos porque el panel hace
    polling), esto no cachea nada: un mes cerrado no cambia, y cada consulta
    ya es bajo demanda, no repetida cada 5s.
    """
    return await run_in_threadpool(
        get_historical_entries,
        year, month, limit=limit, offset=offset,
        user=user, status=status, domain=domain, ip=ip, denied_only=denied,
    )


@router.get("/historical/{year}/{month}/export")
async def historical_export(
    year: int, month: int,
    format: Literal["csv", "ndjson"] = Query("csv"),
    user: str | None = Query(None),
    status: int | None = Query(None),
    domain: str | None = Query(None),
    ip: str | None = Query(None),
    denied: bool = Query(False),
    _: Admin = Depends(get_current_admin),
):
    """Exporta un mes histórico completo (hasta el tope de líneas), en streaming.

    Sin 'raw' aquí a propósito: reconstruir la línea original de un archivo ya
    comprimido no aporta nada sobre re-leerla tal cual del .gz (ver /export
    de arriba, pensado para el access.log activo); para el histórico sirve
    directamente el .gz consolidado si alguien quiere el formato nativo.
    """
    filtros = {"user": user, "status": status, "domain": domain, "ip": ip, "denied_only": denied}
    stamp = f"{year}{month:02d}"

    if format == "ndjson":
        def _gen_ndjson():
            for e in iter_historical_lines(year, month, filtros):
                yield json.dumps({k: v for k, v in e.items() if k != "raw_line"}, ensure_ascii=False) + "\n"
        return StreamingResponse(
            _gen_ndjson(),
            media_type="application/x-ndjson",
            headers={"Content-Disposition": f"attachment; filename=squid-logs-{stamp}.ndjson"},
        )

    def _gen_csv():
        header = io.StringIO()
        writer = csv.writer(header)
        writer.writerow(["timestamp", "time", "client_ip", "action", "status", "bytes", "method", "url", "domain", "user", "content_type", "denied"])
        yield header.getvalue()
        for e in iter_historical_lines(year, month, filtros):
            row = io.StringIO()
            writer = csv.writer(row)
            writer.writerow([
                e["timestamp"], e["time"], e["client_ip"], e["action"], e["status"],
                e["bytes"], e["method"], e["url"], e["domain"], e["user"],
                e["content_type"], "yes" if e["denied"] else "no",
            ])
            yield row.getvalue()

    return StreamingResponse(
        _gen_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=squid-logs-{stamp}.csv"},
    )
