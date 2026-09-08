#!/usr/bin/env python3
"""Genera el index.json de un access.log mensual ya consolidado.

Standalone a propósito, sin importar nada del backend: este script corre
dentro del contenedor/servicio de Squid (via cron.monthly), que no tiene el
entorno virtual del backend ni sus dependencias. Reutiliza el mismo patrón de
parseo que backend/app/services/log_service.py (LINE_PATTERN) para que las
cifras del índice coincidan con lo que el panel mostraría si leyera esas
líneas -si un campo cambia de formato en el access.log real, hay que
actualizar los dos sitios a la vez.

El índice es la base de datos "de pobre" para el histórico: un resumen
precalculado que se lee entero y no cambia nunca (el mes ya cerró), así que
no hace falta ninguna base de datos ni reindexado para mostrar estadísticas
de un mes pasado -alcanza con leer este JSON.

Uso: build_monthly_index.py <access.log.gz> <year> <month> <output.json>
"""

import gzip
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# Mismo patrón que backend/app/services/log_service.py:LINE_PATTERN.
# Si ese cambia, este debe cambiar igual.
LINE_PATTERN = re.compile(
    r'^(\d+\.\d+)\s+'           # timestamp
    r'(\d+)\s+'                 # elapsed (ms)
    r'(\S+)\s+'                 # client IP
    r'(\S+)/(\d+)\s+'           # action/status
    r'(\d+)\s+'                 # bytes
    r'(\S+)\s+'                 # method
    r'(\S+)\s+'                 # url
    r'(\S+)\s+'                 # user
    r'(\S+)\s+'                 # hierarchy
    r'(\S+)'                    # content type
)

# Cuántos dominios/usuarios distintos guardar en el ranking. El resto de la
# cardinalidad (unique_domains/unique_users) sí se cuenta completa.
TOP_N = 20


def dominio_de(url: str) -> str:
    """Misma lógica que log_service.parse_line() para el campo 'domain'."""
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
    return domain


def construir_indice(gz_path: Path, year: int, month: int) -> dict:
    total_lines = 0
    total_bytes = 0
    denied_count = 0
    primer_ts = None
    ultimo_ts = None
    usuarios = Counter()
    dominios = Counter()
    estados = Counter()

    with gzip.open(gz_path, "rt", encoding="utf-8", errors="replace") as f:
        for linea in f:
            m = LINE_PATTERN.match(linea.strip())
            if not m:
                continue
            total_lines += 1

            ts = float(m.group(1))
            if primer_ts is None or ts < primer_ts:
                primer_ts = ts
            if ultimo_ts is None or ts > ultimo_ts:
                ultimo_ts = ts

            action = m.group(4)
            status = int(m.group(5))
            estados[str(status)] += 1

            nbytes = int(m.group(6))
            total_bytes += nbytes

            url = m.group(8)
            dominios[dominio_de(url)] += 1

            user = m.group(9)
            if user != "-":
                usuarios[user] += 1

            if status in (401, 403, 407) or "DENIED" in action:
                denied_count += 1

    def fmt(ts):
        if ts is None:
            return None
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    return {
        "year": year,
        "month": month,
        "file": gz_path.name,
        "size_bytes": gz_path.stat().st_size,
        "total_lines": total_lines,
        "date_range": {"first": fmt(primer_ts), "last": fmt(ultimo_ts)},
        "unique_users": len(usuarios),
        "unique_domains": len(dominios),
        "status_codes": dict(estados),
        "top_domains": [{"domain": d, "count": c} for d, c in dominios.most_common(TOP_N)],
        "top_users": [{"user": u, "count": c} for u, c in usuarios.most_common(TOP_N)],
        "total_bytes": total_bytes,
        "denied_count": denied_count,
        "generated_at": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
    }


def main():
    if len(sys.argv) != 5:
        print("Uso: build_monthly_index.py <access.log.gz> <year> <month> <output.json>", file=sys.stderr)
        sys.exit(1)

    gz_path = Path(sys.argv[1])
    year = int(sys.argv[2])
    month = int(sys.argv[3])
    out_path = Path(sys.argv[4])

    if not gz_path.exists():
        print(f"No existe {gz_path}", file=sys.stderr)
        sys.exit(1)

    indice = construir_indice(gz_path, year, month)
    out_path.write_text(json.dumps(indice, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
