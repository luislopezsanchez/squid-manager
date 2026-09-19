"""Tests de `_raiz_dominio`, usada por GET /api/ldap/groups.

Los grupos de un Active Directory real suelen vivir fuera del search_base
configurado para usuarios (p.ej. CN=Builtin, o una OU de Grupos aparte), así
que la búsqueda de grupos se hace desde la raíz del dominio (los componentes
dc=) y no desde search_base tal cual. Ver el docstring de la función.
"""

from app.routes.ldap import _raiz_dominio


def test_extrae_la_raiz_de_un_search_base_de_usuarios():
    assert _raiz_dominio("cn=Users,dc=test,dc=com") == "dc=test,dc=com"


def test_extrae_la_raiz_desde_una_ou_anidada():
    assert _raiz_dominio("ou=Ventas,ou=Personas,dc=empresa,dc=local") == "dc=empresa,dc=local"


def test_ignora_mayusculas_en_dc():
    assert _raiz_dominio("CN=Users,DC=test,DC=com") == "DC=test,DC=com"


def test_sin_componentes_dc_devuelve_el_valor_original():
    """Un search_base sin dc= (poco común, pero posible en OpenLDAP) no
    debe romper la búsqueda: se usa tal cual en vez de devolver vacío."""
    assert _raiz_dominio("o=miorganizacion") == "o=miorganizacion"


def test_ya_es_la_raiz_del_dominio():
    assert _raiz_dominio("dc=test,dc=com") == "dc=test,dc=com"
