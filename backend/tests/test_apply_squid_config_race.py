"""Bug real encontrado en la auditoría QA del 2026-09-20: borrar una ACL
mientras otra petición está aplicando la configuración (por ejemplo, un
`add_member`/`remove_member` de grupos, que aplica solo) puede disparar un
`ObjectDeletedError` de SQLAlchemy en pleno renderizado de la plantilla
-`generate_squid_config` defiere `Acl.value` a propósito por rendimiento, y
esa columna se termina pidiendo recién al renderizar, más tarde que la
consulta inicial-. Reproducido en vivo contra la BD real: dos peticiones
concurrentes (borrar una ACL + aplicar cambios) bastan para dispararlo.

Antes de la corrección, esto tumbaba la petición con un 500 crudo. Ahora
`apply_squid_config` lo trata como cualquier otro fallo del pipeline: no
aplica nada, marca pendiente e informa con un mensaje claro.
"""

from sqlalchemy.orm.exc import ObjectDeletedError

from app.services import config_state, squid_service


class _FakeQueryVacia:
    def filter(self, *a, **k):
        return self

    def first(self):
        return None

    def all(self):
        return []


class _FakeDB:
    """Solo lo mínimo para llegar hasta generate_squid_config sin reventar antes."""

    def query(self, *a, **k):
        return _FakeQueryVacia()


def test_objectdeletederror_durante_el_apply_no_tumba_la_peticion(monkeypatch):
    def _generar_y_reventar(db, kerberos=None):
        raise ObjectDeletedError("Instance <Acl> has been deleted, or its row is otherwise not present.")

    monkeypatch.setattr("app.services.config_generator.generate_squid_config", _generar_y_reventar)
    config_state.mark_clean()

    resultado = squid_service.apply_squid_config(db=_FakeDB())

    assert resultado["status"] == "error"
    assert "pendiente" in resultado["message"].lower()
    assert config_state.is_dirty() is True


def test_cualquier_otro_error_inesperado_del_pipeline_tampoco_tumba_la_peticion(monkeypatch):
    def _generar_y_reventar(db, kerberos=None):
        raise RuntimeError("fallo inesperado cualquiera")

    monkeypatch.setattr("app.services.config_generator.generate_squid_config", _generar_y_reventar)
    config_state.mark_clean()

    resultado = squid_service.apply_squid_config(db=_FakeDB())

    assert resultado["status"] == "error"
    assert config_state.is_dirty() is True
