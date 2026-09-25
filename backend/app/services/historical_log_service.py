"""Servicio de logs históricos: lectura bajo demanda de los meses ya
consolidados en frío (/var/log/squid/archive/historical/AAAA/MM/).

Deliberadamente separado de log_service.py y sin ningún estado ni caché
compartidos con él: ese servicio es el que consultan el dashboard, las
métricas y el visor en vivo cada pocos segundos, y no debe competir por I/O
ni por CPU con nada que toque archivos históricos, potencialmente de cientos
de MB comprimidos. Aquí no hay caché con TTL porque no hace falta: un mes
cerrado no cambia nunca, así que su index.json (generado una sola vez por
build_monthly_index.py al consolidar) es la fuente de las estadísticas
-nunca se recorre el .gz completo solo para mostrar un resumen-. El .gz en sí
solo se abre cuando el admin pide ver o exportar las líneas de un mes
concreto, bajo demanda, nunca en un polling.
"""

import gzip
import json
import logging
import subprocess
from pathlib import Path

from app.services.log_service import parse_line
from app.services.runtime.native_runtime import _sudo_prefix


def _matches(entry: dict, user, status, domain, ip, denied_only) -> bool:
    """Mismo criterio de filtrado que log_service._matches().

    Reimplementado en vez de importar el privado de log_service: ese difiere
    a propósito la semántica de filtros de este módulo si algún día hiciera
    falta, sin arrastrar un acoplamiento entre "vivo" e "histórico" que este
    archivo entero existe para evitar.
    """
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

logger = logging.getLogger(__name__)

HISTORICAL_DIR = Path("/var/log/squid/archive/historical")

# Tope dursn la misma lógica que log_service.MAX_SCAN_LINES: un mes entero
# puede tener millones de líneas, y esto es bajo demanda, no polling, pero
# sigue sin tener sentido devolver un CSV de 5 millones de filas al panel.
MAX_EXPORT_LINES = 500_000


def list_months() -> list[dict]:
    """Lista los meses con log consolidado, más nuevo primero.

    Lee solo los index.json (livianos, unos KB cada uno): nunca abre los
    .gz para armar este listado.
    """
    meses = []
    if not HISTORICAL_DIR.is_dir():
        return meses

    for year_dir in HISTORICAL_DIR.iterdir():
        if not year_dir.is_dir() or not year_dir.name.isdigit():
            continue
        for month_dir in year_dir.iterdir():
            if not month_dir.is_dir() or not month_dir.name.isdigit():
                continue
            index_path = month_dir / "index.json"
            gz_path = month_dir / f"access-{year_dir.name}{month_dir.name}.log.gz"
            if index_path.exists():
                try:
                    meses.append(json.loads(index_path.read_text(encoding="utf-8")))
                    continue
                except (json.JSONDecodeError, OSError) as e:
                    logger.warning(f"index.json ilegible en {index_path}: {e}")
            # Sin índice (instalación vieja sin actualizar, o el indexador
            # falló al consolidar ese mes en particular): igual se informa
            # que el mes existe, con lo mínimo que se puede saber sin abrirlo.
            if gz_path.exists():
                meses.append({
                    "year": int(year_dir.name),
                    "month": int(month_dir.name),
                    "file": gz_path.name,
                    "size_bytes": gz_path.stat().st_size,
                    "sin_indice": True,
                })

    meses.sort(key=lambda m: (m["year"], m["month"]), reverse=True)
    return meses


def _mes_dir(year: int, month: int) -> Path:
    return HISTORICAL_DIR / str(year) / f"{month:02d}"


# Script privilegiado que hace el borrado de verdad (ver ese archivo): este
# backend corre sin permiso de escritura en /var/log/squid a propósito (ver
# backend/entrypoint.sh), así que un shutil.rmtree() directo acá fallaría con
# PermissionError contra una instalación real -no es un detalle de
# configuración de un entorno en particular, es la misma razón por la que
# reconfigurar/reiniciar Squid tampoco se hace directo, más abajo en
# runtime/native_runtime.py.
_SCRIPT_BORRADO = "/usr/local/lib/squidmanager/delete_historical_month.sh"


def delete_month(year: int, month: int) -> bool:
    """Borra un mes histórico entero (el .gz consolidado, su index.json y el
    directorio AAAA/MM) desde el panel. False si ese mes no existe.

    El borrado en sí -incluido el criterio de retirar también el directorio
    AAAA si se queda sin meses, igual que la purga por retención de
    consolidate-monthly-logs.sh- vive en _SCRIPT_BORRADO, no acá: ver el
    comentario de arriba sobre por qué este proceso no puede escribir ahí
    directamente.
    """
    if not _mes_dir(year, month).is_dir():
        return False

    try:
        resultado = subprocess.run(
            _sudo_prefix() + [_SCRIPT_BORRADO, str(year), f"{month:02d}"],
            capture_output=True, text=True, timeout=30,
        )
    except FileNotFoundError:
        # sudo no está instalado (imagen mínima de Docker, por ejemplo): un
        # mensaje claro de "esto no está soportado en este modo todavía" es
        # mejor que dejar subir un FileNotFoundError crudo hasta el panel.
        raise RuntimeError(
            "El borrado de logs históricos no está disponible en esta instalación "
            "(falta sudo o el script privilegiado -ver instalación nativa vs. Docker)."
        )
    if resultado.returncode != 0:
        raise RuntimeError(
            f"No se pudo borrar el log histórico de {year}-{month:02d}: {resultado.stderr.strip()}"
        )
    return True


def get_month_index(year: int, month: int) -> dict | None:
    """El index.json de un mes concreto, o None si no existe."""
    index_path = _mes_dir(year, month) / "index.json"
    if not index_path.exists():
        return None
    try:
        return json.loads(index_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"index.json ilegible en {index_path}: {e}")
        return None


def _gz_de(year: int, month: int) -> Path | None:
    gz = _mes_dir(year, month) / f"access-{year}{month:02d}.log.gz"
    return gz if gz.exists() else None


def get_historical_entries(
    year: int,
    month: int,
    limit: int = 100,
    offset: int = 0,
    user: str | None = None,
    status: int | None = None,
    domain: str | None = None,
    ip: str | None = None,
    denied_only: bool = False,
) -> dict:
    """Lee y filtra las líneas de un mes histórico, en streaming.

    A diferencia de log_service.get_logs() (que lee desde el final porque el
    caso normal es "lo más reciente"), aquí se lee desde el principio del
    mes: no hay "más reciente" dentro de un archivo cerrado, y paginar hacia
    adelante es lo que espera alguien revisando un mes completo.
    """
    gz = _gz_de(year, month)
    if gz is None:
        return {"entries": [], "total_matched": 0, "has_more": False}

    coincidencias = []
    total_matched = 0
    con_offset_aplicado = 0

    with gzip.open(gz, "rt", encoding="utf-8", errors="replace") as f:
        for linea in f:
            entry = parse_line(linea)
            if entry is None:
                continue
            if not _matches(entry, user, status, domain, ip, denied_only):
                continue
            total_matched += 1
            if con_offset_aplicado < offset:
                con_offset_aplicado += 1
                continue
            if len(coincidencias) < limit:
                coincidencias.append(entry)
            # Se sigue contando total_matched incluso pasado el límite, para
            # que el panel sepa cuántas hay en total y arme la paginación.

    return {
        "entries": coincidencias,
        "total_matched": total_matched,
        "has_more": offset + len(coincidencias) < total_matched,
    }


def iter_historical_lines(year: int, month: int, filtros: dict, max_lines: int = MAX_EXPORT_LINES):
    """Generador de entradas ya parseadas y filtradas, para exportar en streaming.

    Separado de get_historical_entries() porque exportar no pagina: recorre
    todo el mes (hasta max_lines) y va entregando de a una, sin acumular todo
    en memoria antes de empezar a responder.
    """
    gz = _gz_de(year, month)
    if gz is None:
        return

    emitidas = 0
    with gzip.open(gz, "rt", encoding="utf-8", errors="replace") as f:
        for linea in f:
            if emitidas >= max_lines:
                logger.warning(
                    f"Exportación de {year}-{month:02d} cortada en {max_lines} líneas"
                )
                break
            entry = parse_line(linea)
            if entry is None:
                continue
            if not _matches(entry, filtros.get("user"), filtros.get("status"),
                             filtros.get("domain"), filtros.get("ip"),
                             filtros.get("denied_only", False)):
                continue
            emitidas += 1
            yield entry
