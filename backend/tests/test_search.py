"""Buscador global de referencias (app/routes/search.py)."""

from app.routes.search import _regla_coincide


def test_coincide_por_nombre_de_acl_parcial():
    assert _regla_coincide("block_facebook authenticated", None, "face")


def test_coincide_por_descripcion():
    assert _regla_coincide("localnet", "Acceso de la red de ventas", "ventas")


def test_no_coincide_si_no_aparece_en_ningun_lado():
    assert not _regla_coincide("localnet authenticated", "Acceso general", "facebook")


def test_insensible_a_mayusculas_en_el_termino():
    """El término ya llega en minúsculas (buscar_referencias lo normaliza
    antes de llamar); esta función no vuelve a hacerlo con `termino`, pero
    sí normaliza los campos que compara -confirma que no hace falta pasar
    el término ya en minúsculas dos veces."""
    assert _regla_coincide("Grupo_Ventas", None, "ventas")
