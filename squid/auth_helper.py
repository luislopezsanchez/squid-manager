#!/usr/bin/env python3
"""Helper de autenticación para Squid: combina usuarios locales y LDAP.

Protocolo de Squid (auth básica):
  - Squid escribe "username password\\n" en stdin
  - El helper responde "OK\\n" o "ERR\\n" en stdout
  - Es un proceso de larga duración (un helper atiende muchas peticiones)

Lógica:
  1. Verifica contra el htpasswd LOCAL (squid_passwd).
  2. Si no está local, verifica la ALLOW-LIST de usuarios LDAP y, si el usuario
     está autorizado, hace bind contra LDAP.
  3. Si ninguna vía funciona, responde ERR.

Archivos de configuración (escritos por el backend en el volumen compartido):
  - /etc/squid/squid_passwd       : htpasswd local (bcrypt)
  - /etc/squid/ldap_allowlist     : usuarios LDAP autorizados (allow-list estricto)
  - /etc/squid/ldap_helper.conf   : config de conexión LDAP (key=value)
"""

import sys
import os

HTPASSWD_FILE = "/etc/squid/squid_passwd"
ALLOWLIST_FILE = "/etc/squid/ldap_allowlist"
LDAP_CONF_FILE = "/etc/squid/ldap_helper.conf"


def check_local(username, password):
    """Verifica usuario/contraseña contra el htpasswd local (bcrypt)."""
    try:
        import bcrypt
    except ImportError:
        return False
    try:
        with open(HTPASSWD_FILE) as f:
            for line in f:
                line = line.strip()
                if not line or ":" not in line:
                    continue
                u, h = line.split(":", 1)
                if u != username:
                    continue
                # htpasswd genera $2y$; bcrypt de Python espera $2b$ (mismo algoritmo)
                h_bcrypt = h.replace("$2y$", "$2b$")
                try:
                    return bcrypt.checkpw(password.encode("utf-8"), h_bcrypt.encode("utf-8"))
                except Exception:
                    return False
    except FileNotFoundError:
        pass
    return False


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
    return config


def is_allowed(username):
    """Verifica si el usuario LDAP está en la allow-list (estricto)."""
    try:
        with open(ALLOWLIST_FILE) as f:
            allowed = {l.strip() for l in f if l.strip()}
            return username in allowed
    except FileNotFoundError:
        return False


def check_ldap(username, password):
    """Autentica contra LDAP/AD usando la config del archivo."""
    if not is_allowed(username):
        return False
    config = load_ldap_config()
    if not config.get("server_url") or not config.get("bind_dn"):
        return False

    try:
        from ldap3 import Server, Connection, SUBTREE
    except ImportError:
        return False

    server_url = config.get("server_url")
    bind_dn = config.get("bind_dn")
    bind_password = config.get("bind_password", "")
    search_base = config.get("search_base", "")
    user_filter = config.get("user_filter", "(sAMAccountName=%s)")

    try:
        server = Server(server_url, connect_timeout=5)
        conn = Connection(server, user=bind_dn, password=bind_password,
                          auto_bind=True, receive_timeout=5)
    except Exception:
        return False

    # Construir filtro sustituyendo %s por el username
    if "%s" in user_filter:
        search_filter = user_filter.replace("%s", username)
    else:
        search_filter = user_filter

    try:
        conn.search(search_base=search_base, search_filter=search_filter,
                    search_scope=SUBTREE, attributes=["1.1"])
        if not conn.entries:
            conn.unbind()
            return False
        user_dn = conn.entries[0].entry_dn
    except Exception:
        conn.unbind()
        return False

    # Bind como el usuario
    try:
        user_conn = Connection(server, user=user_dn, password=password,
                               auto_bind=True, receive_timeout=5)
        ok = user_conn.bound
        user_conn.unbind()
    except Exception:
        ok = False
    conn.unbind()
    return ok


def main():
    # Bucle principal de Squid auth
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        username = parts[0] if parts else ""
        password = parts[1] if len(parts) > 1 else ""

        if not username:
            sys.stdout.write("ERR\n")
            sys.stdout.flush()
            continue

        # 1. Local primero
        if check_local(username, password):
            sys.stdout.write("OK\n")
            sys.stdout.flush()
            continue

        # 2. LDAP (solo si está en allow-list)
        if check_ldap(username, password):
            sys.stdout.write("OK\n")
            sys.stdout.flush()
            continue

        sys.stdout.write("ERR\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
