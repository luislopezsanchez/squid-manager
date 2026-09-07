#!/usr/bin/env python3
"""Helper de autenticación Digest (RFC 2617) para usuarios LOCALES del proxy.

Protocolo de Squid (auth digest, Squid 3.4+ — ver
https://wiki.squid-cache.org/Features/AddonHelpers):
  - Squid escribe '"usuario":"realm"\\n' en stdin (usuario y realm entre
    comillas dobles, separados por dos puntos).
  - El helper NUNCA ve la contraseña ni la respuesta digest del cliente: solo
    resuelve usuario+realm a su HA1 = MD5(usuario:realm:password). Squid
    calcula y compara el digest de la respuesta por su cuenta, con ese HA1.
  - El helper responde 'OK ha1="<hex>"\\n' si existe, o 'ERR\\n' si no.
  - Es un proceso de larga duración (un helper atiende muchas peticiones).

Solo usuarios LOCALES: a diferencia de auth_helper.py (Basic), este no
consulta LDAP. digest_ldap_auth existiría, pero exige que el directorio
guarde el HA1 en un atributo -no es estándar en Active Directory ni en la
mayoría de esquemas LDAP, así que requeriría preparar el directorio aparte
(fuera del alcance de lo que SquidManager puede automatizar). Ver el aviso
que el panel muestra en Configuración al activar Digest con LDAP habilitado.

Archivo de configuración (escrito por el backend en el volumen compartido):
  - /etc/squid/squid_digest : "usuario:realm:HA1" por línea (mismo formato
    que espera digest_file_auth con -c, para poder usar el binario oficial
    de Squid como respaldo/depuración si hiciera falta).
"""

import re
import sys
import syslog

DIGEST_FILE = "/etc/squid/squid_digest"

# "usuario":"realm" — con o sin espacio alrededor de los dos puntos, tal como
# lo puede mandar cualquier version de Squid.
LINEA_PATTERN = re.compile(r'^"([^"]*)"\s*:\s*"([^"]*)"')


def log_error(message):
    """Deja constancia del fallo sin escribir en stdout, que es el canal de Squid."""
    try:
        syslog.syslog(syslog.LOG_ERR, f"squidmanager_digest_helper: {message}")
    except Exception:
        pass
    try:
        sys.stderr.write(f"squidmanager_digest_helper: {message}\n")
        sys.stderr.flush()
    except Exception:
        pass


def buscar_ha1(username: str, realm: str) -> str | None:
    """Busca el HA1 de usuario+realm en el archivo local. None si no existe."""
    try:
        with open(DIGEST_FILE) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or line.count(":") < 2:
                    continue
                u, r, ha1 = line.split(":", 2)
                if u == username and r == realm:
                    return ha1
    except FileNotFoundError:
        pass
    except Exception as e:
        log_error(f"error leyendo {DIGEST_FILE}: {e}")
    return None


def handle(line: str) -> str:
    """Procesa una línea del protocolo y devuelve la respuesta para Squid."""
    m = LINEA_PATTERN.match(line.strip())
    if not m:
        return "BH message=\"formato de peticion invalido\""

    username, realm = m.group(1), m.group(2)
    if not username:
        return "ERR"

    ha1 = buscar_ha1(username, realm)
    if ha1 is None:
        return "ERR"

    return f'OK ha1="{ha1}"'


def main():
    for line in sys.stdin:
        line = line.rstrip("\n")
        if not line:
            continue
        try:
            response = handle(line)
        except Exception as e:
            # Un fallo inesperado deniega esta peticion, pero el helper sigue
            # vivo: si muriera, Squid dejaria de autenticar a todos.
            log_error(f"error inesperado procesando una peticion: {e}")
            response = "BH message=\"error interno del helper\""

        sys.stdout.write(response + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        log_error(f"el helper termino por un error: {e}")
        sys.exit(1)
