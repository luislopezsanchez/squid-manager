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


def test_organiza_por_anio_y_mes():
    """El histórico se organiza en carpetas AAAA/MM, no en un único directorio
    plano: es lo que hace manejable navegar años de logs desde el panel."""
    contenido = _script()
    assert 'HISTORICAL_DIR="$ARCHIVE_DIR/historical"' in contenido
    assert 'DESTINO_DIR="$HISTORICAL_DIR/$ANIO/$MES_NUM"' in contenido


def test_genera_el_indice_solo_para_access_no_cache():
    """cache.log es diagnostico interno de Squid, sin usuarios/dominios/
    estados que resumir: no tiene sentido indexarlo."""
    contenido = _script()
    assert 'if [ "$TIPO" = "access" ]' in contenido
    assert "build_monthly_index.py" not in contenido or "INDEXADOR" in contenido


def test_el_indexador_es_opcional_no_bloqueante():
    """Una instalacion vieja sin actualizar el indexador todavia debe poder
    consolidar el .gz: perder logs por falta del resumen seria peor que no
    tener el resumen."""
    contenido = _script()
    assert '[ -f "$INDEXADOR" ] || INDEXADOR=""' in contenido


def test_indexador_fuera_de_cron_monthly():
    """Cualquier archivo en /etc/cron.monthly lo ejecuta run-parts por su
    cuenta una vez al mes: el indexador es una libreria que invoca este
    script, no una tarea independiente."""
    contenido = _script()
    assert "/usr/local/lib/squidmanager/build_monthly_index.py" in contenido
    assert "/etc/cron.monthly/build_monthly_index" not in contenido


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
    assert "/usr/local/lib/squidmanager/build_monthly_index.py" in nativo

    dockerfile = (raiz / "squid" / "Dockerfile").read_text(encoding="utf-8")
    assert "consolidate-monthly-logs.sh" in dockerfile
    assert "/etc/cron.monthly/squidmanager-log-archive" in dockerfile
    assert "/usr/local/lib/squidmanager/build_monthly_index.py" in dockerfile


# --- Purga por retención (hallazgo 08-001 de la auditoría 2026-09-08) ------

def test_tiene_retencion_configurable_con_valor_por_defecto():
    """Sin límite, el histórico crecía para siempre -inconsistente con el
    resto del proyecto, que sí purga lo demás (30 días los diarios, 12
    meses el audit_log)."""
    contenido = _script()
    assert 'RETENCION_MESES_HISTORICO="${RETENCION_MESES_HISTORICO:-12}"' in contenido


def test_purga_por_mes_completo_no_archivo_por_archivo():
    """Un mes es la unidad del histórico (access+cache+index.json juntos):
    borrar a medias dejaría un index.json huérfano sin sus .gz, o viceversa."""
    contenido = _script()
    assert 'rm -rf "$MES_DIR"' in contenido


def test_ignora_directorios_con_nombre_no_numerico():
    """Un directorio que no sea AAAA o MM (algo dejado a mano, por ejemplo)
    no debe intentar compararse como fecha ni, mucho menos, borrarse por
    error."""
    contenido = _script()
    assert "*[!0-9]*" in contenido


def test_retira_el_anio_si_quedo_vacio():
    """Sin esto, los directorios AAAA de años ya purgados enteros se
    acumulan vacíos para siempre."""
    contenido = _script()
    assert 'rmdir "$ANIO_DIR"' in contenido
