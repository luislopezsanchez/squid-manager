"""Agregados por hora del access.log: ingesta incremental y consultas.

Problema que resuelve: Actividad de red, Latencia, Errores, Panorama,
Tendencias y el PDF releían y parseaban el access.log (más los rotados,
algunos .gz) completo en CADA petición para ventanas de 24h/7d/30d. El coste
crece con el tráfico y con los días pedidos.

Cómo: un hilo de fondo lee SOLO las líneas nuevas cada `_POLL_SECONDS` y las
suma en tablas por hora (ru_*, migración 0040). Las consultas del panel
hacen `SELECT ... GROUP BY` sobre esas tablas: tiempo casi constante y no
depende del tamaño del log.

Precisión: la resolución es la hora. Una ventana de "24h" cubre desde el
comienzo de la hora de hace 24h (hasta 1h de más). Los percentiles de
latencia salen de un histograma de cubos fijos (`LAT_EDGES`), no del valor
exacto. Las ventanas de 1h y "últimas 1000 peticiones" siguen leyendo el log
directo: son rápidas y necesitan precisión por minuto.

Rotación: se recuerda (inode, offset) del access.log activo. Cuando el inode
cambia, el archivo viejo es ahora el rotado más reciente: se termina de
leer desde el offset guardado (sin duplicar lo ya contado) y se marca como
procesado. Los rotados que nunca se vieron (backfill inicial, o el servicio
estuvo apagado) se leen enteros una sola vez.
"""

import gzip
import json
import logging
import os
import re
import threading
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

from app.database import SessionLocal

logger = logging.getLogger(__name__)

ACCESS_LOG_PATH = "/var/log/squid/access.log"
_POLL_SECONDS = 30
_BATCH_LINES = 200_000
# Días de agregados que se conservan (las ventanas del panel llegan a 30d;
# el resto es margen para rangos libres y comparativas).
RETENTION_DAYS = int(os.environ.get("ROLLUP_RETENTION_DAYS", "120"))

# Bordes superiores (ms) de los cubos del histograma de latencia. El último
# cubo (índice len(LAT_EDGES)) recoge todo lo mayor.
LAT_EDGES = (5, 10, 25, 50, 100, 200, 300, 500, 750, 1000, 1500, 2000, 3000, 5000, 10000, 30000)

_CODIGOS_POLITICA = (401, 403, 407)
_ACIERTOS = ("TCP_HIT", "TCP_MEM_HIT", "TCP_IMS_HIT", "TCP_INM_HIT", "TCP_REFRESH_UNMODIFIED")
_FALLOS = ("TCP_MISS", "TCP_REFRESH_MODIFIED", "TCP_CLIENT_REFRESH_MISS", "TCP_SWAPFAIL_MISS")

_ready = False           # True cuando terminó el backfill inicial
_lock = threading.Lock()  # una sola ingesta a la vez (hilo de fondo / tests)


# ---------------------------------------------------------------------------
# Agregación en memoria (función pura, testeable sin base de datos)
# ---------------------------------------------------------------------------

def _bucket_lat(ms: int) -> int:
    for i, edge in enumerate(LAT_EDGES):
        if ms <= edge:
            return i
    return len(LAT_EDGES)


def _hora(ts: float) -> int:
    return int(ts) // 3600 * 3600


class Agregado:
    """Acumulador en memoria de un lote de líneas."""

    def __init__(self):
        self.total = defaultdict(lambda: [0] * 9)     # h -> req,bytes,denied,errors,hits,misses,bytes_hit,lat_sum,lat_n
        self.lat = defaultdict(int)                   # (h, b) -> n
        self.status = defaultdict(int)                # (h, status) -> n
        self.user = defaultdict(lambda: [0, 0, 0])    # (h, user) -> req,bytes,denied
        self.domain = defaultdict(lambda: [0] * 7)    # (h, dom) -> req,bytes,denied,denied_bytes,errors,lat_sum,lat_n
        self.ipuser = defaultdict(int)                # (h, ip, user) -> req
        self.lineas = 0

    def agregar(self, e: dict) -> None:
        """`e` es una entrada ya parseada (metrics_service._parse_log_line)."""
        h = _hora(e["timestamp"])
        b = e["bytes"]
        denied = bool(e["denied"])
        status = e["status"]
        es_error = status >= 400 and status not in _CODIGOS_POLITICA
        base = e["action"].split("_ABORTED")[0]
        es_connect = e["method"] == "CONNECT"

        t = self.total[h]
        t[0] += 1
        t[1] += b
        if denied:
            t[2] += 1
        if es_error:
            t[3] += 1
        if base in _ACIERTOS:
            t[4] += 1
            t[6] += b
        elif base in _FALLOS:
            t[5] += 1
        if not es_connect:
            t[7] += e["elapsed_ms"]
            t[8] += 1
            self.lat[(h, _bucket_lat(e["elapsed_ms"]))] += 1
        self.status[(h, status)] += 1

        u = e["user"]
        if u:
            r = self.user[(h, u)]
            r[0] += 1
            r[1] += b
            if denied:
                r[2] += 1
            self.ipuser[(h, e["client_ip"], u)] += 1

        d = e["domain"]
        if d:
            r = self.domain[(h, d[:255])]
            r[0] += 1
            r[1] += b
            if denied:
                r[2] += 1
                r[3] += b
            if es_error:
                r[4] += 1
            if not es_connect:
                r[5] += e["elapsed_ms"]
                r[6] += 1
        self.lineas += 1


def agregar_lineas(lineas, parse) -> Agregado:
    ag = Agregado()
    for linea in lineas:
        e = parse(linea)
        if e and not e["interno"]:
            ag.agregar(e)
    return ag


# ---------------------------------------------------------------------------
# Escritura
# ---------------------------------------------------------------------------

_UPSERTS = {
    "ru_total": (
        "INSERT INTO ru_total (h,requests,bytes,denied,errors,hits,misses,bytes_hit,lat_sum,lat_n) "
        "VALUES (:h,:a0,:a1,:a2,:a3,:a4,:a5,:a6,:a7,:a8) ON CONFLICT (h) DO UPDATE SET "
        "requests=ru_total.requests+EXCLUDED.requests, bytes=ru_total.bytes+EXCLUDED.bytes, "
        "denied=ru_total.denied+EXCLUDED.denied, errors=ru_total.errors+EXCLUDED.errors, "
        "hits=ru_total.hits+EXCLUDED.hits, misses=ru_total.misses+EXCLUDED.misses, "
        "bytes_hit=ru_total.bytes_hit+EXCLUDED.bytes_hit, lat_sum=ru_total.lat_sum+EXCLUDED.lat_sum, "
        "lat_n=ru_total.lat_n+EXCLUDED.lat_n"
    ),
    "ru_lat": (
        "INSERT INTO ru_lat (h,b,n) VALUES (:h,:b,:n) ON CONFLICT (h,b) DO UPDATE SET n=ru_lat.n+EXCLUDED.n"
    ),
    "ru_status": (
        "INSERT INTO ru_status (h,status,n) VALUES (:h,:s,:n) ON CONFLICT (h,status) DO UPDATE SET n=ru_status.n+EXCLUDED.n"
    ),
    "ru_user": (
        "INSERT INTO ru_user (h,username,requests,bytes,denied) VALUES (:h,:u,:a0,:a1,:a2) "
        "ON CONFLICT (h,username) DO UPDATE SET requests=ru_user.requests+EXCLUDED.requests, "
        "bytes=ru_user.bytes+EXCLUDED.bytes, denied=ru_user.denied+EXCLUDED.denied"
    ),
    "ru_domain": (
        "INSERT INTO ru_domain (h,domain,requests,bytes,denied,denied_bytes,errors,lat_sum,lat_n) "
        "VALUES (:h,:d,:a0,:a1,:a2,:a3,:a4,:a5,:a6) ON CONFLICT (h,domain) DO UPDATE SET "
        "requests=ru_domain.requests+EXCLUDED.requests, bytes=ru_domain.bytes+EXCLUDED.bytes, "
        "denied=ru_domain.denied+EXCLUDED.denied, denied_bytes=ru_domain.denied_bytes+EXCLUDED.denied_bytes, "
        "errors=ru_domain.errors+EXCLUDED.errors, lat_sum=ru_domain.lat_sum+EXCLUDED.lat_sum, "
        "lat_n=ru_domain.lat_n+EXCLUDED.lat_n"
    ),
    "ru_ipuser": (
        "INSERT INTO ru_ipuser (h,ip,username,requests) VALUES (:h,:ip,:u,:n) "
        "ON CONFLICT (h,ip,username) DO UPDATE SET requests=ru_ipuser.requests+EXCLUDED.requests"
    ),
}


def _filas(ag: Agregado) -> dict[str, list[dict]]:
    def vec(_, vals):
        return {f"a{i}": v for i, v in enumerate(vals)}

    return {
        "ru_total": [{"h": h, **vec(None, v)} for h, v in ag.total.items()],
        "ru_lat": [{"h": h, "b": b, "n": n} for (h, b), n in ag.lat.items()],
        "ru_status": [{"h": h, "s": s, "n": n} for (h, s), n in ag.status.items()],
        "ru_user": [{"h": h, "u": u, **vec(None, v)} for (h, u), v in ag.user.items()],
        "ru_domain": [{"h": h, "d": d, **vec(None, v)} for (h, d), v in ag.domain.items()],
        "ru_ipuser": [{"h": h, "ip": ip, "u": u, "n": n} for (h, ip, u), n in ag.ipuser.items()],
    }


_CLAVES = {
    "ru_total": ("h",), "ru_lat": ("h", "b"), "ru_status": ("h", "s"), "ru_user": ("h", "u"),
    "ru_domain": ("h", "d"), "ru_ipuser": ("h", "ip", "u"),
}


def _volcar(db, ag: Agregado) -> None:
    """Suma el lote a las tablas. Las filas van ordenadas por clave para que
    dos escrituras concurrentes no se bloqueen entre sí en distinto orden."""
    for tabla, filas in _filas(ag).items():
        if not filas:
            continue
        claves = _CLAVES[tabla]
        filas.sort(key=lambda r: tuple(r[k] for k in claves))
        for i in range(0, len(filas), 5000):
            db.execute(text(_UPSERTS[tabla]), filas[i:i + 5000])


# ---------------------------------------------------------------------------
# Estado (offset / archivos ya procesados)
# ---------------------------------------------------------------------------

def _get_state(db, k: str) -> str | None:
    row = db.execute(text("SELECT v FROM ru_state WHERE k=:k"), {"k": k}).first()
    return row[0] if row else None


def _set_state(db, k: str, v: str) -> None:
    db.execute(
        text("INSERT INTO ru_state (k,v) VALUES (:k,:v) ON CONFLICT (k) DO UPDATE SET v=EXCLUDED.v"),
        {"k": k, "v": v},
    )


def _rotados() -> list[tuple[str, str]]:
    """[(stem, ruta)] de los access.log rotados, del más viejo al más nuevo."""
    archive = Path(ACCESS_LOG_PATH).parent / "archive"
    if not archive.is_dir():
        return []
    patron = re.compile(r"^access\.log-(\d{8})(?:\.gz)?$")
    out = []
    for p in archive.iterdir():
        m = patron.match(p.name)
        if m:
            out.append((m.group(1), str(p)))
    out.sort()
    return out


def _leer_lineas_desde(ruta: str, offset: int = 0):
    """Líneas completas de `ruta` desde `offset` (bytes). Devuelve
    (lineas, nuevo_offset). Solo para archivos sin comprimir."""
    with open(ruta, "rb") as f:
        f.seek(offset)
        chunk = f.read()
    if not chunk:
        return [], offset
    ult = chunk.rfind(b"\n")
    if ult == -1:
        return [], offset
    completo = chunk[: ult + 1]
    return completo.decode("utf-8", errors="replace").splitlines(), offset + len(completo)


def _ingerir_archivo_completo(db, ruta: str, parse) -> int:
    abrir = gzip.open if ruta.endswith(".gz") else open
    total = 0
    lote = []
    with abrir(ruta, "rt", encoding="utf-8", errors="replace") as f:
        for linea in f:
            lote.append(linea.rstrip("\n"))
            if len(lote) >= _BATCH_LINES:
                ag = agregar_lineas(lote, parse)
                _volcar(db, ag)
                db.commit()
                total += ag.lineas
                lote = []
    if lote:
        ag = agregar_lineas(lote, parse)
        _volcar(db, ag)
        db.commit()
        total += ag.lineas
    return total


# ---------------------------------------------------------------------------
# Un ciclo de ingesta
# ---------------------------------------------------------------------------

def tick() -> dict:
    """Pone al día los agregados. Idempotente entre llamadas: lo ya contado
    no se vuelve a contar (offset + archivos marcados)."""
    global _ready
    from app.services.metrics_service import _parse_log_line as parse

    with _lock:
        db = SessionLocal()
        try:
            resumen = {"archivos": 0, "lineas": 0}
            activo = Path(ACCESS_LOG_PATH)
            estado = json.loads(_get_state(db, "active") or "null")
            st = activo.stat() if activo.exists() else None

            # 1) Rotación: el inode del activo cambió -> el viejo es un rotado.
            if estado and st and estado["inode"] != st.st_ino:
                viejo = None
                for stem, ruta in reversed(_rotados()):
                    if not ruta.endswith(".gz") and os.stat(ruta).st_ino == estado["inode"]:
                        viejo = (stem, ruta)
                        break
                if viejo:
                    lineas, _ = _leer_lineas_desde(viejo[1], estado["offset"])
                    ag = agregar_lineas(lineas, parse)
                    _volcar(db, ag)
                    resumen["lineas"] += ag.lineas
                    _set_state(db, f"arch:{viejo[0]}", "done")
                else:
                    # No se pudo identificar (ya comprimido): mejor perder unos
                    # segundos que contar dos veces todo el archivo.
                    nuevos = [s for s, _ in _rotados() if _get_state(db, f"arch:{s}") is None]
                    if nuevos:
                        _set_state(db, f"arch:{nuevos[-1]}", "done")
                        logger.warning("Rotación no identificada por inode; se marca %s como procesado", nuevos[-1])
                estado = None
                _set_state(db, "active", "null")
                db.commit()

            # 2) Rotados nunca vistos (backfill inicial o servicio apagado).
            for stem, ruta in _rotados():
                if _get_state(db, f"arch:{stem}") is not None:
                    continue
                try:
                    n = _ingerir_archivo_completo(db, ruta, parse)
                except OSError as e:
                    logger.warning("No se pudo leer el log rotado %s: %s", ruta, e)
                    continue
                _set_state(db, f"arch:{stem}", "done")
                db.commit()
                resumen["archivos"] += 1
                resumen["lineas"] += n

            # 3) El activo, desde el último offset.
            if st:
                offset = estado["offset"] if estado else 0
                if st.st_size < offset:  # truncado (copytruncate)
                    offset = 0
                while True:
                    lineas, nuevo = _leer_lineas_desde(str(activo), offset)
                    if not lineas:
                        break
                    ag = agregar_lineas(lineas, parse)
                    _volcar(db, ag)
                    resumen["lineas"] += ag.lineas
                    offset = nuevo
                    _set_state(db, "active", json.dumps({"inode": st.st_ino, "offset": offset}))
                    db.commit()
                    if len(lineas) < _BATCH_LINES:
                        break
                if not estado:
                    _set_state(db, "active", json.dumps({"inode": st.st_ino, "offset": offset}))
                    db.commit()

            _set_state(db, "ready", "1")
            db.commit()
            _ready = True
            return resumen
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


def _purgar_viejos() -> None:
    db = SessionLocal()
    try:
        limite = int(time.time()) - RETENTION_DAYS * 86400
        for t in ("ru_total", "ru_lat", "ru_status", "ru_user", "ru_domain", "ru_ipuser"):
            db.execute(text(f"DELETE FROM {t} WHERE h < :l"), {"l": limite})
        db.commit()
    finally:
        db.close()


def _loop() -> None:
    logger.info("Agregador de access.log (rollups por hora) iniciado")
    ultima_purga = 0.0
    while True:
        try:
            r = tick()
            if r["lineas"]:
                logger.info("Rollups: %s líneas, %s archivos rotados", r["lineas"], r["archivos"])
            if time.time() - ultima_purga > 6 * 3600:
                _purgar_viejos()
                ultima_purga = time.time()
        except Exception as e:
            logger.error("Error en el agregador de access.log: %s", e)
        time.sleep(_POLL_SECONDS)


def start_rollup_service() -> None:
    """Arranca el hilo de fondo una sola vez, al iniciar el backend."""
    threading.Thread(target=_loop, name="rollup-service", daemon=True).start()


# ---------------------------------------------------------------------------
# Consultas
# ---------------------------------------------------------------------------

def _rango(seconds: int | None, desde: float | None, hasta: float | None) -> tuple[int, int] | None:
    """[h0, h1] (horas, inclusive) que cubre la consulta, o None si esta
    consulta debe seguir leyendo el log directo."""
    ahora = time.time()
    if desde is not None and hasta is not None:
        return _hora(desde), _hora(hasta)
    if seconds is None or seconds <= 3600:
        return None
    return _hora(ahora - seconds), _hora(ahora)


def disponible(seconds: int | None = None, desde: float | None = None, hasta: float | None = None) -> bool:
    if _rango(seconds, desde, hasta) is None:
        return False
    if _ready:
        return True
    # Tras un reinicio el hilo aún no corrió: el estado persistido dice si
    # el backfill ya se hizo alguna vez.
    db = SessionLocal()
    try:
        return _get_state(db, "ready") == "1"
    except Exception:
        return False
    finally:
        db.close()


def _q(sql: str, params: dict) -> list:
    db = SessionLocal()
    try:
        return db.execute(text(sql), params).fetchall()
    finally:
        db.close()


def _p(seconds, desde, hasta) -> dict:
    h0, h1 = _rango(seconds, desde, hasta)
    return {"h0": h0, "h1": h1}


def top_users(limit, sort_by, seconds, desde, hasta) -> list[dict]:
    col = "requests" if sort_by == "requests" else "bytes"
    rows = _q(
        f"SELECT username, SUM(bytes), SUM(requests) FROM ru_user WHERE h BETWEEN :h0 AND :h1 "
        f"GROUP BY username ORDER BY SUM({col}) DESC, username LIMIT :n",
        {**_p(seconds, desde, hasta), "n": limit},
    )
    return [{"user": r[0], "bytes": int(r[1]), "requests": int(r[2])} for r in rows]


def top_domains(limit, denied_only, sort_by, seconds, desde, hasta) -> list[dict]:
    if denied_only:
        req, byt = "denied", "denied_bytes"
    else:
        req, byt = "requests", "bytes"
    col = byt if sort_by == "bytes" else req
    rows = _q(
        f"SELECT domain, SUM({req}), SUM({byt}) FROM ru_domain WHERE h BETWEEN :h0 AND :h1 "
        f"GROUP BY domain HAVING SUM({req}) > 0 ORDER BY SUM({col}) DESC, domain LIMIT :n",
        {**_p(seconds, desde, hasta), "n": limit},
    )
    return [{"domain": r[0], "requests": int(r[1]), "bytes": int(r[2])} for r in rows]


def totales_actividad(seconds, desde, hasta) -> dict:
    p = _p(seconds, desde, hasta)
    u = _q("SELECT COUNT(DISTINCT username), COALESCE(SUM(bytes),0), COALESCE(SUM(requests),0) "
           "FROM ru_user WHERE h BETWEEN :h0 AND :h1", p)[0]
    d = _q("SELECT COUNT(DISTINCT domain), COALESCE(SUM(requests),0), COALESCE(SUM(bytes),0) "
           "FROM ru_domain WHERE h BETWEEN :h0 AND :h1", p)[0]
    b = _q("SELECT COUNT(DISTINCT domain), COALESCE(SUM(denied),0) FROM ru_domain "
           "WHERE h BETWEEN :h0 AND :h1 AND denied > 0", p)[0]
    t = _q("SELECT COALESCE(SUM(denied),0) FROM ru_total WHERE h BETWEEN :h0 AND :h1", p)[0]
    return {
        "usuarios": {"count": int(u[0]), "bytes": int(u[1]), "requests": int(u[2])},
        "dominios": {"count": int(d[0]), "requests": int(d[1]), "bytes": int(d[2])},
        "dominios_bloqueados": {"count": int(b[0]), "requests": int(b[1])},
        "usuarios_bloqueados_requests": int(t[0]),
    }


def top_blocked_users(limit, seconds, desde, hasta) -> tuple[list[tuple[str, int]], int]:
    """([(usuario, bloqueos)], bloqueos_sin_usuario)."""
    p = _p(seconds, desde, hasta)
    rows = _q("SELECT username, SUM(denied) FROM ru_user WHERE h BETWEEN :h0 AND :h1 "
              "GROUP BY username HAVING SUM(denied) > 0 ORDER BY SUM(denied) DESC, username LIMIT :n",
              {**p, "n": limit})
    con_usuario = _q("SELECT COALESCE(SUM(denied),0) FROM ru_user WHERE h BETWEEN :h0 AND :h1", p)[0][0]
    total = _q("SELECT COALESCE(SUM(denied),0) FROM ru_total WHERE h BETWEEN :h0 AND :h1", p)[0][0]
    return [(r[0], int(r[1])) for r in rows], int(total) - int(con_usuario)


def ips_compartidas(limit, seconds, desde, hasta) -> list[dict]:
    rows = _q(
        "SELECT ip, COUNT(DISTINCT username) AS nu, SUM(requests) AS req, "
        "ARRAY_AGG(DISTINCT username) FROM ru_ipuser WHERE h BETWEEN :h0 AND :h1 "
        "GROUP BY ip HAVING COUNT(DISTINCT username) >= 2 ORDER BY nu DESC, req DESC LIMIT :n",
        {**_p(seconds, desde, hasta), "n": limit},
    )
    return [{"ip": r[0], "usuarios": sorted(r[3]), "requests": int(r[2])} for r in rows]


def _percentil(hist: list[int], p: float) -> int | None:
    total = sum(hist)
    if not total:
        return None
    objetivo = total * p
    acum = 0
    for i, n in enumerate(hist):
        acum += n
        if acum > objetivo or i == len(hist) - 1:
            return LAT_EDGES[i] if i < len(LAT_EDGES) else LAT_EDGES[-1] * 2
    return None


def latencia(limit, seconds, desde, hasta) -> dict:
    p = _p(seconds, desde, hasta)
    s, n = _q("SELECT COALESCE(SUM(lat_sum),0), COALESCE(SUM(lat_n),0) FROM ru_total "
              "WHERE h BETWEEN :h0 AND :h1", p)[0]
    hist = [0] * (len(LAT_EDGES) + 1)
    for b, c in _q("SELECT b, SUM(n) FROM ru_lat WHERE h BETWEEN :h0 AND :h1 GROUP BY b", p):
        hist[b] = int(c)
    if not n:
        resumen = {"latency_avg_ms": None, "latency_p50_ms": None, "latency_p95_ms": None}
    else:
        resumen = {
            "latency_avg_ms": round(int(s) / int(n)),
            "latency_p50_ms": _percentil(hist, 0.50),
            "latency_p95_ms": _percentil(hist, 0.95),
        }
    rows = _q("SELECT domain, SUM(lat_sum), SUM(lat_n) FROM ru_domain WHERE h BETWEEN :h0 AND :h1 "
              "GROUP BY domain HAVING SUM(lat_n) >= 3 ORDER BY SUM(lat_sum)::float/SUM(lat_n) DESC LIMIT :n",
              {**p, "n": limit})
    dominios = [{"domain": r[0], "avg_ms": round(int(r[1]) / int(r[2])), "samples": int(r[2])} for r in rows]
    return {**resumen, "domains": dominios}


def errores_http(limit, seconds, desde, hasta) -> dict:
    p = _p(seconds, desde, hasta)
    por_codigo = _q(
        "SELECT status, SUM(n) FROM ru_status WHERE h BETWEEN :h0 AND :h1 AND status >= 400 "
        "AND status NOT IN (401,403,407) GROUP BY status ORDER BY SUM(n) DESC LIMIT :n", {**p, "n": limit})
    total = _q("SELECT COALESCE(SUM(errors),0) FROM ru_total WHERE h BETWEEN :h0 AND :h1", p)[0][0]
    por_dominio = _q(
        "SELECT domain, SUM(errors) FROM ru_domain WHERE h BETWEEN :h0 AND :h1 AND errors > 0 "
        "GROUP BY domain ORDER BY SUM(errors) DESC, domain LIMIT :n", {**p, "n": limit})
    return {
        "total": int(total),
        "by_code": [{"code": int(r[0]), "count": int(r[1])} for r in por_codigo],
        "by_domain": [{"domain": r[0], "count": int(r[1])} for r in por_dominio],
    }


def cache_resumen(seconds, desde, hasta) -> dict:
    p = _p(seconds, desde, hasta)
    h, m, bh = _q("SELECT COALESCE(SUM(hits),0), COALESCE(SUM(misses),0), COALESCE(SUM(bytes_hit),0) "
                  "FROM ru_total WHERE h BETWEEN :h0 AND :h1", p)[0]
    h, m, bh = int(h), int(m), int(bh)
    return {
        "cache_hits": h, "cache_misses": m,
        "cache_hit_ratio": round(h / (h + m) * 100, 1) if (h + m) else None,
        "cache_bytes_saved": bh,
    }


def serie_total(seconds, desde, hasta) -> list[dict]:
    """Una fila por hora: peticiones, bytes, bloqueos, errores, aciertos, fallos
    y latencia media. Base de los gráficos de Panorama/Tendencias."""
    rows = _q("SELECT h, requests, bytes, denied, errors, hits, misses, lat_sum, lat_n FROM ru_total "
              "WHERE h BETWEEN :h0 AND :h1 ORDER BY h", _p(seconds, desde, hasta))
    return [
        {"timestamp": r[0], "requests": int(r[1]), "bytes": int(r[2]), "denied": int(r[3]),
         "errors": int(r[4]), "hits": int(r[5]), "misses": int(r[6]),
         "latency_avg_ms": round(int(r[7]) / int(r[8])) if r[8] else None}
        for r in rows
    ]


def volumen_por_periodo(seconds, desde, hasta) -> dict:
    """Mismo formato que metrics_service.get_volumen_por_periodo: por hora
    hasta 24h, por día calendario para ventanas mayores."""
    horas = serie_total(seconds, desde, hasta)
    if not horas:
        return {"granularidad": "dia", "puntos": []}
    largo = seconds if seconds else (hasta - desde)
    if largo <= 86400:
        return {"granularidad": "hora",
                "puntos": [{"timestamp": x["timestamp"], "bytes": x["bytes"], "requests": x["requests"]} for x in horas]}
    dias: dict[float, dict] = {}
    for x in horas:
        d = datetime.fromtimestamp(x["timestamp"]).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        g = dias.setdefault(d, {"timestamp": d, "bytes": 0, "requests": 0})
        g["bytes"] += x["bytes"]
        g["requests"] += x["requests"]
    return {"granularidad": "dia", "puntos": [dias[k] for k in sorted(dias)]}


def serie_entidad(user, domain, seconds, desde, hasta) -> list[dict]:
    p = _p(seconds, desde, hasta)
    if user:
        rows = _q("SELECT h, SUM(bytes), SUM(requests) FROM ru_user WHERE username=:e "
                  "AND h BETWEEN :h0 AND :h1 GROUP BY h ORDER BY h", {**p, "e": user})
    else:
        rows = _q("SELECT h, SUM(bytes), SUM(requests) FROM ru_domain WHERE domain=:e "
                  "AND h BETWEEN :h0 AND :h1 GROUP BY h ORDER BY h", {**p, "e": domain})
    return [{"timestamp": r[0], "bytes": int(r[1]), "requests": int(r[2])} for r in rows]


def opciones_de_filtro(horas: int = 24) -> dict:
    """Usuarios, códigos y dominios vistos en las últimas `horas`, para los
    desplegables de filtros del visor de Registros (antes escaneaba 50.000
    líneas del log en cada refresco solo para armarlos)."""
    p = {"h0": _hora(time.time() - horas * 3600), "h1": _hora(time.time())}
    usuarios = _q("SELECT username FROM ru_user WHERE h BETWEEN :h0 AND :h1 GROUP BY username "
                  "ORDER BY SUM(requests) DESC LIMIT 300", p)
    estados = _q("SELECT DISTINCT status FROM ru_status WHERE h BETWEEN :h0 AND :h1 ORDER BY status", p)
    dominios = _q("SELECT domain FROM ru_domain WHERE h BETWEEN :h0 AND :h1 GROUP BY domain "
                  "ORDER BY SUM(requests) DESC LIMIT 50", p)
    total = _q("SELECT COALESCE(SUM(requests),0) FROM ru_total WHERE h BETWEEN :h0 AND :h1", p)[0][0]
    return {
        "total_entries": int(total),
        "truncated": False,
        "users": sorted(r[0] for r in usuarios),
        "statuses": [int(r[0]) for r in estados],
        "top_domains": sorted(r[0] for r in dominios),
    }
