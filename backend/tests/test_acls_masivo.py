"""Acción masiva sobre ACLs: borra las que no se usan y reporta las que no pudo."""
from types import SimpleNamespace as N

from app.routes import acls as r


class _Q:
    def __init__(self, filas): self.filas = filas
    def options(self, *_): return self
    def filter(self, *_): return self
    def all(self): return self.filas


class _DB:
    def __init__(self, filas): self.filas, self.borradas, self.agregadas, self.commits = filas, [], [], 0
    def query(self, *_): return _Q(self.filas)
    def add(self, x): self.agregadas.append(x)
    def delete(self, x): self.borradas.append(x.name)
    def commit(self): self.commits += 1


def _acl(i, nombre, enabled=True):
    return N(id=i, name=nombre, enabled=enabled, source="inline", type="dstdomain")


def test_borrado_masivo_omite_las_en_uso(monkeypatch):
    monkeypatch.setattr("app.services.squid_names.usos_de_todas", lambda db: {"b": ["regla X"]})
    marcas = []
    monkeypatch.setattr(r, "mark_dirty", lambda: marcas.append(1))
    db = _DB([_acl(1, "a"), _acl(2, "b"), _acl(3, "c")])
    out = r.accion_masiva(r.AclBulkIn(ids=[1, 2, 3, 99], accion="delete"), db=db,
                          current_admin=N(id=1, username="admin"), background_tasks=None)
    assert out["hechas"] == ["a", "c"] and db.borradas == ["a", "c"]
    motivos = {o["name"]: o["motivo"] for o in out["omitidas"]}
    assert motivos["b"].startswith("En uso") and motivos[None] == "ACL no encontrada"
    assert db.commits == 1 and marcas == [1]


def test_activar_y_desactivar_masivo(monkeypatch):
    monkeypatch.setattr(r, "mark_dirty", lambda: None)
    a, b = _acl(1, "a", enabled=False), _acl(2, "b", enabled=True)
    db = _DB([a, b])
    r.accion_masiva(r.AclBulkIn(ids=[1, 2], accion="enable"), db=db, current_admin=N(id=1, username="x"), background_tasks=None)
    assert a.enabled and b.enabled
    r.accion_masiva(r.AclBulkIn(ids=[1, 2], accion="disable"), db=db, current_admin=N(id=1, username="x"), background_tasks=None)
    assert not a.enabled and not b.enabled and not db.borradas
