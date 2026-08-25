"""Pruebas de los orígenes exentos de autenticación.

Es una exención de autenticación, así que lo que más se cuida es que un valor
mal escrito no pase: aquí un error no da un mensaje visible, deja pasar —o deja
fuera— a quien no toca.
"""

import pytest

from app.services.origenes_service import parsear_lista, validar_origenes


@pytest.mark.parametrize("entrada,esperado", [
    ("203.0.113.10", ["203.0.113.10"]),
    ("203.0.113.10 198.51.100.0/24", ["203.0.113.10", "198.51.100.0/24"]),
    ("203.0.113.10,198.51.100.5", ["203.0.113.10", "198.51.100.5"]),
    ("203.0.113.10\n198.51.100.5", ["203.0.113.10", "198.51.100.5"]),
    ("", []),
    (None, []),
])
def test_parsear(entrada, esperado):
    assert parsear_lista(entrada) == esperado


def test_acepta_ip_suelta_y_red():
    ok, _ = validar_origenes(["203.0.113.10", "198.51.100.0/24", "2001:db8::/32"])
    assert ok


def test_rechaza_un_nombre_de_host():
    ok, mensaje = validar_origenes(["proxy.empresa.local"])
    assert not ok
    assert "proxy.empresa.local" in mensaje


def test_rechaza_una_ip_mal_formada():
    ok, mensaje = validar_origenes(["203.0.113.999"])
    assert not ok
    assert "203.0.113.999" in mensaje


def test_rechaza_abarcar_todo_internet():
    """0.0.0.0/0 dejaria el proxy abierto sin autenticacion."""
    ok, mensaje = validar_origenes(["0.0.0.0/0"])
    assert not ok
    assert "abierto sin autenticación" in mensaje


def test_una_entrada_mala_invalida_la_lista():
    ok, _ = validar_origenes(["203.0.113.10", "no-es-una-ip"])
    assert not ok


# --- Generación del squid.conf ---------------------------------------------

def test_sin_origenes_todos_se_autentican():
    from test_config_generator import FakeDB, FakeSetting
    from app.services.config_generator import generate_squid_config

    config = generate_squid_config(
        FakeDB(settings=[FakeSetting("http_port", "3128", "network")])
    )
    assert "origenes_confianza" not in config
    assert "http_access deny !authenticated" in config


def test_la_exencion_va_antes_de_exigir_credenciales():
    """Si fuera después, no serviría de nada: nunca se llegaría a evaluar."""
    from test_config_generator import FakeDB, FakeSetting
    from app.services.config_generator import generate_squid_config

    db = FakeDB(settings=[
        FakeSetting("http_port", "3128", "network"),
        FakeSetting("trusted_sources", "203.0.113.10", "security"),
    ])
    config = generate_squid_config(db)

    assert "acl origenes_confianza src 203.0.113.10" in config

    posicion_exencion = config.index("http_access allow origenes_confianza")
    posicion_deny = config.index("http_access deny !authenticated")
    assert posicion_exencion < posicion_deny, (
        "La exención debe emitirse antes de exigir credenciales"
    )
