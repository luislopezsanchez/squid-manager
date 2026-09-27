"""Helper de ACL externa de Squid para listas de bloqueo de dominios
(squid/domain_block_helper.py).

Standalone respecto al backend a propósito (corre con el python3 del
sistema, sin el venv del backend): se importa como script suelto, mismo
patrón que test_ldap_group_helper.py.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

from app.services import domain_index_service

if sys.platform == "win32":
    pytest.skip(
        "squid/domain_block_helper.py importa el módulo syslog (exclusivo de Unix)",
        allow_module_level=True,
    )


def _raiz_del_proyecto() -> Path | None:
    for base in Path(__file__).resolve().parents:
        if (base / "squid" / "domain_block_helper.py").is_file():
            return base
    return None


def _cargar_modulo(db_path):
    raiz = _raiz_del_proyecto()
    assert raiz, "no se encontró squid/domain_block_helper.py"
    ruta = raiz / "squid" / "domain_block_helper.py"

    spec = importlib.util.spec_from_file_location("domain_block_helper", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.DB_PATH = str(db_path)
    return mod


def _sembrar(db_path, monkeypatch, categoria, dominios):
    """Construye el índice con el mismo camino que usa producción
    (domain_index_service, en modo WAL) -no una tabla armada a mano-: un
    bug real se coló antes porque el test montaba la base sin WAL y el
    helper, con `PRAGMA query_only=1`, fallaba con "attempt to write a
    readonly database" solo contra una base en WAL de verdad."""
    monkeypatch.setattr(domain_index_service, "DB_PATH", Path(db_path))
    domain_index_service.index_category(categoria, dominios, "hash-de-prueba")


def test_match_exacto(tmp_path, monkeypatch):
    db_path = tmp_path / "domain_index.db"
    _sembrar(db_path, monkeypatch, "cat", ["foo.com"])
    mod = _cargar_modulo(db_path)

    assert mod.domain_blocked("cat", "foo.com") is True
    assert mod.domain_blocked("cat", "sub.foo.com") is False


def test_match_de_subdominio(tmp_path, monkeypatch):
    db_path = tmp_path / "domain_index.db"
    _sembrar(db_path, monkeypatch, "cat", [".foo.com"])
    mod = _cargar_modulo(db_path)

    assert mod.domain_blocked("cat", "foo.com") is True
    assert mod.domain_blocked("cat", "sub.foo.com") is True
    assert mod.domain_blocked("cat", "otro.com") is False


def test_categoria_inexistente_no_bloquea(tmp_path, monkeypatch):
    db_path = tmp_path / "domain_index.db"
    _sembrar(db_path, monkeypatch, "cat", ["foo.com"])
    mod = _cargar_modulo(db_path)

    assert mod.domain_blocked("otra_categoria", "foo.com") is False


def test_indice_inexistente_no_rompe_ni_bloquea(tmp_path):
    """El índice puede no existir todavía (instalación recién actualizada,
    antes del primer 'Aplicar cambios'): el helper no debe reventar, y
    dejar pasar es más seguro que bloquear todo el tráfico a ciegas."""
    db_path = tmp_path / "no_existe.db"
    mod = _cargar_modulo(db_path)

    assert mod.domain_blocked("cat", "foo.com") is False


def test_handle_protocolo_linea_completa(tmp_path, monkeypatch):
    db_path = tmp_path / "domain_index.db"
    _sembrar(db_path, monkeypatch, "hagezi_gambling", ["casino.com"])
    mod = _cargar_modulo(db_path)

    # message= queda disponible como %o en la página de error personalizada
    # (deny_info, ver config_generator.py): el "motivo" que ve el usuario
    # bloqueado nombra la categoría real, no un texto genérico.
    assert mod.handle("casino.com hagezi_gambling") == 'OK message="hagezi_gambling"'
    assert mod.handle("otrositio.com hagezi_gambling") == "ERR"
    assert mod.handle("solo-un-campo") == "ERR"


def test_consulta_funciona_con_un_indice_de_verdad_grande(tmp_path, monkeypatch):
    """Con una lista de tamaño real (no solo 1-2 dominios como el resto de
    estos tests) se ejercita el mismo archivo WAL con el que se topó un bug
    real en producción, 2026-09-27: el helper fallaba con "attempt to write
    a readonly database" en cada consulta contra el índice de ~5.9M
    dominios recién construido -causa: un PRAGMA query_only=1 en la
    conexión del helper, que en ciertas condiciones de WAL choca con una
    operación de mantenimiento interna que ni siquiera es un INSERT/UPDATE
    de verdad. No se logró reproducir la condición exacta (concurrencia
    entre el escritor y varios hijos del helper arrancando a la vez) en un
    test aislado de un solo proceso -de ahí que el fix se documente en el
    propio código, no solo acá-, pero este test sí cubre que consultar un
    índice grande sigue devolviendo lo correcto."""
    db_path = tmp_path / "domain_index.db"
    muchos_dominios = [f"sitio{i}.example.com" for i in range(200_000)]
    _sembrar(db_path, monkeypatch, "cat_grande", muchos_dominios)
    mod = _cargar_modulo(db_path)

    assert mod.domain_blocked("cat_grande", "sitio199999.example.com") is True
    assert mod.domain_blocked("cat_grande", "no-esta-en-la-lista.example.com") is False


def test_indice_corrupto_no_bloquea_y_no_muere(tmp_path):
    """Un índice corrupto o momentáneamente inconsistente (una reescritura a
    mitad, un disco lleno) no debería tumbar el helper -Squid lo marcaría
    caído y dejaría de resolver la ACL para todo el mundo- ni bloquear todo
    el tráfico a ciegas: se deja pasar y se registra el error."""
    db_path = tmp_path / "domain_index.db"
    db_path.write_text("esto no es una base de datos SQLite válida")
    mod = _cargar_modulo(db_path)

    assert mod.domain_blocked("cat", "foo.com") is False
    # Una segunda consulta, tras el fallo, tampoco debería morir.
    assert mod.domain_blocked("cat", "otro.com") is False
