"""Retención del registro de auditoría (audit_log).

Los logs de Squid —el dato más sensible que maneja este sistema, el
historial de navegación de personas identificadas— sí tienen retención:
rotación diaria y 7 días, vía `squid/squid-logrotate` (documentado en
docs/production.md). El `audit_log` (quién cambió qué ajuste y cuándo)
se había quedado fuera de ese criterio y crecía sin límite.

Igual que el resto del mantenimiento periódico del proyecto (backups,
rotación de logs), la purga no vive dentro del backend como una tarea en
segundo plano: se invoca desde fuera por cron, vía
`backend/scripts/purge_audit_log.py`. Así no hace falta un scheduler
nuevo dentro de la aplicación para una tarea que corre, como mucho, una
vez al día.
"""

import logging
from datetime import timedelta

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.utils import utcnow

logger = logging.getLogger(__name__)

# 12 meses: más largo que los 7 días de retención de los logs de
# navegación a propósito (es un registro de auditoría administrativa, no
# el historial de navegación), pero con un límite explícito en vez de
# "para siempre".
RETENCION_MESES_POR_DEFECTO = 12


def purgar_antiguos(db: Session, meses: int = RETENCION_MESES_POR_DEFECTO) -> int:
    """Borra las entradas de audit_log anteriores a `meses` meses.

    Devuelve cuántas filas se borraron.
    """
    corte = utcnow() - timedelta(days=meses * 30)
    borrados = (
        db.query(AuditLog)
        .filter(AuditLog.timestamp < corte)
        .delete(synchronize_session=False)
    )
    db.commit()
    if borrados:
        logger.info(f"audit_log: purgadas {borrados} entradas anteriores a {corte.date()}")
    return borrados
