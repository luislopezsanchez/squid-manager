"""Que cada instalación se identifique con un nombre propio.

Squid añade su `visible_hostname` a la cabecera `Via` al reenviar, y rechaza
como bucle de reenvío cualquier petición que ya lleve el suyo. Cuando todas las
instalaciones se llamaban igual, dos SquidManager encadenados se cortaban entre
sí con un `403 Acceso Denegado` que no mencionaba la causa.

El síntoma despistaba: HTTP fallaba y HTTPS funcionaba, porque el tráfico HTTPS
viaja dentro del túnel y esa cabecera no se inspecciona.
"""

import re
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent


def test_el_nombre_por_defecto_no_es_fijo():
    """Guardia contra la regresión: si vuelve a ser fijo, vuelve el bucle."""
    fuente = (BACKEND_DIR / "app" / "main.py").read_text()

    bloque = re.search(
        r'"visible_hostname":\s*\((.*?)\),\s*\n', fuente, re.DOTALL
    )
    assert bloque, "no se encontro el ajuste visible_hostname en seed_data"

    definicion = bloque.group(1)
    assert "token_hex" in definicion or "uuid" in definicion, (
        "visible_hostname debe llevar un sufijo unico por instalacion: con un "
        "valor fijo, dos SquidManager encadenados se rechazan como bucle."
    )


def test_el_nombre_llega_al_squid_conf():
    from test_config_generator import FakeDB, FakeSetting
    from app.services.config_generator import generate_squid_config

    db = FakeDB(settings=[
        FakeSetting("http_port", "3128", "network"),
        FakeSetting("visible_hostname", "squidmanager-oficina", "general"),
    ])
    assert "visible_hostname squidmanager-oficina" in generate_squid_config(db)
