#!/usr/bin/env python3
"""Helper de ACL externa para Squid que siempre responde OK con un mensaje
fijo -no consulta nada, existe solo para que el "Motivo" de la página de
bloqueo personalizada (%o, deny_info, ver config_generator.py) pueda
mostrar un texto específico por regla de acceso, sin necesitar un archivo
de página de error nuevo por regla.

Por qué hace falta: Squid solo expone %o (mensaje de un ACL externo) como
forma de meter texto dinámico en una página de error -no hay ningún tag
que diga "qué regla fue" directamente. El truco: se declara una ACL más al
final de la línea `http_access deny ...` (ver squid.conf.j2), que este
helper resuelve SIEMPRE como OK -no cambia si la regla matchea o no-, solo
para que Squid la recuerde como "la última ACL" (así funciona deny_info) y
%o pueda devolver el motivo de esa regla en particular. El motivo en sí
viaja como %DATA de la propia declaración `acl ... external
squidmanager_static_message_helper <palabra1> <palabra2> ...`, no como
argumento de arranque -mismo mecanismo que ya usa domain_block_helper.py
con la categoría de una lista de bloqueo. SIN comillas a propósito: en una
línea `acl`, un argumento entre comillas significa "leer esto como
archivo" para Squid -para cualquier tipo de ACL, no solo dstdomain-, así
que un motivo con espacios envuelto en comillas rompe con "Can not open
file ... for reading" (confirmado en vivo, 2026-09-27). Squid junta cada
palabra suelta en %DATA, separadas por espacio, cada una URL-encoded por
su cuenta.

Protocolo (external_acl_type, sin concurrency, formato %DATA sola): cada
línea de entrada trae el motivo partido en una o más palabras
URL-encoded; se decodifica cada una y se vuelven a unir con un espacio
para reconstruir el texto original. Igual que domain_block_helper.py,
ninguna excepción debe escapar del bucle principal -es un proceso de
larga duración (children-max=), y si Squid lo marca caído deja de
resolver esta ACL para todo el mundo.
"""

import sys
import syslog
from urllib.parse import unquote


def log_error(message):
    try:
        syslog.syslog(syslog.LOG_ERR, f"squidmanager_static_message_helper: {message}")
    except Exception:
        pass
    try:
        sys.stderr.write(f"squidmanager_static_message_helper: {message}\n")
        sys.stderr.flush()
    except Exception:
        pass


def handle(line: str) -> str:
    # El motivo llega como varias palabras sueltas (%DATA), no como un
    # único argumento entre comillas -ver el comentario en squid.conf.j2
    # sobre por qué las comillas no sirven acá (Squid las interpreta como
    # "leer de un archivo", para cualquier tipo de ACL). Cada palabra ya
    # viene URL-encoded por separado; se decodifica cada una y se vuelven
    # a unir con un espacio para reconstruir el texto original.
    partes = line.strip().split()
    motivo = " ".join(unquote(p) for p in partes)
    return f'OK message="{motivo}"'


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            response = handle(line)
        except Exception as e:
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
