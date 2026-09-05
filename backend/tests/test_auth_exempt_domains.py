"""Pruebas de los dominios exentos de autenticación por destino.

Igual que los orígenes de confianza, es una exención de autenticación: un
valor mal escrito no da un error visible, deja pasar sin credenciales a
cualquiera que apunte a ese dominio.
"""

import pytest

from app.services.auth_exempt_service import parsear_lista, validar_dominios


@pytest.mark.parametrize("entrada,esperado", [
    ("windowsupdate.com", ["windowsupdate.com"]),
    ("windowsupdate.com .office.com", ["windowsupdate.com", ".office.com"]),
    ("windowsupdate.com,office.com", ["windowsupdate.com", "office.com"]),
    ("windowsupdate.com\noffice.com", ["windowsupdate.com", "office.com"]),
    ("", []),
    (None, []),
])
def test_parsear(entrada, esperado):
    assert parsear_lista(entrada) == esperado


def test_acepta_dominio_y_subdominio_con_punto():
    ok, _ = validar_dominios(["windowsupdate.com", ".office.com"])
    assert ok


@pytest.mark.parametrize("comodin", ["", ".", "*", ".*"])
def test_rechaza_comodines_que_exentarian_todo(comodin):
    ok, mensaje = validar_dominios([comodin])
    assert not ok
    assert "CUALQUIER destino" in mensaje


def test_una_entrada_mala_invalida_la_lista():
    ok, _ = validar_dominios(["windowsupdate.com", "*"])
    assert not ok


# --- Generación del squid.conf ---------------------------------------------

def test_sin_dominios_exentos_no_aparece_la_acl():
    from test_config_generator import FakeDB, FakeSetting
    from app.services.config_generator import generate_squid_config

    config = generate_squid_config(
        FakeDB(settings=[FakeSetting("http_port", "3128", "network")])
    )
    assert "exentos_auth_dominio" not in config
    assert "http_access deny !authenticated" in config


def test_la_exencion_va_antes_de_exigir_credenciales():
    """Si fuera después, no serviría de nada: nunca se llegaría a evaluar."""
    from test_config_generator import FakeDB, FakeSetting
    from app.services.config_generator import generate_squid_config

    db = FakeDB(settings=[
        FakeSetting("http_port", "3128", "network"),
        FakeSetting("auth_exempt_domains", "windowsupdate.com .office.com", "security"),
    ])
    config = generate_squid_config(db)

    assert "acl exentos_auth_dominio dstdomain windowsupdate.com .office.com" in config

    posicion_exencion = config.index("http_access allow exentos_auth_dominio")
    posicion_deny = config.index("http_access deny !authenticated")
    assert posicion_exencion < posicion_deny, (
        "La exención debe emitirse antes de exigir credenciales"
    )


def test_convive_con_origenes_confianza():
    """Ambas exenciones (por IP de origen y por dominio de destino) coexisten."""
    from test_config_generator import FakeDB, FakeSetting
    from app.services.config_generator import generate_squid_config

    db = FakeDB(settings=[
        FakeSetting("http_port", "3128", "network"),
        FakeSetting("trusted_sources", "203.0.113.10", "security"),
        FakeSetting("auth_exempt_domains", "windowsupdate.com", "security"),
    ])
    config = generate_squid_config(db)

    assert "acl origenes_confianza src 203.0.113.10" in config
    assert "acl exentos_auth_dominio dstdomain windowsupdate.com" in config
