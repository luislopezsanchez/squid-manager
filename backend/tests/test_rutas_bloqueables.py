"""El panel no puede depender de rutas que un bloqueador vaya a cortar.

El caso real: `/api/metrics/dashboard` contiene «metrics», una palabra que los
bloqueadores de anuncios y los filtros de privacidad (uBlock, AdGuard, los
escudos de Brave) cortan por defecto porque la asocian a telemetría. La
petición no llegaba a salir del navegador, así que en el servidor no quedaba
ni rastro —cero líneas en el log de nginx— y el dashboard se quedaba
«Cargando métricas…» para siempre sin que nada explicara por qué.

Quien administra un proxy es justo quien suele llevar bloqueador, así que no
era un caso raro. Estas pruebas fijan las dos mitades de la solución: que
existe una ruta alternativa que ningún filtro toca, y que la original sigue
ahí para quien ya consuma la API desde fuera.
"""

import re
from pathlib import Path

import pytest

from app.main import app


# Palabras que las listas de filtros habituales cortan por su nombre. Se
# comprueban solo contra lo que usa el PANEL: la API pública puede ofrecer
# `/api/metrics` sin problema, porque quien la consume no es un navegador con
# extensiones.
PALABRAS_BLOQUEADAS = ("metrics", "analytics", "telemetry", "tracking", "adserver")


def _rutas_de_la_app() -> list[str]:
    return [r.path for r in app.routes if hasattr(r, "path")]


def test_existe_la_ruta_alternativa_del_panel():
    rutas = _rutas_de_la_app()
    assert "/api/panel/dashboard" in rutas


def test_la_ruta_original_sigue_disponible():
    """No se rompe a quien ya consuma /api/metrics desde fuera."""
    rutas = _rutas_de_la_app()
    assert "/api/metrics/dashboard" in rutas


def test_las_dos_rutas_ofrecen_lo_mismo():
    rutas = set(_rutas_de_la_app())
    bajo_metrics = {r[len("/api/metrics"):] for r in rutas if r.startswith("/api/metrics")}
    bajo_panel = {r[len("/api/panel"):] for r in rutas if r.startswith("/api/panel")}
    assert bajo_metrics == bajo_panel, (
        "las dos rutas deben servir los mismos endpoints; "
        f"solo en metrics: {bajo_metrics - bajo_panel}, "
        f"solo en panel: {bajo_panel - bajo_metrics}"
    )


def _cliente_del_frontend() -> Path | None:
    """Localiza el cliente de la API del panel, si el frontend está presente."""
    for base in Path(__file__).resolve().parents:
        candidato = base / "frontend" / "src" / "api" / "client.ts"
        if candidato.is_file():
            return candidato
    return None


def test_el_panel_no_pide_ninguna_ruta_bloqueable():
    """La prueba que habría evitado el fallo: mirar lo que pide el navegador."""
    cliente = _cliente_del_frontend()
    if cliente is None:
        pytest.skip("el frontend no está disponible junto al backend")

    texto = cliente.read_text(encoding="utf-8")
    # Solo las rutas que se piden de verdad: request('/loquesea'). Los
    # comentarios que expliquen el problema no cuentan.
    llamadas = re.findall(r"request<[^>]*>\(\s*[`'\"]([^`'\"]+)", texto)
    assert llamadas, "no se encontró ninguna llamada en el cliente de la API"

    culpables = [
        ruta for ruta in llamadas
        if any(p in ruta.lower() for p in PALABRAS_BLOQUEADAS)
    ]
    assert not culpables, (
        "el panel pide rutas que un bloqueador puede cortar sin dejar rastro "
        f"en el servidor: {culpables}"
    )
