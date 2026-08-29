"""Pruebas de la traducción de los mensajes del backend.

Lo que se protege aquí es la propiedad que hace utilizable una traducción
incompleta: un mensaje que no esté en el diccionario debe salir en español, no
desaparecer ni convertirse en un identificador. Con esa garantía se puede
publicar con el 90 % traducido; sin ella, cada hueco es un error visible.
"""

import pytest

from app.i18n import IDIOMAS_SOPORTADOS, TRADUCCIONES, idioma_de_cabecera, traducir


# ---------------------------------------------------------------------------
# Elección del idioma a partir de la cabecera
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "cabecera,esperado",
    [
        ("en", "en"),
        ("pt", "pt"),
        ("es", "es"),
        # El panel manda un único código; un navegador manda su lista entera.
        ("en-US,en;q=0.9,es;q=0.8", "en"),
        ("pt-BR,pt;q=0.9", "pt"),
        # Regionales que comparten diccionario.
        ("es-AR", "es"),
        # Sin cabecera, o con un idioma que no se soporta: español.
        (None, "es"),
        ("", "es"),
        ("de,fr;q=0.9", "es"),
    ],
)
def test_idioma_de_cabecera(cabecera, esperado):
    assert idioma_de_cabecera(cabecera) == esperado


def test_se_escoge_el_primer_idioma_conocido_de_la_lista():
    """Un navegador en alemán con español de reserva debe recibir español."""
    assert idioma_de_cabecera("de-DE,de;q=0.9,es;q=0.7") == "es"


# ---------------------------------------------------------------------------
# Traducción
# ---------------------------------------------------------------------------
def test_traduce_un_mensaje_conocido():
    assert traducir("Usuario no encontrado", "en") == "User not found"
    assert traducir("Usuario no encontrado", "pt") == "Usuário não encontrado"


def test_en_espanol_devuelve_el_original():
    assert traducir("Usuario no encontrado", "es") == "Usuario no encontrado"


def test_un_mensaje_sin_traducir_sale_en_espanol():
    """La garantía que permite publicar con la traducción a medias."""
    original = "Un mensaje que nadie ha traducido todavía"
    assert traducir(original, "en") == original
    assert traducir(original, "pt") == original


def test_un_idioma_desconocido_no_rompe():
    assert traducir("Usuario no encontrado", "de") == "Usuario no encontrado"


# ---------------------------------------------------------------------------
# Coherencia del diccionario
# ---------------------------------------------------------------------------
def test_los_dos_idiomas_cubren_los_mismos_mensajes():
    """Un mensaje traducido a un idioma y no al otro es casi siempre un olvido."""
    solo_en = set(TRADUCCIONES["en"]) - set(TRADUCCIONES["pt"])
    solo_pt = set(TRADUCCIONES["pt"]) - set(TRADUCCIONES["en"])
    assert not solo_en, f"traducidos al inglés pero no al portugués: {sorted(solo_en)}"
    assert not solo_pt, f"traducidos al portugués pero no al inglés: {sorted(solo_pt)}"


def test_ninguna_traduccion_esta_vacia():
    for idioma, diccionario in TRADUCCIONES.items():
        vacias = [k for k, v in diccionario.items() if not v.strip()]
        assert not vacias, f"{idioma}: traducciones vacías para {vacias}"


def test_el_espanol_no_tiene_diccionario():
    """Es el idioma original: sus textos son las claves, no una traducción."""
    assert "es" not in TRADUCCIONES
    assert "es" in IDIOMAS_SOPORTADOS
