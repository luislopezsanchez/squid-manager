"""Que las migraciones no bajen el nivel de log de la aplicación.

Segunda mitad del mismo problema. Aunque `fileConfig` ya no desactive los
loggers existentes, aplica el nivel que declara el alembic.ini —WARN— al logger
raíz. Como la aplicación registra sus avisos con `logger.info()`, todo lo
posterior a las migraciones se descartaba por nivel: el arranque parecía
cortarse a la mitad y en producción se perdían los mensajes informativos.
"""

import logging
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent


def test_el_alembic_ini_baja_el_nivel_raiz():
    """Deja constancia de por qué hace falta restaurarlo.

    Si algún día el alembic.ini pasa a declarar INFO, este test lo señala y se
    podrá simplificar run_migrations().
    """
    ini = (BACKEND_DIR / "alembic.ini").read_text()
    assert "level = WARN" in ini, (
        "El alembic.ini ya no baja el nivel raíz: revisa si sigue haciendo "
        "falta restaurarlo en run_migrations()."
    )


def test_run_migrations_restaura_el_nivel():
    """Guardia contra la regresión."""
    fuente = (BACKEND_DIR / "app" / "main.py").read_text()
    assert "logging.getLogger().setLevel(logging.INFO)" in fuente, (
        "run_migrations() debe devolver el nivel raíz a INFO después de "
        "migrar, o la aplicación se queda sin logs informativos."
    )


def test_asi_se_perdian_los_mensajes():
    """Demuestra el mecanismo sin tocar la configuración del proceso."""
    raiz = logging.getLogger()
    nivel_original = raiz.level
    try:
        raiz.setLevel(logging.WARNING)   # como lo deja Alembic
        assert not raiz.isEnabledFor(logging.INFO), "un info se descartaria"
        assert raiz.isEnabledFor(logging.WARNING), "un warning si pasaria"

        raiz.setLevel(logging.INFO)      # como lo deja el arreglo
        assert raiz.isEnabledFor(logging.INFO)
    finally:
        raiz.setLevel(nivel_original)
