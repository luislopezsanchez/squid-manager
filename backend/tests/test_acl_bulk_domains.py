"""Carga masiva de dominios para ACLs (blocklists grandes).

Una lista de miles de dominios no se escribe inline en squid.conf -sería
una sola línea de decenas de miles de caracteres-: por encima de un umbral
pasa a 'file', un archivo aparte que Squid lee directo (ver
squid_service.build_acl_list_files). Por debajo del umbral sigue siendo una
ACL normal, 'inline', igual que cualquiera creada a mano.
"""

from pathlib import Path

import pytest

from app.services.squid_names import validar_lista_dominios, MAX_DOMINIOS_POR_CARGA
from app.services import squid_service


# --- Validación de la lista ------------------------------------------------

def test_acepta_dominios_simples_y_con_punto_inicial():
    validos, rechazados = validar_lista_dominios([".facebook.com", "instagram.com"])
    assert validos == [".facebook.com", "instagram.com"]
    assert rechazados == []


def test_ignora_lineas_vacias_y_comentarios():
    validos, _ = validar_lista_dominios(["", "  ", "#comentario", "ads.example.com"])
    assert validos == ["ads.example.com"]


def test_deduplica_sin_importar_mayusculas():
    validos, _ = validar_lista_dominios(["Ads.Example.com", "ads.example.com"])
    assert len(validos) == 1


def test_rechaza_lineas_que_no_parecen_dominio():
    """Sin esto, una línea con un salto disfrazado o un espacio podría
    colarse en el archivo de la ACL y romper el formato esperado por
    Squid -o peor, inyectar algo en otro lado si algún día se reusara este
    valor en otro contexto."""
    validos, rechazados = validar_lista_dominios([
        "dominio valido.com",  # espacio
        "algo#raro.com",
        "correcto.com",
    ])
    assert validos == ["correcto.com"]
    assert len(rechazados) == 2


def test_rechaza_dominio_demasiado_largo():
    largo = "a" * 260 + ".com"
    validos, rechazados = validar_lista_dominios([largo])
    assert validos == []
    assert rechazados == [largo]


def test_conserva_el_orden_de_aparicion():
    validos, _ = validar_lista_dominios(["c.com", "a.com", "b.com"])
    assert validos == ["c.com", "a.com", "b.com"]


# --- Generación de squid.conf: ACL 'file' vs 'inline' -----------------------

def test_acl_file_referencia_el_archivo_no_el_valor_inline():
    from test_config_generator import FakeDB, FakeSetting
    from app.services.config_generator import generate_squid_config

    config = generate_squid_config(FakeDB(
        settings=[FakeSetting("http_port", "3128", "network")],
        acls=[__import__("test_config_generator").FakeAcl(
            "blocklist", "dstdomain", "ads1.com\nads2.com", source="file",
        )],
    ))
    assert 'acl blocklist dstdomain "/etc/squid/acl_lists/blocklist.txt"' in config
    assert "ads1.com" not in config  # el valor no va inline


def test_acl_sni_file_tampoco_emite_el_valor_inline():
    """Bug real encontrado por el test de arriba: el bloque SNI (SSL Bump)
    duplica dstdomain/dstdom_regex para HTTPS con su propio 'acl sni_...',
    y ese bloque tenía su PROPIA referencia directa a acl.value -sin pasar
    por el cambio de 'file'-, así que una blocklist grande igual terminaba
    entera en una línea, ahora en el bloque SNI en vez del principal."""
    from test_config_generator import FakeDB, FakeSetting, FakeAcl
    from app.services.config_generator import generate_squid_config

    config = generate_squid_config(FakeDB(
        settings=[FakeSetting("http_port", "3128", "network")],
        acls=[FakeAcl("blocklist", "dstdomain", "ads1.com\nads2.com", source="file")],
    ))
    assert 'acl sni_blocklist ssl::server_name "/etc/squid/acl_lists/blocklist.txt"' in config
    assert "ads1.com" not in config
    assert "ads2.com" not in config


def test_acl_inline_sigue_igual_que_siempre():
    from test_config_generator import FakeDB, FakeSetting, FakeAcl
    from app.services.config_generator import generate_squid_config

    config = generate_squid_config(FakeDB(
        settings=[FakeSetting("http_port", "3128", "network")],
        acls=[FakeAcl("redes", "dstdomain", ".facebook.com .instagram.com")],
    ))
    assert "acl redes dstdomain .facebook.com .instagram.com" in config


# --- build_acl_list_files: escritura y limpieza -----------------------------

class _FakeAclRow:
    def __init__(self, name, value, source="file"):
        self.name = name
        self.value = value
        self.source = source


class _FakeQuery:
    def __init__(self, items):
        self._items = items

    def filter(self, *a, **k):
        return self

    def all(self):
        return self._items


class _FakeDBAcls:
    def __init__(self, acls):
        self._acls = acls

    def query(self, model):
        return _FakeQuery(self._acls)


def test_build_acl_list_files_escribe_un_dominio_por_linea(tmp_path, monkeypatch):
    monkeypatch.setattr(squid_service, "ACL_LISTS_DIR", tmp_path)
    db = _FakeDBAcls([_FakeAclRow("blocklist", "ads1.com\nads2.com\n")])

    squid_service.build_acl_list_files(db)

    contenido = (tmp_path / "blocklist.txt").read_text()
    assert contenido == "ads1.com\nads2.com\n"


def test_build_acl_list_files_borra_sobrantes(tmp_path, monkeypatch):
    monkeypatch.setattr(squid_service, "ACL_LISTS_DIR", tmp_path)
    (tmp_path / "vieja.txt").write_text("resto.de.una.acl.borrada.com\n")

    db = _FakeDBAcls([_FakeAclRow("nueva", "sitio.com")])
    squid_service.build_acl_list_files(db)

    assert not (tmp_path / "vieja.txt").exists()
    assert (tmp_path / "nueva.txt").exists()


def test_build_acl_list_files_no_toca_lo_que_sigue_vigente(tmp_path, monkeypatch):
    monkeypatch.setattr(squid_service, "ACL_LISTS_DIR", tmp_path)
    db = _FakeDBAcls([_FakeAclRow("blocklist", "a.com")])

    squid_service.build_acl_list_files(db)
    squid_service.build_acl_list_files(db)  # segunda pasada, mismo resultado

    assert (tmp_path / "blocklist.txt").read_text() == "a.com\n"


def test_apply_escribe_los_archivos_de_acl_antes_de_validar():
    """Bug real encontrado en vivo: Squid abre el archivo de una ACL
    dstdomain/dstdom_regex AL PARSEAR la config, no en caliente como el
    helper de auth con squid_passwd. Si build_acl_list_files() se llama
    DESPUÉS de validate_squid_config(), la primera vez que se crea una ACL
    así la validación fallaba con "Can not open file ... for reading"
    aunque la config generada fuera perfectamente válida."""
    import inspect

    fuente = inspect.getsource(squid_service._apply_squid_config)
    pos_build = fuente.index("build_acl_list_files(db)")
    pos_validate = fuente.index("validate_squid_config(config_text)")
    assert pos_build < pos_validate


def test_umbral_definido_y_razonable():
    """Solo para que un cambio accidental de MAX_DOMINIOS_POR_CARGA no pase
    inadvertido: es el techo de una carga, no del total de ACLs."""
    assert MAX_DOMINIOS_POR_CARGA >= 10_000
