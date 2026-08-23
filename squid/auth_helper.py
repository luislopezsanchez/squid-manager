#!/usr/bin/env python3
"""Helper de autenticación para Squid: combina usuarios locales y LDAP.

Protocolo de Squid (auth básica):
  - Squid escribe "username password\\n" en stdin, con los valores escapados
    en %XX cuando contienen espacios o caracteres especiales.
  - El helper responde "OK\\n" o "ERR\\n" en stdout
  - Es un proceso de larga duración (un helper atiende muchas peticiones)

Lógica:
  1. Verifica contra el htpasswd LOCAL (squid_passwd).
  2. Si no está local, verifica la ALLOW-LIST de usuarios LDAP y, si el usuario
     está autorizado, hace bind contra LDAP.
  3. Si ninguna vía funciona, responde ERR.

Ninguna excepción debe escapar del bucle principal: si el proceso muere, Squid
marca el helper como caído y deja de autenticar a todo el mundo.

Archivos de configuración (escritos por el backend en el volumen compartido):
  - /etc/squid/squid_passwd       : htpasswd local (bcrypt)
  - /etc/squid/ldap_allowlist     : usuarios LDAP autorizados (allow-list estricto)
  - /etc/squid/ldap_helper.conf   : config de conexión LDAP (key=value)
"""

import sys
import syslog
from urllib.parse import unquote

HTPASSWD_FILE = "/etc/squid/squid_passwd"
ALLOWLIST_FILE = "/etc/squid/ldap_allowlist"
LDAP_CONF_FILE = "/etc/squid/ldap_helper.conf"


def log_error(message):
    """Deja constancia del fallo sin escribir en stdout, que es el canal de Squid."""
    try:
        syslog.syslog(syslog.LOG_ERR, f"squidmanager_auth_helper: {message}")
    except Exception:
        pass
    try:
        sys.stderr.write(f"squidmanager_auth_helper: {message}\n")
        sys.stderr.flush()
    except Exception:
        pass


def check_local(username, password):
    """Verifica usuario/contraseña contra el htpasswd local (bcrypt)."""
    try:
        import bcrypt
    except ImportError:
        log_error("el módulo bcrypt no está instalado")
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
                h_bcrypt = h.replace("$2y$", "$2b$", 1)
                try:
                    return bcrypt.checkpw(password.encode("utf-8"), h_bcrypt.encode("utf-8"))
                except Exception:
                    return False
    except FileNotFoundError:
        pass
    except Exception as e:
        log_error(f"error leyendo {HTPASSWD_FILE}: {e}")
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
    except Exception as e:
        log_error(f"error leyendo {LDAP_CONF_FILE}: {e}")
    return config


def is_allowed(username):
    """Verifica si el usuario LDAP está en la allow-list (estricto)."""
    try:
        with open(ALLOWLIST_FILE) as f:
            allowed = {l.strip() for l in f if l.strip()}
            return username in allowed
    except FileNotFoundError:
        return False
    except Exception as e:
        log_error(f"error leyendo {ALLOWLIST_FILE}: {e}")
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
        log_error("el módulo ldap3 no está instalado")
        return False

    server_url = config.get("server_url")
    bind_dn = config.get("bind_dn")
    bind_password = config.get("bind_password", "")
    search_base = config.get("search_base", "")
    user_filter = config.get("user_filter", "(sAMAccountName=%s)")

    # Un usuario sin contraseña haría un "unauthenticated bind", que LDAP
    # acepta como correcto sin verificar nada.
    if not password:
        return False

    conn = None
    try:
        server = Server(server_url, connect_timeout=5)
        conn = Connection(server, user=bind_dn, password=bind_password,
                          auto_bind=True, receive_timeout=5)
    except Exception as e:
        log_error(f"no se pudo conectar a LDAP: {e}")
        return False

    try:
        # Escapar el usuario para que no altere la estructura del filtro LDAP.
        safe_username = (
            username.replace("\\", "\\5c").replace("*", "\\2a")
            .replace("(", "\\28").replace(")", "\\29").replace("\x00", "\\00")
        )
        search_filter = (
            user_filter.replace("%s", safe_username) if "%s" in user_filter else user_filter
        )

        conn.search(search_base=search_base, search_filter=search_filter,
                    search_scope=SUBTREE, attributes=["1.1"])
        if not conn.entries:
            return False
        user_dn = conn.entries[0].entry_dn
    except Exception as e:
        log_error(f"error buscando el usuario en LDAP: {e}")
        return False
    finally:
        if conn is not None:
            try:
                conn.unbind()
            except Exception:
                pass

    try:
        user_conn = Connection(server, user=user_dn, password=password,
                               auto_bind=True, receive_timeout=5)
        ok = user_conn.bound
        try:
            user_conn.unbind()
        except Exception:
            pass
        return ok
    except Exception:
        # Contraseña incorrecta: es un resultado normal, no un error del helper.
        return False


def authenticate(username, password):
    """Local primero, LDAP después."""
    if check_local(username, password):
        return True
    return check_ldap(username, password)


def handle(line):
    """Procesa una línea del protocolo y devuelve la respuesta para Squid."""
    parts = line.split(None, 1)
    if not parts:
        return "ERR"

    raw_user = parts[0]
    raw_pass = parts[1] if len(parts) > 1 else ""

    # Squid escapa en %XX los valores con espacios o caracteres especiales.
    # Se prueba primero el valor decodificado y, si no cuadra, el literal:
    # así funciona tanto con Squid escapando como sin escapar.
    candidates = []
    decoded = (unquote(raw_user), unquote(raw_pass))
    candidates.append(decoded)
    if (raw_user, raw_pass) != decoded:
        candidates.append((raw_user, raw_pass))

    for username, password in candidates:
        if not username:
            continue
        if authenticate(username, password):
            return "OK"
    return "ERR"


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            response = handle(line)
        except Exception as e:
            # Un fallo inesperado deniega esta petición, pero el helper sigue
            # vivo: si muriera, Squid dejaría de autenticar a todos.
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
