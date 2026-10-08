"""Base SQLite en memoria con las tablas reales, para probar rutas con consultas de verdad (sin PostgreSQL)."""
import importlib
import pkgutil

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import app.models as _modelos

for _m in pkgutil.iter_modules(_modelos.__path__):
    importlib.import_module(f"app.models.{_m.name}")

from app.database import Base  # noqa: E402


def nueva_sesion():
    motor = create_engine("sqlite://")
    for t in Base.metadata.sorted_tables:
        if t.name != "doc_chunks":          # columna tsvector: solo PostgreSQL
            t.create(motor)
    with motor.begin() as c:                # la crea una migración, no un modelo
        c.execute(text("CREATE TABLE app_modules (key TEXT PRIMARY KEY, enabled BOOLEAN, updated_at TIMESTAMP)"))
    return sessionmaker(bind=motor, expire_on_commit=False)()
