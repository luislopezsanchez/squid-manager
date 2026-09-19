#!/usr/bin/env python3
"""Helper de ACL externa para Squid: pertenencia a un grupo de LDAP/AD.

Protocolo de Squid (external_acl_type, sin concurrency):
  - Cada línea de entrada trae los campos declarados en el `external_acl_type`
    del squid.conf generado: %LOGIN (el usuario ya autenticado) + los
    parámetros fijos de la línea `acl ... external ldap_group_helper <grupo>
    <direct|nested>` que lo referencia -uno por cada grupo de AD configurado
    en el panel, todos comparten el mismo pool de este helper.
  - Responde "OK" o "ERR" por línea, sin más.
  - Proceso de larga duración (Squid arranca varias copias, `children=`):
    ninguna excepción debe escapar del bucle principal, o Squid lo marca
    caído y deja de resolver esa ACL para todo el mundo.

Nested vs. direct:
  - "direct": el usuario tiene que ser miembro DIRECTO del grupo (atributo
    `member` del grupo) -funciona contra cualquier directorio LDAPv3.
  - "nested": además cuenta la pertenencia a través de grupos anidados,
    usando la regla de coincidencia recursiva de Active Directory
    (1.2.840.113556.1.4.1941) -específica de AD, no funciona en OpenLDAP.

Usa la misma configuración de conexión que el helper de autenticación
(/etc/squid/ldap_helper.conf, escrito por el backend) -no una copia propia,
para no arriesgarse a que las dos queden desincronizadas.
"""

import sys
import syslog
from urllib.parse import unquote

LDAP_CONF_FILE = "/etc/squid/ldap_helper.conf"

# Grupo -> DN, resuelto una sola vez por proceso: el nombre de un grupo no
# cambia mientras el helper está vivo, y resolverlo de nuevo en cada
# petición duplicaría una búsqueda LDAP que no hace falta repetir.
_group_dn_cache: dict = {}


def _escapar_filtro_ldap(valor: str) -> str:
    """Escapa un valor para insertarlo en un filtro LDAP (RFC 4515). Misma
    lógica que auth_helper.py y backend/app/routes/ldap.py -ver el
    comentario de ese archivo sobre por qué hay varias copias en vez de
    una sola importada: este script corre en el runtime de Squid, fuera
    del paquete del backend."""
    return (
        valor.replace("\\", "\\5c").replace("*", "\\2a")
        .replace("(", "\\28").replace(")", "\\29").replace("\x00", "\\00")
    )


def log_error(message):
    try:
        syslog.syslog(syslog.LOG_ERR, f"squidmanager_ldap_group_helper: {message}")
    except Exception:
        pass
    try:
        sys.stderr.write(f"squidmanager_ldap_group_helper: {message}\n")
        sys.stderr.flush()
    except Exception:
        pass


def load_ldap_config():
    """Lee la configuración LDAP (key=value) desde el archivo."""
    config = {}
    try:
        with open(LDAP_CONF_FILE) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                config[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    except Exception as e:
        log_error(f"error leyendo {LDAP_CONF_FILE}: {e}")
    return config


def _connect(config):
    from ldap3 import Server, Connection

    server = Server(config.get("server_url", ""), connect_timeout=5)
    return Connection(
        server, user=config.get("bind_dn", ""), password=config.get("bind_password", ""),
        auto_bind=True, receive_timeout=5,
    )


def _resolve_group_dn(conn, search_base, group_name):
    if group_name in _group_dn_cache:
        return _group_dn_cache[group_name]
    from ldap3 import SUBTREE

    safe = _escapar_filtro_ldap(group_name)
    conn.search(
        search_base=search_base, search_filter=f"(|(cn={safe})(sAMAccountName={safe}))",
        search_scope=SUBTREE, attributes=["1.1"],
    )
    dn = conn.entries[0].entry_dn if conn.entries else None
    _group_dn_cache[group_name] = dn
    return dn


def check_group(username: str, group_name: str, mode: str) -> bool:
    if not username or not group_name:
        return False
    config = load_ldap_config()
    if not config.get("server_url") or not config.get("bind_dn"):
        return False

    try:
        from ldap3 import SUBTREE, BASE
    except ImportError:
        log_error("el módulo ldap3 no está instalado")
        return False

    search_base = config.get("search_base", "")
    user_filter_tpl = config.get("user_filter", "(sAMAccountName=%s)")

    conn = None
    try:
        conn = _connect(config)
    except Exception as e:
        log_error(f"no se pudo conectar a LDAP: {e}")
        return False

    try:
        group_dn = _resolve_group_dn(conn, search_base, group_name)
        if not group_dn:
            return False

        safe_user = _escapar_filtro_ldap(username)
        user_filter = (
            user_filter_tpl.replace("%s", safe_user) if "%s" in user_filter_tpl else user_filter_tpl
        )

        if mode == "nested":
            # Regla de coincidencia recursiva de Active Directory: cuenta
            # la pertenencia directa Y a través de grupos anidados.
            safe_group_dn = _escapar_filtro_ldap(group_dn)
            member_filter = f"(&{user_filter}(memberOf:1.2.840.113556.1.4.1941:={safe_group_dn}))"
            conn.search(search_base=search_base, search_filter=member_filter,
                        search_scope=SUBTREE, attributes=["1.1"])
            return bool(conn.entries)

        # "direct": resolver el DN del usuario y comprobar que aparece en
        # el atributo `member` del propio grupo -funciona contra
        # cualquier directorio LDAPv3, no solo Active Directory.
        conn.search(search_base=search_base, search_filter=user_filter,
                    search_scope=SUBTREE, attributes=["1.1"])
        if not conn.entries:
            return False
        user_dn = conn.entries[0].entry_dn
        safe_user_dn = _escapar_filtro_ldap(user_dn)
        conn.search(search_base=group_dn, search_filter=f"(member={safe_user_dn})",
                    search_scope=BASE, attributes=["1.1"])
        return bool(conn.entries)
    except Exception as e:
        log_error(f"error comprobando la pertenencia de '{username}' a '{group_name}': {e}")
        return False
    finally:
        if conn is not None:
            try:
                conn.unbind()
            except Exception:
                pass


def handle(line: str) -> str:
    parts = line.split()
    if len(parts) < 2:
        return "ERR"
    username = unquote(parts[0])
    group_name = unquote(parts[1])
    mode = unquote(parts[2]) if len(parts) > 2 else "direct"
    return "OK" if check_group(username, group_name, mode) else "ERR"


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            response = handle(line)
        except Exception as e:
            # Un fallo inesperado deniega esta petición puntual, pero el
            # helper sigue vivo: si muriera, Squid dejaría de resolver
            # esta ACL para todo el mundo.
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
