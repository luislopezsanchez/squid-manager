#!/usr/bin/env python3
"""Helper de ACL externa para Squid: pertenencia a una lista de bloqueo de
dominios (external_acl_type, ver config_generator.py y domain_index_service.py
en el backend -este script corre AFUERA de ese paquete, con el python3 del
sistema, igual que ldap_group_helper.py-).

Por qué existe: una ACL 'file' de dominios (HaGeZi, una blocklist subida a
mano) puede tener millones de líneas. Declararla como
`acl nombre dstdomain "/archivo.txt"` hace que Squid la cargue ENTERA en
memoria en cada parseo de squid.conf -confirmado en vivo, 2026-09-27: con
una lista de ~5.9M dominios en uso real, `squid -k parse` tardaba más de un
minuto solo por eso, la usara o no ninguna regla-. Este helper reemplaza esa
carga en memoria por una consulta indexada (SQLite) por request: Squid ya
no necesita saber cuántos dominios tiene la lista para reconfigurar.

Protocolo (external_acl_type, sin concurrency):
  - Cada línea trae el dominio -%>rd para HTTP/CONNECT, o %ssl::>sni para el
    peek pre-descifrado de HTTPS, según cuál de las DOS declaraciones lo
    invoque (ver squid.conf.j2: squidmanager_domain_helper /
    squidmanager_domain_helper_sni comparten este mismo script)- seguido
    del nombre de categoría (%DATA, la ACL lo pasa como argumento fijo:
    `acl nombre external squidmanager_domain_helper <categoria>`).
  - Responde OK (el dominio SÍ está en esa lista) o ERR (no está).
  - Proceso de larga duración (children-max=): ninguna excepción debe
    escapar del bucle principal, o Squid lo marca caído y deja de resolver
    esa ACL para todo el mundo.

Semántica de match, verificada en vivo contra Squid 6.14 (no supuesta): una
entrada sin punto inicial ("foo.com") es match EXACTO únicamente; con punto
inicial (".foo.com") hace match del dominio Y de cualquier subdominio -el
índice ya separa ambos casos, ver domain_index_service.index_category().
"""

import sqlite3
import sys
import syslog
from urllib.parse import unquote

DB_PATH = "/etc/squid/acl_lists/domain_index.db"

_conn: sqlite3.Connection | None = None


def log_error(message):
    try:
        syslog.syslog(syslog.LOG_ERR, f"squidmanager_domain_helper: {message}")
    except Exception:
        pass
    try:
        sys.stderr.write(f"squidmanager_domain_helper: {message}\n")
        sys.stderr.flush()
    except Exception:
        pass


def _get_conn() -> sqlite3.Connection:
    """Una sola conexión para toda la vida del proceso.

    Modo rollback-journal (el default de SQLite, NO WAL -ver el docstring
    de domain_index_service._connect() para el porqué exacto: WAL exige que
    hasta una conexión de solo lectura pueda escribir ficheros auxiliares
    en /etc/squid/acl_lists/, que este proceso ('proxy') no puede-). Con el
    default, releer el archivo en cada consulta ya alcanza para ver los
    commits del backend, sin reabrir la conexión.

    busy_timeout generoso: reindexar una categoría grande (blackweb, ~5.9M
    filas) toma un lock exclusivo sobre el archivo entero mientras dura
    -~19s medido en vivo-, y una consulta que caiga justo en esa ventana
    tiene que esperar, no fallar."""
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH, timeout=30)
        _conn.execute("PRAGMA busy_timeout=30000")
    return _conn


def _ancestros(dominio: str) -> list[str]:
    """['a.b.example.com', 'b.example.com', 'example.com', 'com']"""
    partes = dominio.split(".")
    return [".".join(partes[i:]) for i in range(len(partes))]


def domain_blocked(category: str, dominio: str, _reintento: bool = False) -> bool:
    dominio = dominio.strip().lower().rstrip(".")
    if not dominio or not category:
        return False

    try:
        conn = _get_conn()
        row = conn.execute(
            "SELECT 1 FROM domain_entries WHERE category=? AND exact=1 AND domain=? LIMIT 1",
            (category, dominio),
        ).fetchone()
        if row:
            return True

        candidatos = _ancestros(dominio)
        placeholders = ",".join("?" for _ in candidatos)
        row = conn.execute(
            f"SELECT 1 FROM domain_entries WHERE category=? AND exact=0 AND domain IN ({placeholders}) LIMIT 1",
            (category, *candidatos),
        ).fetchone()
        return bool(row)
    except sqlite3.Error as e:
        # Si el índice no existe todavía o está corrupto, no se puede saber
        # si el dominio está bloqueado: se deja pasar (ERR = no coincide),
        # nunca se bloquea todo el tráfico por un problema de este helper.
        # El error queda en el log para que se note -no en silencio-.
        log_error(f"error consultando el índice para '{category}': {e}")
        global _conn
        _conn = None  # por si la conexión quedó en mal estado
        if not _reintento:
            return domain_blocked(category, dominio, True)  # un reintento con conexión nueva antes de rendirse
        return False


def handle(line: str) -> str:
    parts = line.split()
    if len(parts) < 2:
        return "ERR"
    dominio = unquote(parts[0])
    category = unquote(parts[1])
    # message= queda disponible como %o en la página de error personalizada
    # (deny_info, ver config_generator.py) -así el aviso que ve el usuario
    # puede decir "Motivo: hagezi_gambling" en vez de un texto genérico,
    # para el caso más común de bloqueo (una lista de dominios).
    if domain_blocked(category, dominio):
        return f'OK message="{category}"'
    return "ERR"


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            response = handle(line)
        except Exception as e:
            # Un fallo inesperado deniega esta consulta puntual (no
            # bloquea), pero el helper sigue vivo: si muriera, Squid
            # dejaría de resolver esta ACL para todo el mundo.
            log_error(f"error inesperado procesando una petición: {e}")
            response = "ERR"

        sys.stdout.write(response + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        log_error(f"el helper terminó por un error: {e}")
        sys.exit(1)
