"""Que las migraciones no dejen muda a la aplicación.

Alembic reconfigura el logging al arrancar sus migraciones. Con los valores por
defecto de `fileConfig` desactiva todos los loggers que no aparezcan en el
alembic.ini —donde solo están root, sqlalchemy y alembic—, y como las
migraciones corren durante el arranque del backend, la aplicación se quedaba sin
log a partir de ese punto: ni «Migraciones aplicadas», ni la contraseña del
administrador recién creado, ni los errores posteriores en producción.

El síntoma era engañoso: el log se cortaba en medio de Alembic y parecía que el
backend se hubiera colgado, cuando seguía atendiendo peticiones con normalidad.
"""

import logging
from logging.config import fileConfig
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"


def test_env_py_conserva_los_loggers_existentes():
    """Guardia contra la regresión: el parámetro tiene que seguir ahí."""
    fuente = (BACKEND_DIR / "migrations" / "env.py").read_text()
    assert "disable_existing_loggers=False" in fuente, (
        "env.py debe pasar disable_existing_loggers=False a fileConfig, o las "
        "migraciones volverán a silenciar el log de la aplicación."
    )


def test_asi_es_como_se_silenciaba(tmp_path):
    """Demuestra el mecanismo, para que quede claro por qué importa.

    Se usa un fichero de configuración propio, no el del proyecto, para no
    tocar el logging del proceso de pruebas.
    """
    ini = tmp_path / "prueba.ini"
    ini.write_text(
        "[loggers]\nkeys = root\n\n"
        "[handlers]\nkeys = console\n\n"
        "[formatters]\nkeys = simple\n\n"
        "[logger_root]\nlevel = WARN\nhandlers = console\n\n"
        "[handler_console]\nclass = StreamHandler\nlevel = NOTSET\n"
        "formatter = simple\nargs = (sys.stderr,)\n\n"
        "[formatter_simple]\nformat = %(message)s\n"
    )

    de_la_app = logging.getLogger("prueba.app.silenciada")
    assert not de_la_app.disabled

    # Con los valores por defecto, tal como estaba: el logger queda desactivado.
    fileConfig(str(ini))
    assert de_la_app.disabled, "fileConfig deberia haberlo desactivado"

    # Con el parámetro que ahora usa env.py, sobrevive.
    otro = logging.getLogger("prueba.app.viva")
    fileConfig(str(ini), disable_existing_loggers=False)
    assert not otro.disabled

    # No dejar rastro para el resto de la suite.
    de_la_app.disabled = False
    otro.disabled = False
