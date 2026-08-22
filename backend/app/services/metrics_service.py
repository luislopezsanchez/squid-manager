"""Servicio de métricas: parsea access.log de Squid y extrae estadísticas."""

import re
import time
import logging
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime

logger = logging.getLogger(__name__)

ACCESS_LOG_PATH = "/var/log/squid/access.log"

# Formato de access.log de Squid:
# timestamp elapsed client_ip action/status bytes method url user hierarchy content_type
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


def parse_log_line(line: str) -> dict | None:
    """Parsea una línea del access.log de Squid."""
    m = LINE_PATTERN.match(line.strip())
    if not m:
        return None

    timestamp = float(m.group(1))
    elapsed = int(m.group(2))
    client_ip = m.group(3)
    action = m.group(4)
    status = int(m.group(5))
    bytes_transferred = int(m.group(6))
    method = m.group(7)
    url = m.group(8)
    user = m.group(9)
    hierarchy = m.group(10)
    content_type = m.group(11)

    # Extraer dominio de la URL
    domain = ""
    if url.startswith("http://") or url.startswith("https://"):
        try:
            domain = url.split("/")[2]
        except IndexError:
            domain = url
    elif ":443" in url or ":80" in url:
        # CONNECT url:port
        domain = url.split(":")[0] if ":" in url else url
    else:
        domain = url

    # Limpiar dominio (quitar www. opcional)
    if domain.startswith("www."):
        domain = domain[4:]

    return {
        "timestamp": timestamp,
        "elapsed": elapsed,
        "client_ip": client_ip,
        "action": action,
        "status": status,
        "bytes": bytes_transferred,
        "method": method,
        "url": url,
        "domain": domain,
        "user": user if user != "-" else None,
        "hierarchy": hierarchy,
        "content_type": content_type,
        "denied": status in (403, 401) or "DENIED" in action,
    }


def read_recent_logs(seconds: int = 60) -> list[dict]:
    """Lee las líneas del access.log de los últimos N segundos."""
    log_path = Path(ACCESS_LOG_PATH)
    if not log_path.exists():
        logger.warning(f"Access log no encontrado: {ACCESS_LOG_PATH}")
        return []

    now = time.time()
    cutoff = now - seconds
    entries = []

    try:
        with open(log_path, "r") as f:
            for line in f:
                entry = parse_log_line(line)
                if entry and entry["timestamp"] >= cutoff:
                    entries.append(entry)
    except Exception as e:
        logger.error(f"Error leyendo access.log: {e}")

    return entries


def read_last_n_lines(n: int = 500) -> list[dict]:
    """Lee las últimas N líneas del access.log."""
    log_path = Path(ACCESS_LOG_PATH)
    if not log_path.exists():
        return []

    entries = []
    try:
        with open(log_path, "r") as f:
            lines = f.readlines()[-n:]
        for line in lines:
            entry = parse_log_line(line)
            if entry:
                entries.append(entry)
    except Exception as e:
        logger.error(f"Error leyendo access.log: {e}")

    return entries


def get_traffic_stats(seconds: int = 60) -> dict:
    """Estadísticas de tráfico de los últimos N segundos."""
    entries = read_recent_logs(seconds)

    total_bytes = sum(e["bytes"] for e in entries)
    total_requests = len(entries)
    denied_requests = sum(1 for e in entries if e["denied"])
    allowed_requests = total_requests - denied_requests

    # Bytes por segundo (promedio)
    bytes_per_second = total_bytes / seconds if seconds > 0 else 0

    # Conexiones activas (IPs únicas)
    active_ips = set(e["client_ip"] for e in entries)
    active_users = set(e["user"] for e in entries if e["user"])

    return {
        "period_seconds": seconds,
        "total_requests": total_requests,
        "allowed_requests": allowed_requests,
        "denied_requests": denied_requests,
        "total_bytes": total_bytes,
        "bytes_per_second": round(bytes_per_second),
        "active_connections": len(active_ips),
        "active_users": len(active_users),
        "active_ips": list(active_ips)[:20],
    }


def get_top_users(limit: int = 10) -> list[dict]:
    """Top usuarios por bytes transferidos."""
    entries = read_last_n_lines(1000)
    user_bytes = defaultdict(int)
    user_requests = defaultdict(int)

    for e in entries:
        if e["user"]:
            user_bytes[e["user"]] += e["bytes"]
            user_requests[e["user"]] += 1

    top = sorted(user_bytes.items(), key=lambda x: x[1], reverse=True)[:limit]
    return [
        {"user": u, "bytes": b, "requests": user_requests[u]}
        for u, b in top
    ]


def get_top_domains(limit: int = 10, denied_only: bool = False) -> list[dict]:
    """Top dominios visitados o bloqueados."""
    entries = read_last_n_lines(1000)

    if denied_only:
        entries = [e for e in entries if e["denied"]]

    domain_count = Counter(e["domain"] for e in entries if e["domain"])
    domain_bytes = defaultdict(int)
    for e in entries:
        if e["domain"]:
            domain_bytes[e["domain"]] += e["bytes"]

    top = domain_count.most_common(limit)
    return [
        {"domain": d, "requests": c, "bytes": domain_bytes[d]}
        for d, c in top
    ]


def get_system_metrics() -> dict:
    """Métricas del sistema (CPU, RAM, disco)."""
    metrics = {"cpu": {}, "memory": {}, "disk": {}}

    try:
        # CPU load
        with open("/proc/loadavg", "r") as f:
            parts = f.read().split()
            metrics["cpu"]["load_1"] = float(parts[0])
            metrics["cpu"]["load_5"] = float(parts[1])
            metrics["cpu"]["load_15"] = float(parts[2])
    except Exception:
        pass

    try:
        # Memory
        with open("/proc/meminfo", "r") as f:
            meminfo = {}
            for line in f:
                parts = line.split(":")
                if len(parts) == 2:
                    key = parts[0].strip()
                    val = int(parts[1].strip().split()[0]) * 1024  # bytes
                    meminfo[key] = val
            total = meminfo.get("MemTotal", 0)
            available = meminfo.get("MemAvailable", 0)
            used = total - available
            metrics["memory"]["total"] = total
            metrics["memory"]["used"] = used
            metrics["memory"]["available"] = available
            metrics["memory"]["percent"] = round((used / total * 100), 1) if total > 0 else 0
    except Exception:
        pass

    try:
        # Disk (spool de Squid)
        import shutil
        usage = shutil.disk_usage("/var/spool/squid")
        metrics["disk"]["total"] = usage.total
        metrics["disk"]["used"] = usage.used
        metrics["disk"]["free"] = usage.free
        metrics["disk"]["percent"] = round((usage.used / usage.total * 100), 1) if usage.total > 0 else 0
    except Exception:
        pass

    return metrics


def get_traffic_timeline(seconds: int = 60, interval: int = 5) -> list[dict]:
    """Timeline de tráfico dividido en intervalos."""
    entries = read_recent_logs(seconds)
    now = time.time()

    # Crear buckets
    buckets = []
    num_buckets = seconds // interval
    for i in range(num_buckets):
        bucket_start = now - seconds + (i * interval)
        bucket_end = bucket_start + interval
        bucket_entries = [e for e in entries if bucket_start <= e["timestamp"] < bucket_end]
        buckets.append({
            "time": datetime.fromtimestamp(bucket_start).strftime("%H:%M:%S"),
            "bytes": sum(e["bytes"] for e in bucket_entries),
            "requests": len(bucket_entries),
            "denied": sum(1 for e in bucket_entries if e["denied"]),
        })

    return buckets


def get_recent_connections(limit: int = 20) -> list[dict]:
    """Últimas conexiones registradas."""
    entries = read_last_n_lines(limit * 3)  # Leer más por si hay líneas inválidas
    recent = entries[-limit:]
    return [
        {
            "time": datetime.fromtimestamp(e["timestamp"]).strftime("%H:%M:%S"),
            "ip": e["client_ip"],
            "user": e["user"] or "-",
            "method": e["method"],
            "domain": e["domain"],
            "status": e["status"],
            "bytes": e["bytes"],
            "denied": e["denied"],
        }
        for e in reversed(recent)
    ]