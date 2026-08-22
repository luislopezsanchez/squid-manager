"""Servicio de métricas: combina Docker network stats + access.log parsing.

Estrategia híbrida:
- Docker network stats → tráfico REAL en bytes/s (instantáneo, no espera a que termine la transacción)
- access.log → metadata histórica (usuarios, dominios, conexiones con detalle)
- Buffer server-side → histórico de puntos para el gráfico
"""

import re
import time
import logging
import threading
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime

import docker as docker_sdk

logger = logging.getLogger(__name__)

ACCESS_LOG_PATH = "/var/log/squid/access.log"
SQUID_CONTAINER = "squidmgr-proxy"

# ============================================
# Buffer de network stats (server-side)
# ============================================
_network_buffer = []
_network_buffer_lock = threading.Lock()
_prev_network = {"timestamp": 0, "rx_bytes": 0, "tx_bytes": 0}
_MAX_BUFFER = 120  # 10 minutos a 5s por punto
_STATE_FILE = "/tmp/squidmgr_network_state.json"


def _load_prev_state() -> dict:
    """Carga el estado anterior desde archivo (sobrevive a reloads del backend)."""
    try:
        from pathlib import Path
        p = Path(_STATE_FILE)
        if p.exists():
            import json
            return json.loads(p.read_text())
    except Exception:
        pass
    return {"timestamp": 0, "rx_bytes": 0, "tx_bytes": 0}


def _save_prev_state(state: dict):
    """Guarda el estado en archivo."""
    try:
        from pathlib import Path
        import json
        Path(_STATE_FILE).write_text(json.dumps(state))
    except Exception:
        pass


def _get_network_stats_from_proc() -> dict:
    """Lee estadísticas de red del contenedor Squid via docker exec /proc/net/dev.

    Esto es más preciso que Docker stats API porque lee directamente del kernel
    del contenedor y se actualiza instantáneamente.
    """
    global _prev_network

    # Cargar estado previo desde archivo (sobrevive a reloads)
    if _prev_network["timestamp"] == 0:
        _prev_network = _load_prev_state()

    try:
        client = docker_sdk.from_env()
        container = client.containers.get(SQUID_CONTAINER)
        result = container.exec_run(["cat", "/proc/net/dev"])
        output = result.output.decode("utf-8", errors="replace")

        # Parsear /proc/net/dev
        rx_bytes = 0
        tx_bytes = 0
        for line in output.strip().split("\n"):
            if ":" in line and not line.strip().startswith("Inter") and not line.strip().startswith("face"):
                parts = line.split(":")
                iface = parts[0].strip()
                if iface == "eth0" or iface == "ens0":
                    stats = parts[1].split()
                    rx_bytes = int(stats[0])
                    tx_bytes = int(stats[8])
                    break

        # Si no encontramos eth0, sumar todas menos lo
        if rx_bytes == 0 and tx_bytes == 0:
            for line in output.strip().split("\n"):
                if ":" in line and not line.strip().startswith("Inter") and not line.strip().startswith("face"):
                    parts = line.split(":")
                    iface = parts[0].strip()
                    if iface != "lo":
                        stats = parts[1].split()
                        rx_bytes += int(stats[0])
                        tx_bytes += int(stats[8])

        now = time.time()
        prev = _prev_network

        if prev["timestamp"] > 0:
            delta_time = now - prev["timestamp"]
            rx_rate = max(0, (rx_bytes - prev["rx_bytes"]) / delta_time) if delta_time > 0 else 0
            tx_rate = max(0, (tx_bytes - prev["tx_bytes"]) / delta_time) if delta_time > 0 else 0
        else:
            rx_rate = 0
            tx_rate = 0

        _prev_network = {
            "timestamp": now,
            "rx_bytes": rx_bytes,
            "tx_bytes": tx_bytes,
        }
        _save_prev_state(_prev_network)

        return {
            "rx_bytes_per_second": round(rx_rate),
            "tx_bytes_per_second": round(tx_rate),
            "rx_total": rx_bytes,
            "tx_total": tx_bytes,
        }
    except Exception as e:
        logger.error(f"Error leyendo /proc/net/dev: {e}")
        return {"rx_bytes_per_second": 0, "tx_bytes_per_second": 0, "rx_total": 0, "tx_total": 0}


def _get_docker_network_stats() -> dict:
    """Estadísticas de red + CPU + RAM via Docker SDK + /proc/net/dev."""
    net = _get_network_stats_from_proc()

    # CPU y RAM desde Docker stats
    try:
        client = docker_sdk.from_env()
        container = client.containers.get(SQUID_CONTAINER)
        stats = container.stats(stream=False)

        cpu_stats = stats.get("cpu_stats", {})
        precpu_stats = stats.get("precpu_stats", {})
        cpu_delta = cpu_stats.get("cpu_usage", {}).get("total_usage", 0) - precpu_stats.get("cpu_usage", {}).get("total_usage", 0)
        system_delta = cpu_stats.get("system_cpu_usage", 0) - precpu_stats.get("system_cpu_usage", 0)
        num_cpus = cpu_stats.get("online_cpus", 1)
        cpu_percent = round((cpu_delta / system_delta * num_cpus * 100), 1) if system_delta > 0 else 0

        mem_stats = stats.get("memory_stats", {})
        mem_usage = mem_stats.get("usage", 0)
        mem_limit = mem_stats.get("limit", 0)
        mem_percent = round((mem_usage / mem_limit * 100), 1) if mem_limit > 0 else 0
    except Exception:
        cpu_percent = 0
        mem_usage = 0
        mem_limit = 0
        mem_percent = 0

    return {
        **net,
        "cpu_percent": cpu_percent,
        "mem_usage": mem_usage,
        "mem_limit": mem_limit,
        "mem_percent": mem_percent,
    }


def _update_network_buffer() -> dict:
    """Actualiza el buffer de network stats y devuelve el punto actual."""
    stats = _get_docker_network_stats()
    now = time.time()

    point = {
        "timestamp": now,
        "time": datetime.fromtimestamp(now).strftime("%H:%M:%S"),
        "rx_bytes_per_second": stats["rx_bytes_per_second"],
        "tx_bytes_per_second": stats["tx_bytes_per_second"],
        "rx_total": stats["rx_total"],
        "tx_total": stats["tx_total"],
    }

    with _network_buffer_lock:
        _network_buffer.append(point)
        if len(_network_buffer) > _MAX_BUFFER:
            _network_buffer.pop(0)
        # Devolver copia del buffer
        buffer_copy = list(_network_buffer)

    return {"current": stats, "buffer": buffer_copy}


# ============================================
# Parser de access.log (para metadata histórica)
# ============================================
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


def _parse_log_line(line: str) -> dict | None:
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
        "client_ip": m.group(3),
        "action": m.group(4),
        "status": int(m.group(5)),
        "bytes": int(m.group(6)),
        "method": m.group(7),
        "domain": domain,
        "user": m.group(9) if m.group(9) != "-" else None,
        "denied": int(m.group(5)) in (403, 401) or "DENIED" in m.group(4),
    }


def _read_last_n_lines(n: int = 1000) -> list[dict]:
    log_path = Path(ACCESS_LOG_PATH)
    if not log_path.exists():
        return []
    entries = []
    try:
        with open(log_path, "r") as f:
            lines = f.readlines()[-n:]
        for line in lines:
            entry = _parse_log_line(line)
            if entry:
                entries.append(entry)
    except Exception as e:
        logger.error(f"Error leyendo access.log: {e}")
    return entries


def _read_recent_logs(seconds: int = 60) -> list[dict]:
    log_path = Path(ACCESS_LOG_PATH)
    if not log_path.exists():
        return []
    now = time.time()
    cutoff = now - seconds
    entries = []
    try:
        with open(log_path, "r") as f:
            for line in f:
                entry = _parse_log_line(line)
                if entry and entry["timestamp"] >= cutoff:
                    entries.append(entry)
    except Exception as e:
        logger.error(f"Error leyendo access.log: {e}")
    return entries


# ============================================
# API pública
# ============================================

def get_realtime_traffic() -> dict:
    """Tráfico REAL en tiempo real desde Docker network stats."""
    net = _update_network_buffer()
    current = net["current"]

    # Calcular promedio de los últimos puntos del buffer
    buffer = net["buffer"]
    recent = buffer[-12:] if len(buffer) >= 12 else buffer  # últimos 60s
    avg_rx = sum(p["rx_bytes_per_second"] for p in recent) / len(recent) if recent else 0
    avg_tx = sum(p["tx_bytes_per_second"] for p in recent) / len(recent) if recent else 0

    # Combinar con access.log para conteo de peticiones
    log_entries = _read_recent_logs(60)

    return {
        "rx_bytes_per_second": current["rx_bytes_per_second"],
        "tx_bytes_per_second": current["tx_bytes_per_second"],
        "total_bytes_per_second": current["rx_bytes_per_second"] + current["tx_bytes_per_second"],
        "rx_avg_60s": round(avg_rx),
        "tx_avg_60s": round(avg_tx),
        "rx_total": current["rx_total"],
        "tx_total": current["tx_total"],
        # De access.log (metadata)
        "total_requests_60s": len(log_entries),
        "denied_requests_60s": sum(1 for e in log_entries if e["denied"]),
        "active_ips": list(set(e["client_ip"] for e in log_entries))[:20],
        "active_users": list(set(e["user"] for e in log_entries if e["user"])),
    }


def get_traffic_timeline() -> list[dict]:
    """Timeline del buffer de network stats para el gráfico (últimos 5 min)."""
    with _network_buffer_lock:
        buffer = list(_network_buffer)

    # Devolver últimos 5 minutos (60 puntos a 5s)
    return [
        {
            "time": p["time"],
            "rx_bytes": p["rx_bytes_per_second"],
            "tx_bytes": p["tx_bytes_per_second"],
            "total_bytes": p["rx_bytes_per_second"] + p["tx_bytes_per_second"],
        }
        for p in buffer[-60:]
    ]


def get_system_metrics() -> dict:
    """Métricas del sistema desde Docker stats + /proc."""
    net = _get_docker_network_stats()

    metrics = {
        "cpu": {"percent": net["cpu_percent"]},
        "memory": {
            "used": net["mem_usage"],
            "total": net["mem_limit"],
            "percent": net["mem_percent"],
        },
        "disk": {},
    }

    # Fallback a /proc si Docker stats no funcionó
    if net["mem_limit"] == 0:
        try:
            with open("/proc/meminfo", "r") as f:
                meminfo = {}
                for line in f:
                    parts = line.split(":")
                    if len(parts) == 2:
                        meminfo[parts[0].strip()] = int(parts[1].strip().split()[0]) * 1024
                total = meminfo.get("MemTotal", 0)
                available = meminfo.get("MemAvailable", 0)
                metrics["memory"] = {
                    "total": total,
                    "used": total - available,
                    "percent": round((total - available) / total * 100, 1) if total > 0 else 0,
                }
        except Exception:
            pass

    try:
        with open("/proc/loadavg", "r") as f:
            parts = f.read().split()
            metrics["cpu"]["load_1"] = float(parts[0])
            metrics["cpu"]["load_5"] = float(parts[1])
            metrics["cpu"]["load_15"] = float(parts[2])
    except Exception:
        pass

    try:
        import shutil
        usage = shutil.disk_usage("/var/spool/squid")
        metrics["disk"] = {
            "total": usage.total,
            "used": usage.used,
            "free": usage.free,
            "percent": round(usage.used / usage.total * 100, 1) if usage.total > 0 else 0,
        }
    except Exception:
        pass

    return metrics


def get_top_users(limit: int = 10) -> list[dict]:
    entries = _read_last_n_lines(1000)
    user_bytes = defaultdict(int)
    user_requests = defaultdict(int)
    for e in entries:
        if e["user"]:
            user_bytes[e["user"]] += e["bytes"]
            user_requests[e["user"]] += 1
    return [
        {"user": u, "bytes": b, "requests": user_requests[u]}
        for u, b in sorted(user_bytes.items(), key=lambda x: x[1], reverse=True)[:limit]
    ]


def get_top_domains(limit: int = 10, denied_only: bool = False) -> list[dict]:
    entries = _read_last_n_lines(1000)
    if denied_only:
        entries = [e for e in entries if e["denied"]]
    domain_count = Counter(e["domain"] for e in entries if e["domain"])
    domain_bytes = defaultdict(int)
    for e in entries:
        if e["domain"]:
            domain_bytes[e["domain"]] += e["bytes"]
    return [
        {"domain": d, "requests": c, "bytes": domain_bytes[d]}
        for d, c in domain_count.most_common(limit)
    ]


def get_recent_connections(limit: int = 20) -> list[dict]:
    entries = _read_last_n_lines(limit * 3)
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


def get_dashboard() -> dict:
    """Dashboard completo: todas las métricas en una sola llamada."""
    traffic = get_realtime_traffic()
    return {
        "traffic": traffic,
        "top_users": get_top_users(10),
        "top_domains": get_top_domains(10, denied_only=False),
        "top_blocked": get_top_domains(10, denied_only=True),
        "system": get_system_metrics(),
        "timeline": get_traffic_timeline(),
        "connections": get_recent_connections(10),
    }