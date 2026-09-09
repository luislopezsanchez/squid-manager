"""Estadísticas de caché de Squid: lee y parsea el Cache Manager (mgr:info,

mgr:storedir), que Squid expone por HTTP normal en su propio puerto -ver la
nota junto a ProxyRuntime.cache_manager_report() sobre cómo se llega ahí en
cada modo de despliegue (nativo: petición directa; Docker: dentro del propio
contenedor, sin ensanchar ningún permiso de red).

El texto que devuelve Squid es humano, no JSON -este módulo lo convierte a
algo que el frontend pueda mostrar sin parsear texto en el navegador.
"""

import logging
import re

from app.models.squid_settings import SquidSetting
from app.services.runtime import get_runtime
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Únicos reportes que este servicio sabe pedir y mostrar -el frontend nunca
# manda un nombre de reporte libre; otros reportes de Squid (mgr:config, por
# ejemplo) pueden volcar datos que no corresponde exponer por el panel.
REPORTES_PERMITIDOS = ("info", "storedir")


class CacheManagerError(Exception):
    """Error al consultar o interpretar el Cache Manager de Squid."""


def _puerto_actual(db: Session) -> str:
    setting = db.query(SquidSetting).filter(SquidSetting.key == "http_port").first()
    puerto = str(setting.value).strip() if setting else ""
    if not puerto.isdigit():
        raise CacheManagerError("No se encontró un http_port válido configurado.")
    return puerto


def _pedir_reporte(db: Session, reporte: str) -> str:
    if reporte not in REPORTES_PERMITIDOS:
        raise CacheManagerError(f"Reporte no permitido: {reporte!r}")
    puerto = _puerto_actual(db)
    ok, salida = get_runtime().cache_manager_report(reporte, puerto)
    if not ok:
        raise CacheManagerError(salida)
    return salida


# --- Parseo de "mgr:info" ----------------------------------------------

# Cada patron busca UNA linea del texto de Squid y captura los numeros que
# importan. re.search, no todo el texto de una: el formato de Squid no es
# estable columna a columna, pero estas frases si lo son entre versiones.
_PATRONES_INFO = {
    "version": re.compile(r"Squid Object Cache:\s*Version\s*(\S+)"),
    "uptime_segundos": re.compile(r"UP Time:\s*([\d.]+)\s*seconds"),
    "hits_peticiones_5min": re.compile(r"Hits as % of all requests:\s*5min:\s*([\d.-]+)%"),
    "hits_peticiones_60min": re.compile(r"Hits as % of all requests:.*60min:\s*([\d.-]+)%"),
    "hits_bytes_5min": re.compile(r"Hits as % of bytes sent:\s*5min:\s*([\d.-]+)%"),
    "hits_bytes_60min": re.compile(r"Hits as % of bytes sent:.*60min:\s*([\d.-]+)%"),
    "hits_memoria_5min": re.compile(r"Memory hits as % of hit requests:\s*5min:\s*([\d.-]+)%"),
    "hits_memoria_60min": re.compile(r"Memory hits as % of hit requests:.*60min:\s*([\d.-]+)%"),
    "hits_disco_5min": re.compile(r"Disk hits as % of hit requests:\s*5min:\s*([\d.-]+)%"),
    "hits_disco_60min": re.compile(r"Disk hits as % of hit requests:.*60min:\s*([\d.-]+)%"),
    "swap_size_kb": re.compile(r"Storage Swap size:\s*([\d.]+)\s*KB"),
    "swap_capacidad_pct": re.compile(r"Storage Swap capacity:\s*([\d.]+)%\s*used"),
    "mem_size_kb": re.compile(r"Storage Mem size:\s*([\d.]+)\s*KB"),
    "objeto_medio_kb": re.compile(r"Mean Object Size:\s*([\d.]+)\s*KB"),
    "ratio_fallos": re.compile(r"Request failure ratio:\s*([\d.]+)"),
    "clientes_activos": re.compile(r"Number of clients accessing cache:\s*(\d+)"),
    "peticiones_recibidas": re.compile(r"Number of HTTP requests received:\s*(\d+)"),
}


def _numero(texto: str, patron: re.Pattern) -> float | None:
    m = patron.search(texto)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def _parsear_info(texto: str) -> dict:
    datos: dict = {}
    for clave, patron in _PATRONES_INFO.items():
        valor = _numero(texto, patron)
        datos[clave] = valor
    m = _PATRONES_INFO["version"].search(texto)
    datos["version"] = m.group(1) if m else None
    return datos


# --- Parseo de "mgr:storedir" -------------------------------------------

_PATRONES_STOREDIR = {
    "entradas": re.compile(r"Store Entries\s*:\s*(\d+)"),
    "tamano_maximo_kb": re.compile(r"Maximum Swap Size\s*:\s*([\d.]+)\s*KB"),
    "tamano_actual_kb": re.compile(r"Current Store Swap Size:\s*([\d.]+)\s*KB"),
    "capacidad_pct": re.compile(r"Current Capacity\s*:\s*([\d.]+)%\s*used"),
}


def _parsear_storedir(texto: str) -> dict:
    return {clave: _numero(texto, patron) for clave, patron in _PATRONES_STOREDIR.items()}


def obtener_estadisticas_cache(db: Session) -> dict:
    """Estadisticas de cache listas para el frontend: info + storedir.

    Cualquiera de los dos reportes puede fallar sin tumbar al otro -Squid
    vivo pero con un reporte puntual fallando es mas probable que los dos a
    la vez, y no tiene sentido perder el que si funciono.
    """
    resultado: dict = {"info": None, "storedir": None, "errores": []}
    try:
        resultado["info"] = _parsear_info(_pedir_reporte(db, "info"))
    except CacheManagerError as e:
        resultado["errores"].append(f"info: {e}")
        logger.warning("No se pudo obtener mgr:info de Squid: %s", e)

    try:
        resultado["storedir"] = _parsear_storedir(_pedir_reporte(db, "storedir"))
    except CacheManagerError as e:
        resultado["errores"].append(f"storedir: {e}")
        logger.warning("No se pudo obtener mgr:storedir de Squid: %s", e)

    return resultado
