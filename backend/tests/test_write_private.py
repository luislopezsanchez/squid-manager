"""Prueba de _write_private frente a un fichero preexistente hostil.

Bug real encontrado en vivo (contenedor de pruebas 172.30.36.109) al probar
el backend sin privilegios de root (ver docker-compose.yml /
docker-socket-proxy): el contenedor de Squid crea squid_passwd/squid_digest/
ldap_* con su PROPIO usuario del sistema ('proxy', uid 13) y modo 600 la
primera vez que arranca sin encontrarlos. Un backend no-root (uid 999,
mismo grupo pero distinto dueño) no puede truncar ese fichero in situ -el
`os.open(..., O_TRUNC)` original fallaba con `PermissionError: Permission
denied` en el primer `apply` tras el cambio-, aunque sí tiene permiso de
escritura sobre el directorio que lo contiene. _write_private ahora escribe
a un temporal y hace un rename atómico para no depender del modo/dueño del
fichero anterior.
"""

import os
import sys

import pytest

from app.services.squid_service import _write_private


def test_sobreescribe_fichero_ajeno_de_modo_restrictivo(tmp_path):
    destino = tmp_path / "squid_passwd"

    # Simula lo que deja el contenedor de Squid: un fichero vacío, modo 600,
    # creado por otro proceso. No se puede simular el dueño distinto sin
    # privilegios en la prueba, pero el modo 600 ya alcanza para que un
    # O_TRUNC sobre CUALQUIER usuario que no sea el dueño (o sin permiso de
    # grupo) falle -que es justo lo que reemplaza el rename atómico.
    destino.write_text("")
    os.chmod(destino, 0o600)

    _write_private(destino, "usuario1:hash1\n")

    assert destino.read_text() == "usuario1:hash1\n"
    # El rename deja el modo definitivo (640), no el 600 heredado del viejo.
    # En Windows no hay permisos POSIX reales (chmod es un no-op salvo por el
    # bit de solo-lectura), así que esta comprobación solo tiene sentido
    # donde Squid corre de verdad.
    if sys.platform != "win32":
        assert oct(os.stat(destino).st_mode & 0o777) == oct(0o640)


def test_no_deja_temporales_huerfanos(tmp_path):
    destino = tmp_path / "squid_digest"
    _write_private(destino, "contenido")

    restantes = list(tmp_path.iterdir())
    assert restantes == [destino]


def test_crea_directorio_si_no_existe(tmp_path):
    destino = tmp_path / "sub" / "squid_passwd"
    _write_private(destino, "x")
    assert destino.read_text() == "x"
