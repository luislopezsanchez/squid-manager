"""Índice SQLite de dominios para el helper externo de listas de bloqueo.

Por qué existe: hasta ahora, una ACL 'file' de tipo dstdomain (una lista de
bloqueo de dominios, potencialmente de millones de líneas -HaGeZi, una
blocklist subida a mano) se declaraba en squid.conf como
`acl nombre dstdomain "/ruta/al/archivo.txt"`, y Squid la carga ENTERA en
memoria en un árbol splay CADA VEZ que parsea la configuración -en cada
"Aplicar cambios" (reconfigure) y en cada purga de credenciales (restart)-,
la use o no ninguna regla todavía. Encontrado en vivo, 2026-09-27: con una
lista de ~5.9M dominios en uso real por una regla, `squid -k parse` tardaba
más de un minuto solo por esa lista.

La solución (mismo patrón que ya usa `ldap_group_helper.py` para grupos de
LDAP): sacar el contenido de squid.conf del todo. Este módulo mantiene un
índice SQLite en disco; `squid/domain_block_helper.py` (un external_acl_type,
ver config_generator.py) lo consulta por request en vez de que Squid cargue
nada en su propia memoria. Reconfigurar deja de costar nada proporcional al
tamaño de la lista, la use o no una regla, y sin importar cuánto crezca.

Semántica de match (verificada en vivo contra Squid 6.14, no supuesta): una
entrada SIN punto inicial ("foo.com") es una ACL nativa dstdomain de match
EXACTO; con punto inicial (".foo.com") hace match del dominio y de
CUALQUIER subdominio. Este índice replica ambos casos exactamente.
"""

import hashlib
import logging
import os
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

# Mismo directorio que ACL_LISTS_DIR en squid_service.py (no se importa desde
# ahí para no crear un ciclo: squid_service ya va a importar este módulo).
DB_PATH = Path("/etc/squid/acl_lists/domain_index.db")


def _proxy_ids() -> tuple[int, int]:
    """Duplicado deliberado de squid_service._proxy_ids(): mismo criterio,
    ver ese docstring. Un módulo de infraestructura de bajo nivel como este
    no debería depender de squid_service ni al revés."""
    try:
        import pwd

        entrada = pwd.getpwnam("proxy")
        return entrada.pw_uid, entrada.pw_gid
    except Exception:
        return 13, 13


def _connect() -> sqlite3.Connection:
    """Modo rollback-journal (el default de SQLite), NO WAL, a propósito:
    WAL exige que CUALQUIER conexión -incluida una de solo lectura, como la
    de squid/domain_block_helper.py- pueda escribir los ficheros auxiliares
    `-wal`/`-shm` en este mismo directorio. Bug real, visto en vivo,
    2026-09-27: el helper (usuario 'proxy', sin permiso de escritura sobre
    /etc/squid/acl_lists/, que es 2755 -de grupo 'proxy' pero solo
    lectura/ejecución-) fallaba con "attempt to write a readonly database"
    en CADA consulta, aunque nunca ejecute un solo INSERT/UPDATE/DELETE.
    Con el modo por defecto, un lector puro solo necesita permiso de
    LECTURA sobre el propio archivo .db -mismo modelo que ya usa cualquier
    otro fichero que Squid solo lee (squid_passwd, ldap_helper.conf, un
    .txt de ACL)-, sin tocar el directorio para nada. El costo real: quien
    escribe (reindexar una categoría) toma un lock exclusivo sobre TODO el
    archivo mientras dura -no solo la categoría que cambia-, así que una
    consulta que llegue justo en ese momento espera en vez de fallar
    (busy_timeout generoso, más abajo: reindexar blackweb entero, ~5.9M
    filas, midió ~19s en la prueba en vivo). Aceptable: reindexar solo pasa
    cuando cambia el contenido de verdad (una sync diaria, una carga
    manual), no en cada aplicar-cambios.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    nuevo = not DB_PATH.exists()
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS domain_entries ("
        " category TEXT NOT NULL,"
        " domain TEXT NOT NULL,"
        " exact INTEGER NOT NULL,"
        " PRIMARY KEY (category, exact, domain)"
        ") WITHOUT ROWID"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS category_meta ("
        " category TEXT PRIMARY KEY,"
        " content_hash TEXT NOT NULL"
        ")"
    )
    if nuevo:
        # Legible por Squid (usuario 'proxy'), escribible solo por quien
        # corre este backend -mismo criterio que el resto de /etc/squid,
        # ver _write_private en squid_service.py.
        try:
            os.chmod(DB_PATH, 0o640)
            if getattr(os, "geteuid", lambda: 1)() == 0:
                uid, gid = _proxy_ids()
                os.chown(DB_PATH, uid, gid)
        except OSError as e:
            logger.warning(f"No se pudieron ajustar permisos de {DB_PATH}: {e}")
    return conn


def content_hash(dominios: list[str]) -> str:
    """Mismo criterio que hash_domain_list en squid_service.py (formato
    idéntico: una línea por dominio), para poder comparar directo contra
    Acl.content_hash y no reindexar si el contenido no cambió de verdad."""
    h = hashlib.sha256()
    for linea in dominios:
        h.update(linea.encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def categoria_indexada_al_dia(category: str, hash_esperado: str) -> bool:
    """True si el índice ya refleja este contenido -evita reconstruir
    millones de filas en cada apply cuando nada cambió de verdad."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT content_hash FROM category_meta WHERE category=?", (category,)
        ).fetchone()
        return bool(row) and row[0] == hash_esperado
    finally:
        conn.close()


def index_category(category: str, dominios: list[str], hash_nuevo: str) -> int:
    """(Re)construye las filas de esta categoría a partir de la lista ya
    normalizada (mismo formato que escribe write_acl_list_file). Reemplaza
    todo lo que hubiera antes para esa categoría en una sola transacción.

    Devuelve la cantidad de filas insertadas.
    """
    conn = _connect()
    try:
        filas = []
        for cruda in dominios:
            d = cruda.strip().lower()
            if not d:
                continue
            if d.startswith("."):
                filas.append((category, d[1:], 0))
            else:
                filas.append((category, d, 1))

        with conn:
            conn.execute("DELETE FROM domain_entries WHERE category=?", (category,))
            conn.executemany(
                "INSERT OR IGNORE INTO domain_entries (category, domain, exact) VALUES (?, ?, ?)",
                filas,
            )
            conn.execute(
                "INSERT INTO category_meta (category, content_hash) VALUES (?, ?) "
                "ON CONFLICT(category) DO UPDATE SET content_hash=excluded.content_hash",
                (category, hash_nuevo),
            )
        logger.info(f"Índice de dominios '{category}' reconstruido: {len(filas)} entradas")
        return len(filas)
    finally:
        conn.close()


def remove_category(category: str) -> None:
    """Borra una categoría del índice -para cuando la ACL que la respalda
    se borra o cambia de tipo/source, así el helper no sigue contestando
    OK para un nombre que ya no existe en el panel."""
    conn = _connect()
    try:
        with conn:
            conn.execute("DELETE FROM domain_entries WHERE category=?", (category,))
            conn.execute("DELETE FROM category_meta WHERE category=?", (category,))
    finally:
        conn.close()


def _ancestros(dominio: str) -> list[str]:
    """['a.b.example.com', 'b.example.com', 'example.com', 'com']"""
    partes = dominio.split(".")
    return [".".join(partes[i:]) for i in range(len(partes))]


def matches(conn: sqlite3.Connection, category: str, dominio: str) -> bool:
    """Consulta de lectura equivalente a la que hace squid/domain_block_helper.py
    -duplicada allá a propósito, ver su docstring-, expuesta acá para poder
    probar el índice sin pasar por el protocolo stdin/stdout del helper."""
    dominio = dominio.strip().lower().rstrip(".")
    if not dominio or not category:
        return False

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


def categorias_indexadas() -> set[str]:
    conn = _connect()
    try:
        return {r[0] for r in conn.execute("SELECT category FROM category_meta").fetchall()}
    finally:
        conn.close()
