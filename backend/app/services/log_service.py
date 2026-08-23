"""Servicio de logs: lectura filtrada del access.log de Squid.

El access.log de un proxy en uso llega a cientos de MB. Aquí nunca se carga
entero: se lee desde el final en bloques y se para en cuanto hay suficientes
líneas para responder. La versión anterior lo leía completo en cada petición,
y el dashboard consulta cada pocos segundos.
"""

import io
import re
import logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

ACCESS_LOG_PATH = "/var/log/squid/access.log"

# Tope de líneas que se examinan en una petición. Con filtros activos evita
# recorrer un fichero de 500 MB buscando algo que quizá no está.
MAX_SCAN_LINES = 50_000
_CHUNK = 256 * 1024

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


def iter_lines_reverse(path: str, max_lines: int = MAX_SCAN_LINES):
    """Genera las líneas del fichero de la más reciente a la más antigua.

    Lee bloques desde el final, sin cargar el fichero completo en memoria.
    """
    p = Path(path)
    if not p.exists():
        return

    try:
        with open(p, "rb") as f:
            f.seek(0, io.SEEK_END)
            position = f.tell()
            remainder = b""
            produced = 0

            while position > 0 and produced < max_lines:
                read_size = min(_CHUNK, position)
                position -= read_size
                f.seek(position)
                block = f.read(read_size) + remainder
                lines = block.split(b"\n")
                # El primer trozo puede ser una línea partida: se guarda para
                # unirlo con el bloque siguiente.
                remainder = lines.pop(0)

                for raw in reversed(lines):
                    if not raw.strip():
                        continue
                    yield raw.decode("utf-8", errors="replace")
                    produced += 1
                    if produced >= max_lines:
                        return

            if remainder.strip() and produced < max_lines:
                yield remainder.decode("utf-8", errors="replace")
    except Exception as e:
        logger.error(f"Error leyendo access.log: {e}")


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

    status = int(m.group(5))
    action = m.group(4)

    return {
        "timestamp": float(m.group(1)),
        "time": datetime.fromtimestamp(float(m.group(1))).strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_ms": int(m.group(2)),
        "client_ip": m.group(3),
        "action": action,
        "status": status,
        "bytes": int(m.group(6)),
        "method": m.group(7),
        "url": url,
        "domain": domain,
        "user": m.group(9) if m.group(9) != "-" else "-",
        "hierarchy": m.group(10),
        "content_type": m.group(11),
        # 407 es «hacen falta credenciales», que también es acceso denegado.
        "denied": status in (401, 403, 407) or "DENIED" in action,
    }


def _matches(entry: dict, user, status, domain, ip, denied_only) -> bool:
    if denied_only and not entry["denied"]:
        return False
    if user and entry["user"] != user:
        return False
    if status is not None and entry["status"] != status:
        return False
    if domain and domain.lower() not in entry["domain"].lower():
        return False
    if ip and entry["client_ip"] != ip:
        return False
    return True


def filter_entries(
    entries: list[dict],
    user: str | None = None,
    status: int | None = None,
    domain: str | None = None,
    ip: str | None = None,
    denied_only: bool = False,
) -> list[dict]:
    """Aplica los filtros a una lista de entradas ya parseadas."""
    return [e for e in entries if _matches(e, user, status, domain, ip, denied_only)]


def get_logs(
    limit: int = 100,
    offset: int = 0,
    user: str | None = None,
    status: int | None = None,
    domain: str | None = None,
    ip: str | None = None,
    denied_only: bool = False,
    max_scan: int = MAX_SCAN_LINES,
) -> dict:
    """Obtiene logs filtrados con paginación (los más recientes primero)."""
    page = []
    matched = 0
    scanned = 0

    for line in iter_lines_reverse(ACCESS_LOG_PATH, max_scan):
        scanned += 1
        entry = parse_line(line)
        if not entry or not _matches(entry, user, status, domain, ip, denied_only):
            continue
        matched += 1
        if matched > offset and len(page) < limit:
            page.append(entry)

    return {
        # `total` es el número de coincidencias dentro de lo examinado, no de
        # todo el histórico: el fichero no se recorre entero a propósito.
        "total": matched,
        "limit": limit,
        "offset": offset,
        "scanned_lines": scanned,
        "truncated": scanned >= max_scan,
        "entries": page,
    }


def get_log_stats(max_scan: int = MAX_SCAN_LINES) -> dict:
    """Estadísticas del access.log para los filtros rápidos."""
    users = set()
    domains = set()
    statuses = set()
    total = 0

    for line in iter_lines_reverse(ACCESS_LOG_PATH, max_scan):
        entry = parse_line(line)
        if not entry:
            continue
        total += 1
        if entry["user"] != "-":
            users.add(entry["user"])
        if entry["domain"] and entry["domain"] != "error:transaction-end-before-headers":
            domains.add(entry["domain"])
        statuses.add(entry["status"])

    return {
        "total_entries": total,
        "truncated": total >= max_scan,
        "users": sorted(users),
        "statuses": sorted(statuses),
        "top_domains": sorted(domains)[:50],
    }


def get_recent_entries(seconds: int, max_scan: int = MAX_SCAN_LINES) -> list[dict]:
    """Entradas de los últimos `seconds` segundos, de más nueva a más antigua.

    Corta en cuanto encuentra una línea anterior al corte: como el fichero se
    recorre hacia atrás, todo lo que queda por detrás es aún más antiguo.
    """
    import time

    cutoff = time.time() - seconds
    entries = []
    for line in iter_lines_reverse(ACCESS_LOG_PATH, max_scan):
        entry = parse_line(line)
        if not entry:
            continue
        if entry["timestamp"] < cutoff:
            break
        entries.append(entry)
    return entries
