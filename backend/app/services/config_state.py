"""Estado de "cambios pendientes" del squid.conf.

Permite saber si hay cambios en la BD que aún NO se han aplicado a Squid
(es decir, que requieren pulsar "Aplicar Cambios").

- Los cambios en ACLs, reglas, delay pools, settings y grupos modifican el
  squid.conf, por lo que marcan "dirty" hasta que se apliquen.
- Los cambios en usuarios del proxy (squid_passwd) y LDAP se aplican de
  inmediato (regeneran el archivo y recargan), por lo que NO marcan dirty.
"""

_dirty = False


def mark_dirty() -> None:
    """Marca que hay cambios sin aplicar."""
    global _dirty
    _dirty = True


def mark_clean() -> None:
    """Marca que no hay cambios pendientes (tras aplicar)."""
    global _dirty
    _dirty = False


def is_dirty() -> bool:
    """Devuelve True si hay cambios sin aplicar."""
    return _dirty
