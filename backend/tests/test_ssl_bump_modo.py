"""Pruebas de poder desactivar la interceptación de HTTPS.

Squid solo puede interceptar HTTPS una vez en una cadena de proxies. Si este
sale a través de otro que también intercepta, el de arriba recibe la petición
descifrada dentro de un túnel que él mismo cifró y la rechaza con un 403 que no
explica nada. Comprobado encadenando dos SquidManager: el CONNECT se aceptaba y
la petición de dentro se denegaba.
"""

from test_config_generator import FakeDB, FakeSetting
from app.services.config_generator import generate_squid_config


def _config(**ajustes):
    base = [FakeSetting("http_port", "3128", "network")]
    base += [FakeSetting(k, v, "security") for k, v in ajustes.items()]
    return generate_squid_config(FakeDB(settings=base))


def test_por_defecto_se_intercepta():
    """El comportamiento de siempre: sin el ajuste, se intercepta."""
    config = _config()
    assert "ssl_bump bump step3 all" in config
    assert "ssl_bump splice all" not in config


def test_activado_explicitamente():
    config = _config(ssl_bump_enabled="true")
    assert "ssl_bump bump step3 all" in config


def test_desactivado_solo_tuneliza():
    """Lo que hace falta al salir por otro proxy que ya intercepta."""
    config = _config(ssl_bump_enabled="false")
    assert "ssl_bump splice all" in config
    assert "ssl_bump bump step3 all" not in config
    assert "ssl_bump stare step2 all" not in config


def test_admite_varias_formas_de_apagarlo():
    for valor in ("false", "False", "FALSE", "0", "no", "off", " false "):
        config = _config(ssl_bump_enabled=valor)
        assert "ssl_bump splice all" in config, f"con «{valor}» deberia tunelizar"


def test_un_valor_raro_no_apaga_la_interceptacion():
    """Ante la duda, se mantiene el filtrado en lugar de perderlo en silencio."""
    config = _config(ssl_bump_enabled="quizas")
    assert "ssl_bump bump step3 all" in config


def test_sin_interceptar_el_puerto_sigue_aceptando_tls():
    """http_port conserva ssl-bump: sin eso Squid no sabria tunelizar TLS."""
    config = _config(ssl_bump_enabled="false")
    assert "ssl-bump" in config
    assert "sslcrtd_program" in config
