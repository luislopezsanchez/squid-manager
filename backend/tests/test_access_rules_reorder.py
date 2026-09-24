"""Bugs reales encontrados en la auditoría QA del 2026-09-20:

- `PUT /access-rules/reorder` con una lista vacía devolvía 200 sin avisar
  que no hizo nada (probablemente un bug del frontend, no una operación
  intencional).
- Un ID inexistente en la lista se ignoraba en silencio (`if rule:`), sin
  que el llamador se enterara de que algo no se aplicó.

Ambos casos ahora responden 400 con un mensaje explícito.
"""

import pytest
from fastapi import HTTPException

from app.routes.access_rules import ReorderRequest, reorder_rules


class _FakeRule:
    def __init__(self, id, action="allow", acl_names="todo", order=0):
        self.id = id
        self.action = action
        self.acl_names = acl_names
        self.order = order


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *a, **k):
        return self

    def order_by(self, *a, **k):
        return self

    def all(self):
        return self._rows


class _FakeDB:
    def __init__(self, reglas):
        self._reglas = reglas

    def query(self, *a, **k):
        return _FakeQuery(list(self._reglas))

    def add(self, obj):
        pass

    def commit(self):
        pass


class _FakeAdmin:
    id = 1
    username = "admin"


def _reordenar(rule_ids, reglas):
    # reorder_rules() es sync (ver app/routes/access_rules.py): se llama
    # directo, sin asyncio.run().
    return reorder_rules(
        ReorderRequest(rule_ids=rule_ids),
        db=_FakeDB(reglas),
        current_admin=_FakeAdmin(),
        background_tasks=None,
    )


def test_lista_vacia_es_rechazada():
    with pytest.raises(HTTPException) as exc:
        _reordenar([], [_FakeRule(1), _FakeRule(2)])
    assert exc.value.status_code == 400


def test_id_inexistente_es_rechazado():
    with pytest.raises(HTTPException) as exc:
        _reordenar([1, 999], [_FakeRule(1)])
    assert exc.value.status_code == 400
    assert "999" in exc.value.detail


def test_reorden_valido_se_aplica():
    r1, r2 = _FakeRule(1, order=0), _FakeRule(2, order=1)
    resultado = _reordenar([2, 1], [r1, r2])
    assert r2.order == 0
    assert r1.order == 1
