"""Pruebas del arranque del backend.

El caso que motivó estas pruebas: al reinstalar sobre el volumen de datos de una
instalación anterior, PostgreSQL conserva la contraseña con la que se creó, el
backend no puede entrar y el arranque moría con un volcado de más de cien líneas
de SQLAlchemy donde la causa aparecía enterrada en la penúltima.
"""

import logging

from sqlalchemy.exc import OperationalError

from app.main import _explicar_fallo_de_conexion


def _error(mensaje: str) -> OperationalError:
    return OperationalError("SELECT 1", {}, Exception(mensaje))


def test_contrasena_rechazada_explica_el_volumen_heredado(caplog):
    with caplog.at_level(logging.ERROR):
        _explicar_fallo_de_conexion(
            _error('connection failed: FATAL:  password authentication failed for user "squid"')
        )

    texto = caplog.text
    # Lo esencial: que diga por qué pasa y las dos salidas posibles.
    assert "instalación anterior" in texto
    assert "docker compose down -v" in texto      # empezar de cero
    assert "DB_PASS" in texto                     # conservar los datos
    assert "BORRA TODOS LOS DATOS" in texto       # el aviso, bien visible


def test_base_inalcanzable_manda_a_mirar_el_contenedor(caplog):
    with caplog.at_level(logging.ERROR):
        _explicar_fallo_de_conexion(_error("connection failed: Connection refused"))

    texto = caplog.text
    assert "docker compose ps db" in texto
    # Este no es el caso del volumen: no debe sugerir borrar datos.
    assert "down -v" not in texto


def test_un_fallo_desconocido_no_se_disfraza(caplog):
    """Ante algo que no reconocemos, se muestra tal cual en vez de inventar."""
    with caplog.at_level(logging.ERROR):
        _explicar_fallo_de_conexion(_error("algo raro que no habiamos visto"))

    texto = caplog.text
    assert "algo raro que no habiamos visto" in texto
    assert "down -v" not in texto
