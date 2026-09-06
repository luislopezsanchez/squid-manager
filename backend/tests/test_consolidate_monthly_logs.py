"""Consolidación mensual de logs archivados (almacenamiento en frío).

No ejecuta el script -corre en la máquina de destino, no en la suite-, pero
comprueba las propiedades de seguridad que evitan que se lo lleve puesto algo
que no debería: no debe tocar el archivo activo que lee la plataforma, tiene
que ser idempotente, y tiene que fallar de forma segura (set -e) en vez de
seguir a medias si algo sale mal a mitad de camino.
"""

from pathlib import Path

import pytest

MARCADOR = Path("squid") / "consolidate-monthly-logs.sh"


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
    """Sin set -e, un cat que falla a mitad de mes deja un .tmp corrupto y
    sigue como si nada -el mv posterior lo pisaria sobre el destino bueno."""
    contenido = _script()
    assert "set -euo pipefail" in contenido


def test_no_referencia_el_archivo_activo():
    """Este script es solo para lo ya archivado. Si en algun momento alguien
    le agrega una referencia al access.log activo, es la señal de que se está
    mezclando con la rotación diaria -que existe para mantener ESE archivo
    chico, exactamente lo que este script no debe afectar-."""
    contenido = _script()
    assert "/var/log/squid/access.log" not in contenido
    assert "/var/log/squid/cache.log" not in contenido


def test_es_idempotente():
    """Si el cron se disparara dos veces (o alguien lo corre a mano por las
    dudas), no debe volver a concatenar y duplicar el contenido del mes ya
    consolidado."""
    contenido = _script()
    assert '[ -e "$DESTINO" ]' in contenido


def test_escribe_a_un_temporal_antes_de_reemplazar():
    """Un `cat ... > $DESTINO` directo que se corta a mitad dejaria un
    archivo mensual corrupto y sin forma de detectar que quedo incompleto."""
    contenido = _script()
    assert '"$DESTINO.tmp"' in contenido
    assert "mv " in contenido


def test_se_instala_en_cron_monthly_en_los_dos_modos():
    """/etc/cron.monthly ya lo ejecuta run-parts una vez al mes: declarar una
    entrada de cron aparte seria una segunda fuente de verdad para lo mismo.
    Confirma que el instalador nativo y la imagen Docker de verdad lo dejan
    ahi, no solo que el script en si exista."""
    raiz = _raiz_del_proyecto()
    if raiz is None:
        pytest.skip("el proyecto no esta accesible desde aqui")

    nativo = (raiz / "install-nativo.sh").read_text(encoding="utf-8")
    assert "consolidate-monthly-logs.sh" in nativo
    assert "/etc/cron.monthly/squidmanager-log-archive" in nativo

    dockerfile = (raiz / "squid" / "Dockerfile").read_text(encoding="utf-8")
    assert "consolidate-monthly-logs.sh" in dockerfile
    assert "/etc/cron.monthly/squidmanager-log-archive" in dockerfile
