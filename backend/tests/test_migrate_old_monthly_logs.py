"""Migración del layout plano anterior (archive/monthly/) al actual por
año/mes (archive/historical/AAAA/MM/).

Mismo criterio que test_consolidate_monthly_logs.py: no ejecuta el script
-corre en la máquina de destino, no en la suite-, pero comprueba las
propiedades de seguridad que no deben perderse en un cambio futuro:
idempotencia, no sobreescribir ante un choque, fallar seguro, y no tocar
nunca el archivo activo.
"""

from pathlib import Path

import pytest

MARCADOR = Path("squid") / "migrate-old-monthly-logs.sh"


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
    assert "set -euo pipefail" in _script()


def test_no_referencia_el_archivo_activo():
    contenido = _script()
    assert "/var/log/squid/access.log" not in contenido
    assert "/var/log/squid/cache.log" not in contenido


def test_no_sobreescribe_si_el_destino_ya_existe():
    """El caso más peligroso: si alguien ya corrió esto (o consolidate-
    monthly-logs.sh en las dos versiones dejó algo en los dos sitios a la
    vez), un mv ciego pisaría un archivo bueno con otro -o al revés-."""
    contenido = _script()
    assert 'if [ -e "$DESTINO" ]; then' in contenido
    # La rama de "ya existe" tiene que evitar el mv, no solo avisar.
    bloque = contenido.split('if [ -e "$DESTINO" ]; then', 1)[1].split("fi", 1)[0]
    assert "mv " not in bloque


def test_instalacion_nueva_no_hace_nada():
    """Sin archive/monthly, o vacío, el script debe salir en 0 sin
    quejarse -es el caso normal para cualquier instalación nueva-."""
    contenido = _script()
    assert 'if [ ! -d "$MONTHLY_DIR" ]; then' in contenido
    assert "exit 0" in contenido


def test_es_idempotente_por_diseno():
    """La combinación de las dos comprobaciones de arriba (sale si no hay
    nada, no pisa lo que ya está) es lo que hace que correrlo dos veces
    seguidas sea seguro -de eso depende que el aviso a los usuarios diga
    'seguro correrlo dos veces' en docs/actualizacion.md."""
    contenido = _script()
    assert 'if [ -e "$DESTINO" ]; then' in contenido
    assert 'if [ ! -d "$MONTHLY_DIR" ]; then' in contenido


def test_genera_indice_solo_para_access():
    contenido = _script()
    assert 'if [ "$TIPO" = "access" ]; then' in contenido


def test_indexador_ausente_no_bloquea_la_migracion():
    """Un índice que falta es menos grave que perder el .gz consolidado:
    si el indexador no está instalado, el archivo debe migrarse igual."""
    contenido = _script()
    assert 'elif [ ! -f "$INDEXADOR" ]; then' in contenido


def test_documentado_en_la_guia_de_actualizacion():
    raiz = _raiz_del_proyecto()
    if raiz is None:
        pytest.skip("el proyecto no esta accesible desde aqui")
    doc = (raiz / "docs" / "actualizacion.md").read_text(encoding="utf-8")
    assert "migrate-old-monthly-logs.sh" in doc
