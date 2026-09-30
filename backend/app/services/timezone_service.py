"""Zona horaria de la instalación.

Las cuotas se reinician a medianoche, los lunes y el día 1, y los gráficos
agrupan por día: todo eso depende de QUÉ hora es «aquí». Antes se usaba la
zona del sistema operativo (en una VM recién instalada suele ser UTC, y la
«medianoche» caía a las 19:00 o 20:00 hora de Cuba, por ejemplo). Ahora el
administrador la elige en Sistema → Configuración; si no elige ninguna se
sigue usando la del sistema, como antes.

Se guarda en `app_settings` (clave `timezone`).
"""
import time
import threading
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, available_timezones

from sqlalchemy import text

from app.database import SessionLocal

_CLAVE = "timezone"
_lock = threading.Lock()
_cache: dict = {"t": 0.0, "nombre": None}


def _leer() -> str | None:
    db = SessionLocal()
    try:
        r = db.execute(text("SELECT v FROM app_settings WHERE k=:k"), {"k": _CLAVE}).fetchone()
        return r[0] if r and r[0] else None
    except Exception:
        return None
    finally:
        db.close()


def nombre_configurado() -> str | None:
    """Zona elegida por el admin, o None si se usa la del sistema."""
    with _lock:
        if time.time() - _cache["t"] > 30:
            _cache["nombre"], _cache["t"] = _leer(), time.time()
        return _cache["nombre"]


def nombre_sistema() -> str:
    try:
        with open("/etc/timezone") as f:
            n = f.read().strip()
            if n:
                return n
    except OSError:
        pass
    return time.tzname[0] or "UTC"


def get_tz():
    """tzinfo efectiva: la elegida, o la local del sistema."""
    n = nombre_configurado()
    if n:
        try:
            return ZoneInfo(n)
        except Exception:
            pass
    return datetime.now().astimezone().tzinfo


def guardar(nombre: str | None) -> None:
    db = SessionLocal()
    try:
        if nombre:
            db.execute(text("INSERT INTO app_settings (k,v) VALUES (:k,:v) ON CONFLICT (k) DO UPDATE SET v=EXCLUDED.v"),
                       {"k": _CLAVE, "v": nombre})
        else:
            db.execute(text("DELETE FROM app_settings WHERE k=:k"), {"k": _CLAVE})
        db.commit()
    finally:
        db.close()
    with _lock:
        _cache["t"] = 0.0


def es_valida(nombre: str) -> bool:
    return nombre in available_timezones()


def zonas() -> list[str]:
    return sorted(z for z in available_timezones() if "/" in z or z == "UTC")


def ahora_local() -> datetime:
    return datetime.now(timezone.utc).astimezone(get_tz())


def inicio_dia(ts: float) -> float:
    """Epoch de las 00:00 (hora de la instalación) del día al que pertenece `ts`."""
    d = datetime.fromtimestamp(ts, get_tz()).replace(hour=0, minute=0, second=0, microsecond=0)
    return d.timestamp()


def utc_naive_a_local(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc).astimezone(get_tz())


def local_a_utc_naive(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(tzinfo=None)
