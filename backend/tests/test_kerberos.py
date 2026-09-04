"""Pruebas de la autenticación Negotiate (Kerberos/SPNEGO) contra AD."""

from app.services.kerberos_service import validar_keytab


# --- Validación del archivo subido ------------------------------------------

def test_rechaza_archivo_vacio():
    ok, mensaje = validar_keytab(b"")
    assert not ok
    assert "vacío" in mensaje


def test_rechaza_archivo_sin_cabecera_de_keytab():
    ok, mensaje = validar_keytab(b"esto no es un keytab, es texto plano")
    assert not ok
    assert "keytab" in mensaje.lower()


def test_acepta_cabecera_de_keytab_valida():
    # Cabecera real de un keytab v5: 0x05 0x02 + resto de entradas.
    ok, _ = validar_keytab(b"\x05\x02" + b"\x00" * 20)
    assert ok


# --- Generación del bloque negotiate en squid.conf --------------------------

class FakeKerberos:
    def __init__(self, enabled=True, realm="EMPRESA.LOCAL", proxy_fqdn="proxy.empresa.local",
                 keytab_data=b"\x05\x02algo"):
        self.enabled = enabled
        self.realm = realm
        self.proxy_fqdn = proxy_fqdn
        self.keytab_data = keytab_data


def _fake_db_con_kerberos(kerberos):
    from test_config_generator import FakeDB, FakeSetting

    db = FakeDB(settings=[FakeSetting("http_port", "3128", "network")])
    original_query = db.query

    def query(model):
        name = model.__name__ if hasattr(model, "__name__") else str(model)
        if name == "KerberosConfig":
            return db._FakeQuery([kerberos] if kerberos else [])
        return original_query(model)

    db.query = query
    return db


def test_sin_kerberos_configurado_no_se_emite_negotiate():
    from app.services.config_generator import generate_squid_config

    config = generate_squid_config(_fake_db_con_kerberos(None))
    assert "auth_param negotiate" not in config


def test_kerberos_activado_sin_keytab_no_se_emite_negotiate():
    """Sin keytab, apuntar al helper tumbaría la autenticación entera al primer intento."""
    from app.services.config_generator import generate_squid_config

    kerberos = FakeKerberos(enabled=True, keytab_data=None)
    config = generate_squid_config(_fake_db_con_kerberos(kerberos))
    assert "auth_param negotiate" not in config


def test_kerberos_deshabilitado_con_keytab_no_se_emite_negotiate():
    from app.services.config_generator import generate_squid_config

    kerberos = FakeKerberos(enabled=False)
    config = generate_squid_config(_fake_db_con_kerberos(kerberos))
    assert "auth_param negotiate" not in config


def test_kerberos_activado_con_keytab_emite_negotiate_antes_que_basic():
    from app.services.config_generator import generate_squid_config

    kerberos = FakeKerberos(enabled=True, realm="EMPRESA.LOCAL", proxy_fqdn="proxy.empresa.local")
    config = generate_squid_config(_fake_db_con_kerberos(kerberos))
    assert "auth_param negotiate program /usr/lib/squid/negotiate_kerberos_auth" in config
    assert "-s HTTP/proxy.empresa.local@EMPRESA.LOCAL" in config
    assert "-k /etc/squid/HTTP.keytab" in config
    # Basic tiene que seguir presente: Kerberos convive, no reemplaza.
    assert "auth_param basic program" in config
    assert config.index("auth_param negotiate") < config.index("auth_param basic")
