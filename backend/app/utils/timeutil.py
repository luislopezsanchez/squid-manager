"""Fecha y hora en UTC.

`datetime.utcnow()` está obsoleto desde Python 3.12. El reemplazo directo,
`datetime.now(timezone.utc)`, devuelve un datetime con zona horaria, y las
columnas del esquema son TIMESTAMP WITHOUT TIME ZONE. Para no mezclar valores
con y sin zona en la misma columna, aquí se calcula la hora en UTC y se
devuelve sin tzinfo: mismo valor que antes, sin el aviso de obsolescencia.
"""

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Fecha y hora actual en UTC, sin zona horaria adjunta."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def as_naive_utc(value):
    """Normaliza un datetime a UTC sin zona horaria.

    Las fechas que llegan por la API pueden traer zona ("2026-09-01T00:00+02:00")
    y las columnas del esquema no la tienen. Comparar una con otra lanza
    TypeError, así que todo se convierte a UTC antes de guardarlo o compararlo.
    """
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value
