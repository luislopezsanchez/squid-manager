"""Backup/restore automatizado de la base de datos (hallazgo 07-001 de la
auditoría 2026-09-08: sin evidencia de backup automatizado ni restaurado).

Mismo criterio que test_consolidate_monthly_logs.py: no ejecuta los
scripts -corren en la máquina de destino, no en la suite-, pero comprueba
las propiedades de seguridad que no deben perderse: escritura atómica,
rotación real, funciona en los dos modos de despliegue, y el restore
avisa antes de reemplazar la base.
"""

from pathlib import Path

import pytest

BACKUP = Path("backup-database.sh")
RESTORE = Path("restore-database.sh")


def _raiz_del_proyecto() -> Path | None:
    for base in Path(__file__).resolve().parents:
        if (base / BACKUP).is_file():
            return base

    from app.services.squid_service import _project_dir

    base = _project_dir()
    return base if base and (base / BACKUP).is_file() else None


def _script(nombre: Path) -> str:
    raiz = _raiz_del_proyecto()
    if raiz is None:
        pytest.skip("el proyecto no esta accesible desde aqui")
    return (raiz / nombre).read_text(encoding="utf-8")


def test_backup_falla_seguro():
    assert "set -euo pipefail" in _script(BACKUP)


def test_backup_escribe_a_un_temporal_antes_de_reemplazar():
    """Un pg_dump cortado a mitad de camino (disco lleno, cron matado) no
    debe dejar un .sql.gz a medias con nombre de backup terminado."""
    contenido = _script(BACKUP)
    assert '"$TMP"' in contenido
    assert "mv " in contenido


def test_backup_funciona_en_los_dos_modos_de_despliegue():
    contenido = _script(BACKUP)
    assert 'if [ "$DEPLOY_MODE" = "native" ]' in contenido
    assert "sudo -u postgres pg_dump" in contenido
    assert "docker exec squidmgr-db pg_dump" in contenido


def test_backup_tiene_retencion_configurable_con_valor_por_defecto():
    """Sin esto, backups/ crece para siempre -mismo motivo que la
    retención del histórico de logs, hallazgo 08-001 de la misma
    auditoría."""
    contenido = _script(BACKUP)
    assert 'RETENCION_DIAS_BACKUP="${RETENCION_DIAS_BACKUP:-14}"' in contenido
    assert "-mtime" in contenido


def test_backup_usa_clean_if_exists():
    """Bug real encontrado en vivo: sin --clean --if-exists, restaurar sobre
    una base que YA tiene datos (el caso real de una recuperación) deja una
    pila de 'already exists'/'duplicate key' y la restauración queda a
    medias, en vez de reemplazar todo de verdad."""
    contenido = _script(BACKUP)
    assert "--clean --if-exists" in contenido


def test_backup_carga_el_env_para_cron():
    """cron no hereda el entorno del shell interactivo -mismo motivo por
    el que purge_audit_log.py necesita el mismo paso-: sin cargar el
    .env, DEPLOY_MODE/DB_NAME/DB_USER no llegan al script."""
    contenido = _script(BACKUP)
    assert '. "$PROJECT_DIR/.env"' in contenido


def test_restore_pide_el_archivo_como_argumento():
    contenido = _script(RESTORE)
    assert 'ARCHIVO="${1:-}"' in contenido


def test_restore_avisa_antes_de_reemplazar():
    """Restaurar reemplaza la base entera: no debe ejecutarse en
    silencio sin que quien lo corre vea explícitamente qué va a pasar."""
    contenido = _script(RESTORE)
    assert "REEMPLAZA" in contenido or "reemplaza" in contenido


def test_restore_funciona_en_los_dos_modos_de_despliegue():
    contenido = _script(RESTORE)
    assert 'if [ "$DEPLOY_MODE" = "native" ]' in contenido
    assert "docker exec -i squidmgr-db psql" in contenido
