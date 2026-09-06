#!/usr/bin/env python3
"""Purga las entradas de audit_log anteriores a la retención configurada.

Pensado para invocarse desde cron, igual que el backup de la base de
datos (ver docs/production.md). No es un endpoint del panel a propósito:
es una tarea de mantenimiento externa, no una acción que un admin dispare
desde la interfaz.

Uso:
    python -m scripts.purge_audit_log [meses]

Si no se pasa `meses`, usa RETENCION_MESES_POR_DEFECTO (12).

En instalación nativa, DATABASE_URL no tiene valor por defecto: systemd
se lo inyecta al backend vía EnvironmentFile=, pero invocar este script
a mano (o desde cron) NO lo hereda automáticamente. Hay que cargar
/opt/squid-manager/.env antes de llamarlo (ver docs/production.md, que
trae el cron ya armado con esto). En Docker no hace falta: `docker exec`
hereda las variables de entorno del propio contenedor.
"""

import logging
import sys

from app.database import SessionLocal
from app.services.audit_service import purgar_antiguos

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> int:
    meses = int(sys.argv[1]) if len(sys.argv) > 1 else None
    db = SessionLocal()
    try:
        kwargs = {"meses": meses} if meses else {}
        borrados = purgar_antiguos(db, **kwargs)
        logger.info(f"Listo: {borrados} entradas de audit_log purgadas.")
        return 0
    except Exception as e:
        logger.error(f"Error purgando audit_log: {e}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
