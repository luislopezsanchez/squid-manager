"""Índice SQLite de dominios para el helper externo (app/services/domain_index_service.py).

Cubre la semántica de match que motivó todo el helper -verificada en vivo
contra Squid 6.14, no supuesta, ver squid/domain_block_helper.py-: una
entrada sin punto inicial es match EXACTO; con punto inicial, matchea el
dominio y cualquier subdominio.
"""

from app.services import domain_index_service


def _db(tmp_path, monkeypatch):
    monkeypatch.setattr(domain_index_service, "DB_PATH", tmp_path / "domain_index.db")


def test_entrada_sin_punto_es_match_exacto_unicamente(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    domain_index_service.index_category("cat", ["foo.com"], "hash1")

    conn = domain_index_service._connect()
    assert domain_index_service.matches(conn, "cat", "foo.com")
    assert not domain_index_service.matches(conn, "cat", "sub.foo.com")
    assert not domain_index_service.matches(conn, "cat", "otro.com")


def test_entrada_con_punto_matchea_dominio_y_subdominios(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    domain_index_service.index_category("cat", [".foo.com"], "hash1")

    conn = domain_index_service._connect()
    assert domain_index_service.matches(conn, "cat", "foo.com")
    assert domain_index_service.matches(conn, "cat", "sub.foo.com")
    assert domain_index_service.matches(conn, "cat", "deep.sub.foo.com")
    assert not domain_index_service.matches(conn, "cat", "notfoo.com")


def test_categorias_estan_aisladas(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    domain_index_service.index_category("cat_a", ["foo.com"], "hash_a")
    domain_index_service.index_category("cat_b", ["bar.com"], "hash_b")

    conn = domain_index_service._connect()
    assert domain_index_service.matches(conn, "cat_a", "foo.com")
    assert not domain_index_service.matches(conn, "cat_b", "foo.com")


def test_reindexar_reemplaza_el_contenido_anterior(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    domain_index_service.index_category("cat", ["viejo.com"], "hash1")
    domain_index_service.index_category("cat", ["nuevo.com"], "hash2")

    conn = domain_index_service._connect()
    assert not domain_index_service.matches(conn, "cat", "viejo.com")
    assert domain_index_service.matches(conn, "cat", "nuevo.com")


def test_mayusculas_y_punto_final_se_normalizan(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    domain_index_service.index_category("cat", ["foo.com"], "hash1")

    conn = domain_index_service._connect()
    assert domain_index_service.matches(conn, "cat", "FOO.COM")
    assert domain_index_service.matches(conn, "cat", "foo.com.")  # FQDN con punto final


def test_categoria_indexada_al_dia_compara_el_hash(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    assert not domain_index_service.categoria_indexada_al_dia("cat", "hash1")

    domain_index_service.index_category("cat", ["foo.com"], "hash1")
    assert domain_index_service.categoria_indexada_al_dia("cat", "hash1")
    assert not domain_index_service.categoria_indexada_al_dia("cat", "hash2")


def test_remove_category_borra_todo(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    domain_index_service.index_category("cat", ["foo.com"], "hash1")
    domain_index_service.remove_category("cat")

    conn = domain_index_service._connect()
    assert not domain_index_service.matches(conn, "cat", "foo.com")
    assert not domain_index_service.categoria_indexada_al_dia("cat", "hash1")
    assert "cat" not in domain_index_service.categorias_indexadas()


def test_content_hash_mismo_criterio_que_hash_domain_list():
    """No debería divergir del hash que ya guarda Acl.content_hash (ver
    hash_domain_list en squid_service.py): si difiriera, categoria_indexada_al_dia
    nunca daría 'al día' con el hash real que trae la fila de la ACL."""
    from app.services.squid_service import hash_domain_list

    dominios = ["foo.com", ".bar.com", "baz.com"]
    assert domain_index_service.content_hash(dominios) == hash_domain_list(dominios)
