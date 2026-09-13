"""Servicio de métricas: combina contadores del sistema + access.log parsing.

Estrategia híbrida:
- Contadores de red → tráfico REAL en bytes/s (instantáneo, no espera a que termine la transacción)
- access.log → metadata histórica (usuarios, dominios, conexiones con detalle)
- Buffer server-side → histórico de puntos para el gráfico

De dónde salen esos contadores depende del despliegue y lo resuelve el runtime
(`app.services.runtime`): del cgroup del contenedor o del servicio de systemd.
Aquí solo se interpretan, y el formato del texto es el mismo en los dos casos.
"""

import re
import time
import logging
import threading
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime

from app.services.runtime import get_runtime

logger = logging.getLogger(__name__)

ACCESS_LOG_PATH = "/var/log/squid/access.log"

# ============================================
# Buffer de network stats (server-side)
# ============================================
_network_buffer = []
_network_buffer_lock = threading.Lock()
_prev_network = {"timestamp": 0, "rx_bytes": 0, "tx_bytes": 0}
_MAX_BUFFER = 120  # 10 minutos a 5s por punto
# Junto al resto del estado operativo del backend (mismo patron que
# update_service.py con .update_state.json), no en /tmp: en el despliegue
# nativo /tmp es compartido con el resto del sistema, y una ruta fija y
# adivinable ahi es el patron que un usuario local sin privilegios podria
# explotar -crear el archivo antes, o dejarlo como enlace simbolico a otro
# archivo escribible por squidmgr- para que el proceso lo sobrescriba.
# Impacto bajo (no son datos sensibles, los errores se tragan), pero el
# patron no conviene repetirlo (auditoria 2026-09-09, hallazgo 05-004).
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_STATE_FILE = str(_BACKEND_DIR / ".network_state.json")


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


# El cliente de Docker se reutiliza: antes se creaba uno nuevo con from_env()
# en cada peticion (y dos veces por peticion), abriendo una conexion al socket
# cada vez.
_docker_client = None
_docker_client_lock = threading.Lock()

# Las estadisticas del contenedor se cachean unos segundos. El dashboard las
# pide dos veces (trafico y sistema) y antes pagaba el coste entero en cada una.
_stats_cache = {"timestamp": 0.0, "data": None}
_stats_cache_lock = threading.Lock()
_STATS_TTL = 2.0

_EMPTY_STATS = {
    "rx_bytes_per_second": 0,
    "tx_bytes_per_second": 0,
    "rx_total": 0,
    "tx_total": 0,
    "cpu_percent": 0,
    "mem_usage": 0,
    "mem_limit": 0,
    "mem_percent": 0,
    "sampled_at": 0.0,
}


def _get_client():  # pragma: no cover - se conserva por compatibilidad
    """Obsoleto: el acceso a los contadores lo resuelve ahora el runtime."""
    raise RuntimeError(
        "metrics_service ya no habla con Docker directamente; usa get_runtime()"
    )




def _read_container_stats_raw() -> dict:
    """Lee red, memoria y CPU del contenedor Squid en un solo `docker exec`.

    Sustituye a container.stats(stream=False), que tardaba ~1s por llamada: el
    SDK espera dos muestreos del demonio para poder calcular el delta de CPU.
    Aqui se leen los ficheros de cgroup v2 directamente (~0,07s) y el delta se
    calcula con el mismo estado previo que ya se usaba para la red.
    """
    output = get_runtime().read_stats_raw()
    net_part, _, cg_part = output.partition("#CG#")

    # --- red (/proc/net/dev) ---
    ifaces = {}
    for line in net_part.strip().split("\n"):
        stripped = line.strip()
        if ":" not in line or stripped.startswith("Inter") or stripped.startswith("face"):
            continue
        name, _, rest = line.partition(":")
        cols = rest.split()
        if len(cols) >= 9:
            ifaces[name.strip()] = (int(cols[0]), int(cols[8]))

    # Se prefiere la interfaz principal; si no aparece, se suman todas menos lo.
    rx_bytes = tx_bytes = 0
    for preferred in ("eth0", "ens0"):
        if preferred in ifaces:
            rx_bytes, tx_bytes = ifaces[preferred]
            break
    else:
        for name, (rx, tx) in ifaces.items():
            if name != "lo":
                rx_bytes += rx
                tx_bytes += tx

    # --- memoria y CPU (cgroup v2) ---
    mem_usage = mem_limit = cpu_usec = host_mem = inactive_file = 0
    for line in cg_part.strip().split("\n"):
        parts = line.split()
        if len(parts) < 2:
            continue
        key, value = parts[0], parts[1]
        if key == "memcur" and value.isdigit():
            mem_usage = int(value)
        elif key == "memmax" and value.isdigit():
            # "max" significa sin limite; se queda en 0 y se usa la RAM del host.
            mem_limit = int(value)
        elif key == "usage_usec":
            cpu_usec = int(value)
        elif key == "inactive_file" and value.isdigit():
            inactive_file = int(value)
        elif key.startswith("MemTotal"):
            host_mem = int(value) * 1024

    return {
        "rx_bytes": rx_bytes,
        "tx_bytes": tx_bytes,
        # memory.current incluye cache de pagina; `docker stats` descuenta el
        # inactivo para reportar la memoria realmente en uso.
        "mem_usage": max(0, mem_usage - inactive_file),
        "mem_limit": mem_limit,
        "cpu_usec": cpu_usec,
        "host_mem": host_mem,
    }


def _compute_stats() -> dict:
    """Muestra las estadisticas actuales y calcula las tasas contra la anterior."""
    global _prev_network

    if _prev_network["timestamp"] == 0:
        _prev_network = _load_prev_state()

    try:
        raw = _read_container_stats_raw()
    except Exception as e:
        logger.error(f"Error leyendo estadisticas del contenedor Squid: {e}")
        return dict(_EMPTY_STATS)

    now = time.time()
    prev = _prev_network
    delta_time = now - prev["timestamp"] if prev["timestamp"] > 0 else 0

    if delta_time > 0:
        rx_rate = max(0, (raw["rx_bytes"] - prev["rx_bytes"]) / delta_time)
        tx_rate = max(0, (raw["tx_bytes"] - prev["tx_bytes"]) / delta_time)
        # usage_usec es tiempo de CPU acumulado: 100% = un nucleo completo.
        cpu_delta = max(0, raw["cpu_usec"] - prev.get("cpu_usec", 0))
        cpu_percent = round(cpu_delta / 1_000_000 / delta_time * 100, 1)
    else:
        rx_rate = tx_rate = 0
        cpu_percent = 0.0

    _prev_network = {
        "timestamp": now,
        "rx_bytes": raw["rx_bytes"],
        "tx_bytes": raw["tx_bytes"],
        "cpu_usec": raw["cpu_usec"],
    }
    _save_prev_state(_prev_network)

    mem_limit = raw["mem_limit"] or raw["host_mem"]
    mem_usage = raw["mem_usage"]

    return {
        "rx_bytes_per_second": round(rx_rate),
        "tx_bytes_per_second": round(tx_rate),
        "rx_total": raw["rx_bytes"],
        "tx_total": raw["tx_bytes"],
        "cpu_percent": cpu_percent,
        "mem_usage": mem_usage,
        "mem_limit": mem_limit,
        "mem_percent": round(mem_usage / mem_limit * 100, 1) if mem_limit > 0 else 0,
        "sampled_at": now,
    }


def _get_docker_network_stats() -> dict:
    """Estadisticas de red, CPU y RAM del contenedor Squid, cacheadas _STATS_TTL s."""
    with _stats_cache_lock:
        cached = _stats_cache["data"]
        if cached is not None and time.time() - _stats_cache["timestamp"] < _STATS_TTL:
            return cached

    stats = _compute_stats()

    with _stats_cache_lock:
        _stats_cache["timestamp"] = time.time()
        _stats_cache["data"] = stats
    return stats


def _update_network_buffer(extra: dict | None = None) -> dict:
    """Actualiza el buffer de metricas y devuelve el punto actual.

    `extra` trae los contadores derivados del access.log (peticiones,
    denegadas, IPs activas) para que el historico sirva tambien a las
    tarjetas de resumen, no solo al grafico de red.
    """
    stats = _get_docker_network_stats()
    extra = extra or {}
    now = stats.get("sampled_at") or time.time()

    point = {
        "timestamp": now,
        "time": datetime.fromtimestamp(now).strftime("%H:%M:%S"),
        "rx_bytes_per_second": stats["rx_bytes_per_second"],
        "tx_bytes_per_second": stats["tx_bytes_per_second"],
        "rx_total": stats["rx_total"],
        "tx_total": stats["tx_total"],
        "requests": extra.get("requests", 0),
        "denied": extra.get("denied", 0),
        "connections": extra.get("connections", 0),
        "cache_hit_ratio": extra.get("cache_hit_ratio"),
        "mem_percent": stats.get("mem_percent", 0),
        "cpu_percent": stats.get("cpu_percent", 0),
    }

    with _network_buffer_lock:
        # Con la cache, dos llamadas seguidas devuelven la misma muestra: no
        # tiene sentido duplicar el punto en el historico del grafico.
        last = _network_buffer[-1] if _network_buffer else None
        if last is None or point["timestamp"] != last["timestamp"]:
            _network_buffer.append(point)
            if len(_network_buffer) > _MAX_BUFFER:
                _network_buffer.pop(0)
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
        # Tiempo que tardo la peticion, en ms: ya venia en el log y se
        # descartaba, pero es el mejor indicador de salud del proxy.
        "elapsed_ms": int(m.group(2)),
        "client_ip": m.group(3),
        "action": m.group(4),
        "status": int(m.group(5)),
        "bytes": int(m.group(6)),
        "method": m.group(7),
        "domain": domain,
        "user": m.group(9) if m.group(9) != "-" else None,
        "denied": int(m.group(5)) in (401, 403, 407) or "DENIED" in m.group(4),
        # El propio SquidManager le pega a Squid para leer el Cache Manager
        # (ver cache_manager_service.py) -esa peticion queda igual en
        # access.log que cualquier otra, y sin marcarla aparte ensuciaba
        # "Sitios visitados"/"Top usuarios" con su propio trafico interno
        # (ej. "squidmanager-<hash>:3128" apareciendo como si fuera un sitio
        # que alguien visito). Se detecta por el path, no por client_ip: en
        # Docker el origen es otro contenedor, no localhost, asi que filtrar
        # por IP no lo hubiera atajado en ese modo.
        "interno": "squid-internal-mgr" in url,
    }


# Squid marca cada peticion con el resultado de cache. No todas cuentan:
# los tuneles HTTPS (TCP_TUNNEL) y las denegadas nunca llegan a consultarse,
# asi que se excluyen del ratio en lugar de contarlas como fallo.
_ACIERTOS = ("TCP_HIT", "TCP_MEM_HIT", "TCP_IMS_HIT", "TCP_INM_HIT", "TCP_REFRESH_UNMODIFIED")
_FALLOS = ("TCP_MISS", "TCP_REFRESH_MODIFIED", "TCP_CLIENT_REFRESH_MISS", "TCP_SWAPFAIL_MISS")


def _clasificar_cache(action: str) -> str | None:
    """Devuelve 'hit', 'miss' o None si la peticion no es cacheable."""
    base = action.split("_ABORTED")[0]
    if base in _ACIERTOS:
        return "hit"
    if base in _FALLOS:
        return "miss"
    return None


def _resumen_cache(entries: list[dict]) -> dict:
    """Aciertos, fallos y ratio sobre un conjunto de entradas del log."""
    hits = misses = 0
    bytes_hit = 0
    for e in entries:
        tipo = _clasificar_cache(e["action"])
        if tipo == "hit":
            hits += 1
            bytes_hit += e["bytes"]
        elif tipo == "miss":
            misses += 1
    total = hits + misses
    return {
        "cache_hits": hits,
        "cache_misses": misses,
        # None (y no 0) cuando no hubo nada cacheable: un 0% haria pensar que
        # la cache falla, cuando en realidad no se le pidio nada.
        "cache_hit_ratio": round(hits / total * 100, 1) if total else None,
        "cache_bytes_saved": bytes_hit,
    }


def _resumen_latencia(entries: list[dict]) -> dict:
    """Media, mediana y p95 del tiempo de respuesta, en ms.

    Los tuneles CONNECT (HTTPS) se excluyen: ahi `elapsed_ms` mide cuanto
    estuvo abierta la conexion completa, no cuanto tardo en responder, y
    puede ser de horas. Mezclarlo con el resto arruinaria el promedio.
    """
    valores = sorted(e["elapsed_ms"] for e in entries if e["method"] != "CONNECT")
    if not valores:
        return {"latency_avg_ms": None, "latency_p50_ms": None, "latency_p95_ms": None}

    def percentil(p: float) -> int:
        return valores[min(int(len(valores) * p), len(valores) - 1)]

    return {
        "latency_avg_ms": round(sum(valores) / len(valores)),
        "latency_p50_ms": percentil(0.50),
        "latency_p95_ms": percentil(0.95),
    }


def _read_last_n_lines(n: int = 1000) -> list[dict]:
    """Últimas n entradas del access.log, de la más antigua a la más reciente.

    Delega en el lector incremental de log_service: antes hacía
    readlines()[-n:], que carga el fichero entero en memoria.
    """
    from app.services.log_service import iter_lines_reverse

    entries = []
    for line in iter_lines_reverse(ACCESS_LOG_PATH, max_lines=n * 3):
        entry = _parse_log_line(line)
        # El propio trafico interno de SquidManager (Cache Manager, ver
        # "interno" en _parse_log_line) se descarta aca -las metricas y
        # rankings de este modulo son sobre trafico real, no sobre el panel
        # consultandose a si mismo. log_service.py (Registros) no filtra
        # esto: ahi si interesa ver todo lo que Squid proceso de verdad.
        if entry and not entry["interno"]:
            entries.append(entry)
        if len(entries) >= n:
            break
    entries.reverse()
    return entries


def _read_recent_logs(seconds: int = 60, max_lines: int = 50_000) -> list[dict]:
    """Entradas de los últimos `seconds` segundos.

    `max_lines` es el mismo tope de seguridad que ya usa log_service para
    cualquier lectura por ventana de tiempo: en un proxy con muchísimo
    tráfico, una ventana grande (7 días) podría en teoría necesitar escanear
    más lineas de las que conviene leer en una sola petición del panel -se
    sube el tope segun la ventana pedida (ver _read_window), no de forma
    ilimitada.
    """
    from app.services.log_service import iter_lines_reverse

    now = time.time()
    cutoff = now - seconds
    entries = []
    for line in iter_lines_reverse(ACCESS_LOG_PATH, max_lines=max_lines):
        entry = _parse_log_line(line)
        if not entry or entry["interno"]:  # ver nota en _read_last_n_lines
            continue
        # El fichero se recorre hacia atrás: al pasar el corte, lo que queda
        # es todavía más antiguo.
        if entry["timestamp"] < cutoff:
            break
        entries.append(entry)
    entries.reverse()
    return entries


# Ventanas de tiempo que ofrece el filtro global de Actividad de red. `None`
# es el comportamiento historico (ultimas 1000 peticiones, sin importar
# cuando ocurrieron) -se mantiene como opcion para no romper get_dashboard()
# ni ningun otro llamador que no pase ventana.
VENTANAS_SEGUNDOS = {"1h": 3600, "24h": 86400, "7d": 7 * 86400, "30d": 30 * 86400}


def _read_window(seconds: int | None) -> list[dict]:
    """Últimas 1000 peticiones (sin filtro) o todas las de una ventana de
    tiempo real -ver VENTANAS_SEGUNDOS. El tope de escaneo sube con la
    ventana: 7 días de un proxy con mucho trafico puede tener mas de 50.000
    lineas antes de llegar al corte real."""
    if seconds is None:
        return _read_last_n_lines(1000)
    tope = 50_000 if seconds <= 3600 else 150_000 if seconds <= 86400 else 400_000
    return _read_recent_logs(seconds, max_lines=tope)


# ============================================
# API pública
# ============================================

def get_realtime_traffic() -> dict:
    """Tráfico REAL en tiempo real desde Docker network stats."""
    # El log se lee primero para que sus contadores entren en el mismo punto
    # del historico que la muestra de red.
    log_entries = _read_recent_logs(60)
    active_ips = list(set(e["client_ip"] for e in log_entries))
    denied_60s = sum(1 for e in log_entries if e["denied"])

    cache = _resumen_cache(log_entries)
    latencia = _resumen_latencia(log_entries)

    net = _update_network_buffer({
        "requests": len(log_entries),
        "denied": denied_60s,
        "connections": len(active_ips),
        "cache_hit_ratio": cache["cache_hit_ratio"],
    })
    current = net["current"]

    # Calcular promedio de los últimos puntos del buffer
    buffer = net["buffer"]
    recent = buffer[-12:] if len(buffer) >= 12 else buffer  # últimos 60s
    avg_rx = sum(p["rx_bytes_per_second"] for p in recent) / len(recent) if recent else 0
    avg_tx = sum(p["tx_bytes_per_second"] for p in recent) / len(recent) if recent else 0

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
        "denied_requests_60s": denied_60s,
        **cache,
        **latencia,
        "active_ips": active_ips[:20],
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
            "timestamp": p["timestamp"],
            "rx_bytes": p["rx_bytes_per_second"],
            "tx_bytes": p["tx_bytes_per_second"],
            "total_bytes": p["rx_bytes_per_second"] + p["tx_bytes_per_second"],
            "requests": p.get("requests", 0),
            "denied": p.get("denied", 0),
            "connections": p.get("connections", 0),
            "cache_hit_ratio": p.get("cache_hit_ratio"),
            "mem_percent": p.get("mem_percent", 0),
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


def get_top_users(limit: int = 10, seconds: int | None = None, sort_by: str = "bytes") -> list[dict]:
    """Top usuarios por bytes o por cantidad de peticiones -no son lo mismo:
    pocas peticiones pueden pesar mucho (una descarga grande) y muchas
    peticiones pueden pesar poco (navegación normal). Antes se pedia siempre
    "top por bytes" y el toggle Datos/Peticiones del frontend solo cambiaba
    que numero mostrar, sin volver a ordenar -el ranking quedaba fijo por
    bytes aunque se mirara "por peticiones", y ademas un usuario con muchas
    peticiones pero pocos bytes podia quedar afuera del top directamente.
    Reportado en vivo por el usuario, 2026-09-12.
    """
    entries = _read_window(seconds)
    user_bytes = defaultdict(int)
    user_requests = defaultdict(int)
    for e in entries:
        if e["user"]:
            user_bytes[e["user"]] += e["bytes"]
            user_requests[e["user"]] += 1

    metrica = user_requests if sort_by == "requests" else user_bytes
    return [
        {"user": u, "bytes": user_bytes[u], "requests": user_requests[u]}
        for u, _ in sorted(metrica.items(), key=lambda x: x[1], reverse=True)[:limit]
    ]


def get_totales_actividad(seconds: int | None = None) -> dict:
    """Totales reales (todos los usuarios/dominios, no solo el top N) para
    la ventana pedida -Actividad de red los usa para el % de concentración
    y el "Total" junto al anillo: antes ese número sumaba solo las filas del
    top 10 visible, y con más de 10 usuarios/dominios reales el "Total"
    mostrado no era el total de verdad. Reportado en vivo por el usuario,
    2026-09-12.
    """
    entries = _read_window(seconds)

    usuarios_bytes = usuarios_requests = 0
    usuarios_vistos: set[str] = set()
    dominios_requests = dominios_bytes = 0
    dominios_vistos: set[str] = set()
    dominios_bloqueados_requests = 0
    dominios_bloqueados_vistos: set[str] = set()
    bloqueos_totales = 0

    for e in entries:
        if e["user"]:
            usuarios_bytes += e["bytes"]
            usuarios_requests += 1
            usuarios_vistos.add(e["user"])
        if e["domain"]:
            dominios_requests += 1
            dominios_bytes += e["bytes"]
            dominios_vistos.add(e["domain"])
        if e["denied"]:
            bloqueos_totales += 1
            if e["domain"]:
                dominios_bloqueados_requests += 1
                dominios_bloqueados_vistos.add(e["domain"])

    return {
        "usuarios": {"count": len(usuarios_vistos), "bytes": usuarios_bytes, "requests": usuarios_requests},
        "dominios": {"count": len(dominios_vistos), "requests": dominios_requests, "bytes": dominios_bytes},
        "dominios_bloqueados": {"count": len(dominios_bloqueados_vistos), "requests": dominios_bloqueados_requests},
        # Igual al total de get_top_blocked_users (con_usuario + anonimos),
        # pero sin necesitar cruzar contra la BD -acá solo hace falta el numero.
        "usuarios_bloqueados_requests": bloqueos_totales,
    }


def get_top_blocked_users(limit: int = 10, db=None, seconds: int | None = None) -> dict:
    """Usuarios con mas peticiones denegadas: quien choca mas con la politica.

    Complementa a "top sitios bloqueados", que dice que se bloquea pero no
    quien. IMPORTANTE: esto cuenta peticiones denegadas (407/403), que no es
    lo mismo que "cuenta deshabilitada". Una peticion puede denegarse por
    credenciales viejas cacheadas en el navegador, por una politica de grupo,
    o porque la cuenta esta deshabilitada de verdad en Usuarios — son cosas
    distintas. Por eso, si se pasa una sesion de BD, cada usuario de la lista
    se cruza contra su estado real (local o LDAP) para no dejar la duda.

    La mayoria de las peticiones denegadas de un navegador real son ruido de
    fondo (telemetria, sondas de conectividad) que nunca llega a mandar
    credenciales, asi que se informa aparte cuantos bloqueos quedaron sin
    usuario para que la diferencia con "top sitios bloqueados" no se lea
    como un fallo de esta tarjeta.
    """
    denegadas = [e for e in _read_window(seconds) if e["denied"]]
    con_usuario = [e for e in denegadas if e["user"]]
    conteo = Counter(e["user"] for e in con_usuario)
    top = conteo.most_common(limit)

    account_status: dict[str, str] = {}
    if db is not None and top:
        from app.models.proxy_user import ProxyUser
        from app.models.ldap_user import LdapUser

        nombres = [u for u, _ in top]
        for pu in db.query(ProxyUser).filter(ProxyUser.username.in_(nombres)).all():
            account_status[pu.username] = "enabled" if pu.enabled else "disabled"
        for lu in db.query(LdapUser).filter(LdapUser.username.in_(nombres)).all():
            # Si el mismo nombre existe local y LDAP (no deberia, pero por las
            # dudas) se prioriza el estado local, que es el que de verdad usa
            # Squid para autenticar via htpasswd.
            account_status.setdefault(lu.username, "enabled" if lu.enabled else "disabled")

    return {
        "users": [
            {
                "user": u,
                "blocked_requests": c,
                # "disabled" = la cuenta esta apagada en Usuarios (bloqueo real).
                # "enabled" = la cuenta sigue activa; los 407/403 son por otra
                # causa (credenciales viejas, politica de grupo, etc).
                # "unknown" = no se cruzo contra la BD, o el usuario no existe
                # como cuenta local ni LDAP (p.ej. se borro despues).
                "account_status": account_status.get(u, "unknown"),
            }
            for u, c in top
        ],
        "anonymous_blocked": len(denegadas) - len(con_usuario),
    }


def get_top_domains(limit: int = 10, denied_only: bool = False, seconds: int | None = None) -> list[dict]:
    entries = _read_window(seconds)
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


def get_latencia(limit: int = 10, seconds: int | None = None) -> dict:
    """Latencia general y por dominio, sobre la ventana pedida (ver _read_window).

    CONNECT (túneles HTTPS) se excluye tanto del promedio general (ver
    _resumen_latencia) como de la latencia por dominio: ahí `elapsed_ms`
    mide cuánto duró la conexión abierta, no cuánto tardó en responder.
    """
    entries = _read_window(seconds)
    resumen = _resumen_latencia(entries)

    por_dominio: dict[str, list[int]] = defaultdict(list)
    for e in entries:
        if e["method"] != "CONNECT" and e["domain"]:
            por_dominio[e["domain"]].append(e["elapsed_ms"])

    # Solo dominios con una muestra mínima: un único pedido lento no dice
    # nada sobre "el sitio es lento", puede ser ruido de una sola petición.
    MUESTRA_MINIMA = 3
    dominios = [
        {"domain": d, "avg_ms": round(sum(v) / len(v)), "samples": len(v)}
        for d, v in por_dominio.items() if len(v) >= MUESTRA_MINIMA
    ]
    dominios.sort(key=lambda x: x["avg_ms"], reverse=True)

    return {**resumen, "domains": dominios[:limit]}


def get_http_errors(limit: int = 10, seconds: int | None = None) -> dict:
    """Códigos de error HTTP más frecuentes y qué dominios los generan.

    No cuenta 401/403/407: ya están cubiertos por "Sitios/usuarios
    bloqueados" -contarlos acá duplicaría el mismo dato bajo otro nombre.
    Esto es para fallos reales del lado del servidor/red (502, 504, 500...)
    o recursos que no existen (404): la señal de "algo está roto", no de
    política de acceso.

    "total" ya es el total REAL (todos los errores de la ventana, no solo
    los de los dominios/codigos que entran en el top `limit`) -a diferencia
    del "Total" que tenia Actividad de Red antes de corregirlo, acá nunca
    hubo ese bug: se cuenta sobre `errores` completo, no sobre el top
    recortado.
    """
    entries = _read_window(seconds)
    CODIGOS_POLITICA = (401, 403, 407)
    errores = [e for e in entries if e["status"] >= 400 and e["status"] not in CODIGOS_POLITICA]

    por_codigo = Counter(e["status"] for e in errores)
    por_dominio = Counter(e["domain"] for e in errores if e["domain"])

    return {
        "total": len(errores),
        "by_code": [{"code": c, "count": n} for c, n in por_codigo.most_common(limit)],
        "by_domain": [{"domain": d, "count": n} for d, n in por_dominio.most_common(limit)],
    }


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


def get_detalle(user: str | None = None, domain: str | None = None, seconds: int | None = None, limit: int = 50) -> list[dict]:
    """Detalle de peticiones de un usuario o dominio puntual (drill-down).

    Complementa a los rankings (top usuarios/dominios): ahi solo se ve el
    numero agregado, aca se ve QUE URLs concretas explican ese numero -la
    pregunta que sigue naturalmente a "quien consume mas" o "que se
    bloquea mas". Requiere exactamente uno de `user`/`domain`, no los dos:
    cruzarlos no aporta mas que filtrar por uno solo, y complica la firma
    para el caso de uso real (clic en UNA fila de UN ranking).
    """
    entries = _read_window(seconds)
    if user:
        entries = [e for e in entries if e["user"] == user]
    if domain:
        entries = [e for e in entries if e["domain"] == domain]

    entries = entries[-limit:]
    return [
        {
            "time": datetime.fromtimestamp(e["timestamp"]).strftime("%Y-%m-%d %H:%M:%S"),
            "user": e["user"] or "-",
            "domain": e["domain"],
            "method": e["method"],
            "status": e["status"],
            "bytes": e["bytes"],
            "elapsed_ms": e["elapsed_ms"],
            "denied": e["denied"],
        }
        for e in reversed(entries)
    ]


def get_tendencia_trafico(user: str | None = None, domain: str | None = None, seconds: int | None = None, buckets: int = 20) -> dict:
    """Evolución en el tiempo (bytes y peticiones) de un usuario o dominio
    puntual, para el gráfico de Tendencias.

    Requiere exactamente uno de `user`/`domain` -mismo criterio que
    get_detalle(). En vez de "baldes" de tamaño fijo (ej. "cada hora"), se
    reparte el rango real de timestamps encontrado (del mas viejo al mas
    nuevo) en `buckets` partes iguales: funciona igual de bien con una
    ventana de 7 dias que con "ultimas 1000 peticiones" -que no tiene una
    duracion fija, puede ser 20 minutos o 3 dias segun cuanto trafico haya-,
    sin tener que adivinar el tamaño de balde "correcto" para cada caso.
    """
    entries = _read_window(seconds)
    if user:
        entries = [e for e in entries if e["user"] == user]
    if domain:
        entries = [e for e in entries if e["domain"] == domain]

    if not entries:
        return {"points": [], "user": user, "domain": domain}

    ts_min = entries[0]["timestamp"]
    ts_max = entries[-1]["timestamp"]
    span = max(ts_max - ts_min, 1)
    ancho = span / buckets

    grupos = [{"bytes": 0, "requests": 0} for _ in range(buckets)]
    for e in entries:
        idx = min(int((e["timestamp"] - ts_min) / ancho), buckets - 1)
        grupos[idx]["bytes"] += e["bytes"]
        grupos[idx]["requests"] += 1

    puntos = [
        {
            "timestamp": ts_min + ancho * (i + 0.5),
            "bytes": g["bytes"],
            "requests": g["requests"],
        }
        for i, g in enumerate(grupos)
    ]
    return {"points": puntos, "user": user, "domain": domain}


def get_volumen_por_periodo(seconds: int | None = None) -> dict:
    """Volumen de tráfico agrupado en baldes que se adaptan a la ventana
    elegida -antes esto vivía en dos funciones separadas ("por día de la
    semana", que siempre mostraba 7 barras fijas sin importar la ventana, y
    "volumen diario", que agrupaba por día calendario). El problema con la
    primera: elegir "30 días" no cambiaba la FORMA del gráfico, solo sumaba
    más datos a las mismas 7 barras de siempre -confuso, porque el usuario
    esperaba ver 30 barras distintas.

    Ahora la granularidad del balde depende de qué tan larga es la ventana,
    para que el gráfico realmente cambie de forma según lo elegido:
      - ventana <= 1h: baldes de 5 minutos (~12 puntos)
      - ventana <= 24h: baldes de 1 hora (~24 puntos)
      - ventana mayor (7d, 30d) o sin ventana (recientes): un balde por día
        calendario -esto absorbe lo que antes era get_volumen_diario.

    Se devuelve también la granularidad usada, para que el frontend sepa
    cómo formatear las etiquetas del eje X y del tooltip (hora vs fecha).
    """
    entries = _read_window(seconds)
    if not entries:
        return {"granularidad": "dia", "puntos": []}

    if seconds is not None and seconds <= 3600:
        granularidad = "minuto"
        ancho = 300
    elif seconds is not None and seconds <= 86400:
        granularidad = "hora"
        ancho = 3600
    else:
        granularidad = "dia"
        ancho = None

    grupos: dict[float, dict] = {}
    for e in entries:
        if granularidad == "dia":
            dt = datetime.fromtimestamp(e["timestamp"]).replace(hour=0, minute=0, second=0, microsecond=0)
            clave = dt.timestamp()
        else:
            clave = (int(e["timestamp"]) // ancho) * ancho
        g = grupos.setdefault(clave, {"timestamp": clave, "bytes": 0, "requests": 0})
        g["bytes"] += e["bytes"]
        g["requests"] += 1

    puntos = [grupos[k] for k in sorted(grupos.keys())]
    return {"granularidad": granularidad, "puntos": puntos}


def get_dashboard(db=None) -> dict:
    """Dashboard completo: todas las métricas en una sola llamada."""
    traffic = get_realtime_traffic()
    return {
        "traffic": traffic,
        "top_users": get_top_users(10),
        "top_domains": get_top_domains(10, denied_only=False),
        "top_blocked": get_top_domains(10, denied_only=True),
        "top_blocked_users": get_top_blocked_users(10, db=db),
        "system": get_system_metrics(),
        "timeline": get_traffic_timeline(),
        "connections": get_recent_connections(10),
    }