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
  - /etc/squid/squid_passwd       : htpasswd local (bcrypt; al migrar desde otro Squid
                                    también apr1, SHA y crypt -ver verify_password_hash)
  - /etc/squid/ldap_allowlist     : usuarios LDAP autorizados (allow-list estricto)
  - /etc/squid/ldap_helper.conf   : config de conexión LDAP (key=value)
"""

import sys
import syslog
from urllib.parse import unquote

HTPASSWD_FILE = "/etc/squid/squid_passwd"
ALLOWLIST_FILE = "/etc/squid/ldap_allowlist"
LDAP_CONF_FILE = "/etc/squid/ldap_helper.conf"


def _escapar_filtro_ldap(valor: str) -> str:
    """Escapa un valor para insertarlo en un filtro LDAP (RFC 4515).

    Sin esto, un nombre de usuario con paréntesis o asterisco altera la
    estructura del filtro de búsqueda. Misma lógica que
    backend/app/routes/ldap.py:_escapar_filtro_ldap (que valida la conexión
    LDAP desde el panel) — este es el helper que autentica de verdad cada
    login del proxy, así que es el que más importa mantener correcto. Un
    test (backend/tests/test_ldap_escape_consistente.py) compara ambas
    copias byte a byte contra el mismo juego de casos para detectar
    cualquier divergencia si una se corrige sin la otra: este script corre
    en el runtime de Squid, fuera del paquete del backend, así que no puede
    importar directamente la copia del panel.
    """
    return (
        valor.replace("\\", "\\5c").replace("*", "\\2a")
        .replace("(", "\\28").replace(")", "\\29").replace("\x00", "\\00")
    )


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


_ITOA64 = "./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def _apr1_md5(password: bytes, salt: bytes) -> str:
    """Hash MD5 de Apache ($apr1$), el que generan `htpasswd -m` y muchos
    Squid instalados a mano. Implementación de referencia del algoritmo."""
    import hashlib

    ctx = password + b"$apr1$" + salt
    final = hashlib.md5(password + salt + password).digest()
    for pl in range(len(password), 0, -16):
        ctx += final[:16] if pl > 16 else final[:pl]
    i = len(password)
    while i:
        ctx += b"\x00" if i & 1 else password[:1]
        i >>= 1
    final = hashlib.md5(ctx).digest()
    for i in range(1000):
        c = password if i & 1 else final
        if i % 3:
            c += salt
        if i % 7:
            c += password
        c += final if i & 1 else password
        final = hashlib.md5(c).digest()

    def to64(v, n):
        out = ""
        for _ in range(n):
            out += _ITOA64[v & 0x3F]
            v >>= 6
        return out

    out = ""
    for a, b, c in ((0, 6, 12), (1, 7, 13), (2, 8, 14), (3, 9, 15), (4, 10, 5)):
        out += to64((final[a] << 16) | (final[b] << 8) | final[c], 4)
    out += to64(final[11], 2)
    return out


def verify_password_hash(password, stored):
    """Compara una contraseña contra un hash de htpasswd de CUALQUIER formato
    que use un Squid administrado a mano, para que quien migra desde uno no
    tenga que cambiar la contraseña a todos sus usuarios:

      - bcrypt   ($2y$ / $2b$ / $2a$): el que genera este panel.
      - Apache MD5 ($apr1$): `htpasswd -m`.
      - SHA-1 ({SHA}): `htpasswd -s`.
      - crypt(3): DES de 13 caracteres, $1$, $5$, $6$.
    """
    import base64
    import hashlib
    import hmac

    if not stored:
        return False
    if stored.startswith(("$2y$", "$2b$", "$2a$")):
        try:
            import bcrypt
            return bcrypt.checkpw(password.encode("utf-8"), stored.replace("$2y$", "$2b$", 1).encode("utf-8"))
        except Exception:
            return False
    if stored.startswith("$apr1$"):
        partes = stored.split("$")
        if len(partes) < 4:
            return False
        calculado = "$apr1$" + partes[2] + "$" + _apr1_md5(password.encode("utf-8"), partes[2].encode("utf-8"))
        return hmac.compare_digest(calculado, stored)
    if stored.startswith("{SHA}"):
        calculado = "{SHA}" + base64.b64encode(hashlib.sha1(password.encode("utf-8")).digest()).decode()
        return hmac.compare_digest(calculado, stored)
    if stored.startswith(("$1$", "$5$", "$6$")) or (len(stored) == 13 and stored[0] not in "$"):
        try:
            import crypt
            return hmac.compare_digest(crypt.crypt(password, stored) or "", stored)
        except Exception:
            return False
    return False


def check_local(username, password):
    """Verifica usuario/contraseña contra el htpasswd local (squid_passwd).

    Acepta los formatos de hash de un htpasswd tradicional (ver
    verify_password_hash), no solo bcrypt."""
    try:
        with open(HTPASSWD_FILE) as f:
            for line in f:
                line = line.strip()
                if not line or ":" not in line:
                    continue
                u, h = line.split(":", 1)
                if u != username:
                    continue
                return verify_password_hash(password, h)
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
        safe_username = _escapar_filtro_ldap(username)
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
