"""Servicio de logs: lectura filtrada del access.log de Squid."""

import re
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

ACCESS_LOG_PATH = "/var/log/squid/access.log"

LINE_PATTERN = re.compile(
    r'^(\d+\.\d+)\s+'           # timestamp
    r'(\d+)\s+'                  # elapsed (ms)
    r'(\S+)\s+'                  # client IP
    r'(\S+)/(\d+)\s+'           # action/status
    r'(\d+)\s+'                  # bytes
    r'(\S+)\s+'                  # method
    r'(\S+)\s+'                  # url
    r'(\S+)\s+'                  # user
    r'(\S+)\s+'                  # hierarchy
    r'(\S+)'                     # content type
)


def parse_line(line: str) -> dict | None:
    """Parsea una línea del access.log de Squid con todos los campos."""
    m = LINE_PATTERN.match(line.strip())
    if not m:
        return None

    url = m.group(8)
    domain = ""
    if url.startswith("http://") or url.startswith("https://"):
        try:
            domain = url.split("/")[2]
        except IndexError:
            domain = url
    elif ":443" in url or ":80" in url:
        domain = url.split(":")[0] if ":" in url else url
    else:
        domain = url

    if domain.startswith("www."):
        domain = domain[4:]

    return {
        "timestamp": float(m.group(1)),
        "time": datetime.fromtimestamp(float(m.group(1))).strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_ms": int(m.group(2)),
        "client_ip": m.group(3),
        "action": m.group(4),
        "status": int(m.group(5)),
        "bytes": int(m.group(6)),
        "method": m.group(7),
        "url": url,
        "domain": domain,
        "user": m.group(9) if m.group(9) != "-" else "-",
        "hierarchy": m.group(10),
        "content_type": m.group(11),
        "denied": int(m.group(5)) in (403, 401) or "DENIED" in m.group(4),
    }


def read_all_entries() -> list[dict]:
    """Lee todas las líneas válidas del access.log."""
    log_path = Path(ACCESS_LOG_PATH)
    if not log_path.exists():
        return []
    entries = []
    try:
        with open(log_path, "r") as f:
            for line in f:
                entry = parse_line(line)
                if entry:
                    entries.append(entry)
    except Exception as e:
        logger.error(f"Error leyendo access.log: {e}")
    return entries


def filter_entries(
    entries: list[dict],
    user: str | None = None,
    status: int | None = None,
    domain: str | None = None,
    ip: str | None = None,
    denied_only: bool = False,
) -> list[dict]:
    """Aplica filtros a la lista de entradas."""
    result = entries

    if denied_only:
        result = [e for e in result if e["denied"]]
    if user:
        result = [e for e in result if e["user"] == user]
    if status is not None:
        result = [e for e in result if e["status"] == status]
    if domain:
        result = [e for e in result if domain.lower() in e["domain"].lower()]
    if ip:
        result = [e for e in result if e["client_ip"] == ip]

    return result


def get_logs(
    limit: int = 100,
    offset: int = 0,
    user: str | None = None,
    status: int | None = None,
    domain: str | None = None,
    ip: str | None = None,
    denied_only: bool = False,
) -> dict:
    """Obtiene logs filtrados con paginación (los más recientes primero)."""
    entries = read_all_entries()
    # Ordenar del más reciente al más antiguo
    entries = list(reversed(entries))

    filtered = filter_entries(entries, user=user, status=status, domain=domain, ip=ip, denied_only=denied_only)

    total = len(filtered)
    page = filtered[offset:offset + limit]

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "entries": page,
    }


def get_log_stats() -> dict:
    """Estadísticas del access.log para los filtros rápidos."""
    entries = read_all_entries()

    users = sorted(set(e["user"] for e in entries if e["user"] != "-"))
    domains = sorted(set(e["domain"] for e in entries if e["domain"] and e["domain"] != "error:transaction-end-before-headers"))
    statuses = sorted(set(e["status"] for e in entries))

    return {
        "total_entries": len(entries),
        "users": users,
        "statuses": statuses,
        "top_domains": list(set(d for d in domains))[:50],
    }
