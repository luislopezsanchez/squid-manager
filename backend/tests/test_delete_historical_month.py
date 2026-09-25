"""delete_historical_month.sh: el script privilegiado que de verdad borra un
mes histórico (ver historical_log_service.py::delete_month, que lo invoca
vía sudo -n porque el backend corre sin permiso de escritura en
/var/log/squid a propósito).

No lo ejecuta -corre en la máquina de destino, no en la suite, y hacerlo de
verdad implicaría root-, pero comprueba las propiedades de seguridad que
importan en un script que arma una ruta de archivo a partir de dos
argumentos y después la borra: valida su forma antes de usarla, y confirma
que la ruta resuelta sigue adentro del directorio esperado antes del rm -rf.
"""

from pathlib import Path

import pytest

MARCADOR = Path("squid") / "delete_historical_month.sh"


def _raiz_del_proyecto() -> Path | None:
    for base in Path(__file__).resolve().parents:
        if (base / MARCADOR).is_file():
            return base

    from app.services.squid_service import _project_dir

    base = _project_dir()
    return base if base and (base / MARCADOR).is_file() else None


def _script() -> str:
    raiz = _raiz_del_proyecto()
    if raiz is None:
        pytest.skip("el proyecto no esta accesible desde aqui")
    return (raiz / MARCADOR).read_text(encoding="utf-8")


def test_falla_seguro_en_vez_de_seguir_a_medias():
    contenido = _script()
    assert "set -euo pipefail" in contenido


def test_valida_el_year_antes_de_usarlo():
    contenido = _script()
    assert '[[ "$YEAR" =~ ^[0-9]{4}$ ]]' in contenido


def test_valida_el_month_antes_de_usarlo():
    contenido = _script()
    assert '[[ "$MONTH" =~ ^(0[1-9]|1[0-2])$ ]]' in contenido


def test_confirma_que_la_ruta_resuelta_queda_dentro_del_directorio_historico():
    """La validación de forma de YEAR/MONTH ya alcanza para que la ruta no
    pueda salirse de HISTORICAL_DIR, pero esta segunda barrera (comparar la
    ruta resuelta contra la base) es la que de verdad importa si algún día
    cambia cómo se arma DESTINO."""
    contenido = _script()
    assert 'REAL_DESTINO="$(realpath -e "$DESTINO")"' in contenido
    assert '"$REAL_BASE"/*' in contenido


def test_borra_el_anio_si_queda_vacio():
    contenido = _script()
    assert 'rmdir "$ANIO_DIR"' in contenido


def test_no_referencia_el_archivo_activo():
    """Mismo criterio que consolidate-monthly-logs.sh: esto es solo para lo
    ya archivado."""
    contenido = _script()
    assert "/var/log/squid/access.log" not in contenido
    assert "/var/log/squid/cache.log" not in contenido
