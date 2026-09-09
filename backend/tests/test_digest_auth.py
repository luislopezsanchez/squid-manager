"""Autenticación Digest (RFC 2617): HA1, generación de squid.conf y la
validación de compatibilidad con el modo 'passthru' del proxy padre."""

import hashlib

from app.routes.proxy_users import _generate_digest_ha1


# --- HA1 ---------------------------------------------------------------

def test_ha1_es_md5_de_usuario_realm_password():
    ha1 = _generate_digest_ha1("jperez", "clave123", "SquidManager Proxy")
    esperado = hashlib.md5(b"jperez:SquidManager Proxy:clave123").hexdigest()
    assert ha1 == esperado


def test_ha1_cambia_si_cambia_el_realm():
    """El realm queda horneado en el hash: es la base del chequeo de
    digest_ha1_realm en squid_service.write_digest_file."""
    ha1_a = _generate_digest_ha1("jperez", "clave123", "RealmA")
    ha1_b = _generate_digest_ha1("jperez", "clave123", "RealmB")
    assert ha1_a != ha1_b


# --- Generación del bloque auth_param en squid.conf ---------------------

def test_por_defecto_se_emite_basic_no_digest():
    from test_config_generator import FakeDB, FakeSetting
    from app.services.config_generator import generate_squid_config

    config = generate_squid_config(FakeDB(settings=[FakeSetting("http_port", "3128", "network")]))
    assert "auth_param basic program" in config
    assert "auth_param digest program" not in config


def test_proxy_auth_scheme_digest_reemplaza_basic():
    from test_config_generator import FakeDB, FakeSetting
    from app.services.config_generator import generate_squid_config

    config = generate_squid_config(FakeDB(settings=[
        FakeSetting("http_port", "3128", "network"),
        FakeSetting("proxy_auth_scheme", "digest", "general"),
    ]))
    assert "auth_param digest program /usr/lib/squid/squidmanager_digest_helper" in config
    assert "auth_param basic program" not in config


def test_digest_usa_el_realm_configurado():
    from test_config_generator import FakeDB, FakeSetting
    from app.services.config_generator import generate_squid_config

    config = generate_squid_config(FakeDB(settings=[
        FakeSetting("http_port", "3128", "network"),
        FakeSetting("proxy_auth_scheme", "digest", "general"),
        FakeSetting("auth_realm", "MiEmpresa", "general"),
    ]))
    assert "auth_param digest realm MiEmpresa" in config


# --- cache_peer: fixed vs passthru ---------------------------------------

class FakeParentProxy:
    def __init__(self, auth_method="fixed", username=None, password=None,
                 host="padre.empresa.com", port=3128, enabled=True, never_direct=True,
                 ca_cert=None):
        self.auth_method = auth_method
        self.username = username
        self.password = password
        self.host = host
        self.port = port
        self.enabled = enabled
        self.never_direct = never_direct
        self.direct_domains = None
        self.ca_cert = ca_cert


def _fake_db_con_padre(padre):
    from test_config_generator import FakeDB, FakeSetting

    db = FakeDB(settings=[FakeSetting("http_port", "3128", "network")])
    original_query = db.query

    def query(model):
        name = model.__name__ if hasattr(model, "__name__") else str(model)
        if name == "ParentProxy":
            return db._FakeQuery([padre] if padre else [])
        return original_query(model)

    db.query = query
    return db


def test_padre_fixed_con_credenciales_usa_login_user_pass():
    from app.services.config_generator import generate_squid_config

    padre = FakeParentProxy(auth_method="fixed", username="ana", password="secreta")
    config = generate_squid_config(_fake_db_con_padre(padre))
    assert "login=ana:secreta" in config
    assert "PASSTHRU" not in config


def test_padre_passthru_no_lleva_credenciales_fijas():
    from app.services.config_generator import generate_squid_config

    padre = FakeParentProxy(auth_method="passthru", username="ana", password="secreta")
    config = generate_squid_config(_fake_db_con_padre(padre))
    assert "login=PASSTHRU connection-auth=on" in config
    assert "login=ana:secreta" not in config


# --- Compatibilidad passthru vs auth local -------------------------------

class _FakeQueryVacia:
    def filter(self, *a, **k):
        return self

    def count(self):
        return 0

    def first(self):
        return None


class _FakeDBSinAuthLocal:
    def query(self, model):
        return _FakeQueryVacia()


def test_passthru_compatible_sin_auth_local():
    from app.services.parent_proxy_service import validar_auth_method_compatible

    ok, _ = validar_auth_method_compatible("passthru", _FakeDBSinAuthLocal())
    assert ok


def test_fixed_siempre_compatible():
    from app.services.parent_proxy_service import validar_auth_method_compatible

    ok, _ = validar_auth_method_compatible("fixed", _FakeDBSinAuthLocal())
    assert ok


def test_metodo_desconocido_rechazado():
    from app.services.parent_proxy_service import validar_auth_method_compatible

    ok, mensaje = validar_auth_method_compatible("otra-cosa", _FakeDBSinAuthLocal())
    assert not ok
    assert "no soportado" in mensaje.lower()


def test_passthru_incompatible_con_usuarios_locales():
    from app.services.parent_proxy_service import validar_auth_method_compatible

    class _QueryConUsuarios(_FakeQueryVacia):
        def count(self):
            return 3

    class _DB(_FakeDBSinAuthLocal):
        def query(self, model):
            name = model.__name__ if hasattr(model, "__name__") else str(model)
            if name == "ProxyUser":
                return _QueryConUsuarios()
            return _FakeQueryVacia()

    ok, mensaje = validar_auth_method_compatible("passthru", _DB())
    assert not ok
    assert "usuarios locales" in mensaje.lower()
