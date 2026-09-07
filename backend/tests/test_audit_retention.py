"""Pruebas de la retención de audit_log.

El registro de auditoría (quién cambió qué y cuándo) crecía sin límite: a
diferencia de los logs de navegación de Squid (7 días, vía logrotate), no
tenía ninguna política de retención. Esto prueba la función que la
implementa.
"""

from datetime import timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.audit_log import AuditLog
from app.services.audit_service import purgar_antiguos, RETENCION_MESES_POR_DEFECTO
from app.utils import utcnow


@pytest.fixture
def db():
    """Sesión sobre una BD SQLite en memoria, con SOLO la tabla audit_log.

    Esta prueba necesita un motor SQL real (purgar_antiguos hace un DELETE
    con filtro por fecha, no algo que un FakeDB pueda replicar con fidelidad
    sin duplicar la lógica que se está probando) — es la única de la suite
    que se conecta a una base de verdad, el resto usa FakeDB/mocks (ver
    conftest.py). Por eso mismo hay que crear solo la tabla que hace falta:
    `Base.metadata.create_all()` crea TODAS las tablas de la app, y
    doc_chunks (Asistente de IA) usa TSVECTOR, un tipo exclusivo de
    PostgreSQL que SQLite no sabe compilar — rompía este test entero por un
    modelo con el que no tiene nada que ver.
    """
    engine = create_engine("sqlite:///:memory:")
    AuditLog.__table__.create(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _crear_entrada(db, dias_atras: int) -> AuditLog:
    entrada = AuditLog(
        admin_username="admin",
        action="update",
        entity="acl",
        timestamp=utcnow() - timedelta(days=dias_atras),
    )
    db.add(entrada)
    db.commit()
    return entrada


def test_borra_solo_lo_mas_viejo_que_el_corte(db):
    _crear_entrada(db, dias_atras=400)   # más viejo que 12 meses
    _crear_entrada(db, dias_atras=10)    # reciente

    borrados = purgar_antiguos(db, meses=12)

    assert borrados == 1
    restantes = db.query(AuditLog).all()
    assert len(restantes) == 1
    assert restantes[0].action == "update"  # sigue siendo la reciente


def test_sin_entradas_viejas_no_borra_nada(db):
    _crear_entrada(db, dias_atras=1)
    _crear_entrada(db, dias_atras=30)

    borrados = purgar_antiguos(db, meses=12)

    assert borrados == 0
    assert db.query(AuditLog).count() == 2


def test_meses_personalizado(db):
    """Una retención más corta borra entradas que la de 12 meses conservaría."""
    _crear_entrada(db, dias_atras=100)

    borrados = purgar_antiguos(db, meses=2)

    assert borrados == 1


def test_retencion_por_defecto_es_12_meses():
    assert RETENCION_MESES_POR_DEFECTO == 12
