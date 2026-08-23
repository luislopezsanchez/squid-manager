"""Tests del generador de squid.conf (Jinja2)."""

import pytest
from app.services.config_generator import generate_squid_config


class FakeSetting:
    def __init__(self, key, value, category="general", description=""):
        self.key = key
        self.value = value
        self.category = category
        self.description = description


class FakeAcl:
    def __init__(self, name, type_, value, enabled=True, description=""):
        self.name = name
        self.type = type_
        self.value = value
        self.enabled = enabled
        self.description = description


class FakeRule:
    def __init__(self, action, acl_names, order, enabled=True, description=""):
        self.action = action
        self.acl_names = acl_names
        self.order = order
        self.enabled = enabled
        self.description = description


class FakeUser:
    def __init__(self, username, enabled=True):
        self.username = username
        self.enabled = enabled


class FakeDelayPool:
    def __init__(self, pool_class, parameters, acl_name="", enabled=True):
        self.pool_class = pool_class
        self.parameters = parameters
        self.acl_name = acl_name
        self.enabled = enabled


class FakeLdap:
    def __init__(self, enabled=False, server_url="", bind_dn="", search_base="", user_filter="(uid=%s)"):
        self.enabled = enabled
        self.server_url = server_url
        self.bind_dn = bind_dn
        self.search_base = search_base
        self.user_filter = user_filter


class FakeDB:
    """Simula una sesión SQLAlchemy con queries básicas."""

    def __init__(self, settings=None, acls=None, rules=None, users=None, delay_pools=None, ldap=None):
        self._settings = settings or []
        self._acls = acls or []
        self._rules = rules or []
        self._users = users or []
        self._delay_pools = delay_pools or []
        self._ldap = ldap

    def query(self, model):
        name = model.__name__ if hasattr(model, "__name__") else str(model)
        if name == "SquidSetting":
            return self._FakeQuery(self._settings)
        elif name == "Acl":
            return self._FakeQuery(self._acls)
        elif name == "AccessRule":
            return self._FakeQuery(self._rules)
        elif name == "ProxyUser":
            return self._FakeQuery(self._users)
        elif name == "DelayPool":
            return self._FakeQuery(self._delay_pools)
        elif name == "LdapConfig":
            return self._FakeQuery([self._ldap] if self._ldap else [])
        return self._FakeQuery([])

    class _FakeQuery:
        def __init__(self, items):
            self._items = items

        def all(self):
            return self._items

        def filter(self, *args):
            # Ignoramos filtros en los tests (simulan datos ya filtrados)
            return self

        def order_by(self, *args):
            return self

        def first(self):
            return self._items[0] if self._items else None


def test_generate_basic_config():
    db = FakeDB(
        settings=[FakeSetting("http_port", "3128", "network")],
        acls=[FakeAcl("redes_sociales", "dstdomain", ".facebook.com")],
        rules=[FakeRule("deny", "redes_sociales", 0)],
    )
    config = generate_squid_config(db)
    assert "http_port 3128" in config
    assert "acl redes_sociales dstdomain .facebook.com" in config
    assert "http_access deny redes_sociales" in config


def test_generate_ssl_bump_config():
    db = FakeDB(
        settings=[FakeSetting("http_port", "3128", "network")],
        acls=[FakeAcl("redes_sociales", "dstdomain", ".facebook.com")],
        rules=[FakeRule("deny", "redes_sociales", 0)],
    )
    config = generate_squid_config(db)
    # SSL Bump debe generar terminate por SNI para ACLs dstdomain deny
    assert "ssl_bump" in config.lower()
    assert "sni_redes_sociales" in config
    assert "ssl_bump terminate" in config


def test_generate_delay_pools():
    db = FakeDB(
        settings=[FakeSetting("http_port", "3128", "network")],
        delay_pools=[FakeDelayPool(2, "64000/64000 64000/32000")],
    )
    config = generate_squid_config(db)
    assert "delay_pools 1" in config
    assert "delay_class 1 2" in config
    assert "delay_parameters 1 64000/64000 64000/32000" in config


def test_generate_empty_config():
    db = FakeDB()
    config = generate_squid_config(db)
    assert "http_port" in config  # al menos el puerto por defecto


class FakeGroup:
    def __init__(self, name, description=""):
        self.id = abs(hash(name)) % 1000
        self.name = name
        self.description = description


def test_el_orden_de_las_reglas_se_respeta():
    """Las reglas salen en el orden del panel.

    La versión anterior extraía las reglas «deny <grupo>» del flujo y las
    refundía al final, con lo que el orden mostrado dejaba de significar nada.
    """
    db = FakeDB(
        settings=[FakeSetting("http_port", "3128", "network")],
        acls=[FakeAcl("uy_domains", "dstdomain", ".uy")],
        rules=[
            FakeRule("allow", "Nacional uy_domains", 0),
            FakeRule("deny", "Nacional", 1),
        ],
    )
    config = generate_squid_config(db)
    pos_allow = config.index("http_access allow Nacional uy_domains")
    pos_deny = config.index("http_access deny Nacional")
    assert pos_allow < pos_deny


def test_se_fuerza_la_autenticacion_antes_de_las_reglas():
    """`deny !authenticated` va antes: así un deny de grupo da 403 y no 407."""
    db = FakeDB(
        settings=[FakeSetting("http_port", "3128", "network")],
        rules=[FakeRule("deny", "Nacional", 0)],
    )
    config = generate_squid_config(db)
    assert "http_access deny !authenticated" in config
    assert config.index("deny !authenticated") < config.index("http_access deny Nacional")


def test_regla_sni_paralela_para_reglas_con_varias_acls():
    """Con varias ACLs en la misma regla también se genera la paralela por SNI.

    Antes se comparaba el campo entero con el nombre de una ACL, así que en
    cuanto la regla combinaba dos condiciones no se generaba nada para HTTPS.
    """
    db = FakeDB(
        settings=[FakeSetting("http_port", "3128", "network")],
        acls=[
            FakeAcl("redes_sociales", "dstdomain", ".facebook.com"),
            FakeAcl("horario", "time", "M-F 09:00-17:00"),
        ],
        rules=[FakeRule("deny", "redes_sociales horario", 0)],
    )
    config = generate_squid_config(db)
    assert "http_access deny sni_redes_sociales horario" in config
    assert "ssl_bump terminate step2 sni_redes_sociales" in config


def test_dominios_excluidos_del_descifrado():
    """Los dominios excluidos se hacen splice antes del bump."""
    db = FakeDB(
        settings=[
            FakeSetting("http_port", "3128", "network"),
            FakeSetting("ssl_bump_exclude", ".banco.com .salud.gob", "security"),
        ],
    )
    config = generate_squid_config(db)
    assert "acl ssl_exclude ssl::server_name .banco.com .salud.gob" in config
    assert config.index("ssl_bump splice step2 ssl_exclude") < config.index("ssl_bump bump step3 all")


def test_store_log_desactivado_por_defecto():
    """store.log escribe mucho y no lo consume nadie."""
    db = FakeDB(settings=[FakeSetting("http_port", "3128", "network")])
    config = generate_squid_config(db)
    assert "cache_store_log none" in config


def test_rutas_de_log_con_prefijo_stdio():
    db = FakeDB(settings=[FakeSetting("http_port", "3128", "network")])
    config = generate_squid_config(db)
    assert "access_log stdio:/var/log/squid/access.log" in config


def test_idioma_de_las_paginas_de_error():
    db = FakeDB(settings=[FakeSetting("http_port", "3128", "network")])
    config = generate_squid_config(db)
    assert "error_default_language es" in config


def test_base_de_certificados_en_el_volumen_persistente():
    """La base vivía en /tmp y se perdía en cada reinicio del contenedor."""
    db = FakeDB(settings=[FakeSetting("http_port", "3128", "network")])
    config = generate_squid_config(db)
    assert "-s /var/lib/ssl_crtd/db" in config
    assert "/tmp/ssl_crtd" not in config
