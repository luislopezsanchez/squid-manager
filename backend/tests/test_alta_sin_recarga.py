"""Crear un usuario del proxy no puede cortar el servicio a los demás.

El caso real: al crear el primer usuario y probar a navegar acto seguido, la
conexión fallaba con «Failed to connect», y al reintentar iba. Medido en la
máquina de pruebas: el alta responde 201 en 0,43 s y el proxy rechaza
conexiones durante unos 200 ms.

La causa era `reload_squid()` —un `squid -k reconfigure`— que la ruta llamaba
tras escribir el htpasswd. Reconfigure reinicia los helpers de autenticación, y
ahí está el corte.

Y no servía para nada, por dos motivos, los dos comprobados en la máquina:

1. `squid/auth_helper.py` abre el fichero de contraseñas **en cada petición**,
   así que un usuario nuevo entra en cuanto se escribe la línea. Añadiendo una a
   mano, sin tocar Squid: 200 con su clave y 407 con una incorrecta.
2. Para quitarle el acceso a alguien tampoco valía: `reconfigure` **no** purga
   la caché de credenciales de Squid. Un usuario borrado del htpasswd seguía
   navegando después de un reconfigure, y solo dejaba de hacerlo tras el
   reinicio completo. De eso se encarga `purge_credentials()`, que reinicia a
   propósito y que estas rutas ya llaman donde corresponde.
"""

import re
from pathlib import Path

import pytest

RUTA = Path(__file__).resolve().parents[1] / "app" / "routes" / "proxy_users.py"


def _fuente() -> str:
    if not RUTA.is_file():
        pytest.skip("no está proxy_users.py en este árbol")
    return RUTA.read_text(encoding="utf-8")


def _cuerpo_de(fuente: str, nombre: str) -> str:
    """Devuelve el código de una función de nivel superior, sin su docstring.

    Quitar el docstring no es un detalle: si no, una prueba que busca el nombre
    de una función se dispara con solo mencionarlo en la explicación de por qué
    ya no se llama.
    """
    inicio = fuente.index(f"def {nombre}(")
    resto = fuente[inicio:]
    siguiente = re.search(r"\n(?:@router|def |async def )", resto[1:])
    cuerpo = resto[: siguiente.start() + 1] if siguiente else resto
    return re.sub(r'""".*?"""', "", cuerpo, count=1, flags=re.S)


def test_escribir_el_htpasswd_no_recarga_squid():
    fuente = _fuente()
    assert "def _sync_passwd(" in fuente, (
        "se esperaba la función _sync_passwd; si se ha renombrado, actualiza esta prueba"
    )
    cuerpo = _cuerpo_de(fuente, "_sync_passwd")
    assert "reload_squid" not in cuerpo, (
        "escribir el htpasswd vuelve a recargar Squid. El helper relee el "
        "fichero en cada petición, así que la recarga no aporta nada y corta "
        "el servicio unos 200 ms."
    )


def test_el_alta_no_reinicia_ni_purga():
    """Crear un usuario no debe tocar el proceso de Squid de ninguna manera."""
    cuerpo = _cuerpo_de(_fuente(), "create_proxy_user")
    for prohibido in ("reload_squid", "purge_credentials", "restart"):
        assert prohibido not in cuerpo, (
            f"create_proxy_user llama a «{prohibido}»: dar de alta a alguien no "
            "puede cortarle el proxy al resto."
        )


@pytest.mark.parametrize("funcion", ["delete_proxy_user", "reset_password"])
def test_quitar_el_acceso_si_purga(funcion):
    """La contraria, que es la que de verdad importa.

    Si esto fallara, un usuario borrado seguiría navegando hasta que venciera
    `credentialsttl` —dos horas por defecto—, que es justo el agujero que
    `purge_credentials()` existe para tapar.
    """
    cuerpo = _cuerpo_de(_fuente(), funcion)
    assert "purge_credentials" in cuerpo, (
        f"{funcion} ya no purga la caché de credenciales: quien pierda el acceso "
        "seguiría navegando hasta dos horas."
    )
