"""El endpoint de salud tiene que llegar al backend, no al catch-all de la SPA.

El caso real, encontrado en una instalación de prueba: nginx no definía
`location /health`, así que la petición caía en

    location / { try_files $uri $uri/ /index.html; }

y devolvía **200 con el HTML del panel**. Comprobado en la máquina: `/health`
y `/esto-no-existe` daban exactamente la misma respuesta.

El problema no es el 404 de `/api/health` —ese es correcto, el health del
backend no lleva prefijo—, sino que el puerto del panel contestaba 200 a
cualquier cosa. Quien apuntara un monitor a `http://servidor:3000/health`
habría visto verde para siempre, también con el backend muerto. Un 404 avisa;
un 200 que miente, no.

Las dos configuraciones de nginx —la del instalador nativo y la de la imagen
del frontend— tenían el mismo hueco.
"""

import re
from pathlib import Path

import pytest


def _raiz() -> Path | None:
    for base in Path(__file__).resolve().parents:
        if (base / "install-nativo.sh").is_file():
            return base
    return None


RAIZ = _raiz()

# Fichero -> a dónde tiene que apuntar el proxy_pass de /health.
CONFIGURACIONES = {
    "install-nativo.sh": "127.0.0.1",
    "frontend/nginx.conf": "backend",
}


def _texto(relativa: str) -> str:
    assert RAIZ is not None, "no se encontró la raíz del proyecto"
    fichero = RAIZ / relativa
    if not fichero.is_file():
        pytest.skip(f"{relativa} no está en este árbol")
    return fichero.read_text(encoding="utf-8")


@pytest.mark.parametrize("relativa", list(CONFIGURACIONES))
def test_health_tiene_su_propia_regla(relativa):
    """`location = /health`, exacta, para que no la absorba el catch-all."""
    texto = _texto(relativa)
    assert re.search(r"location\s*=\s*/health\s*\{", texto), (
        f"{relativa}: no define «location = /health», así que la petición cae "
        "en el catch-all de la SPA y devuelve 200 con el HTML del panel."
    )


@pytest.mark.parametrize("relativa,destino", CONFIGURACIONES.items())
def test_health_se_reenvia_al_backend(relativa, destino):
    """Y que apunte al backend, no a los ficheros estáticos."""
    texto = _texto(relativa)
    bloque = texto[texto.index("location = /health"):]
    bloque = bloque[: bloque.index("}")]
    assert "proxy_pass" in bloque, f"{relativa}: /health no hace proxy_pass"
    assert destino in bloque, (
        f"{relativa}: /health debería reenviar a «{destino}», y el bloque dice:\n{bloque}"
    )
    assert bloque.rstrip().endswith("/health") or "/health" in bloque, (
        f"{relativa}: el proxy_pass de /health debe terminar en /health"
    )


@pytest.mark.parametrize("relativa", list(CONFIGURACIONES))
def test_la_regla_va_antes_del_catch_all(relativa):
    """El orden importa menos en nginx que la exactitud, pero se lee peor.

    nginx resuelve `location = /health` antes que `location /` por precisión,
    no por orden, así que esto no es funcional: es para que quien lea el
    fichero entienda la intención sin tener que recordar las reglas de nginx.
    """
    texto = _texto(relativa)
    # El instalador escribe su nginx dentro de un heredoc, donde las variables
    # van escapadas como \$uri para que no las expanda el shell.
    catch_all = texto.find("try_files $uri")
    if catch_all == -1:
        catch_all = texto.find("try_files \\$uri")
    assert catch_all != -1, f"{relativa}: no se encontró el catch-all de la SPA"
    assert texto.index("location = /health") < catch_all, (
        f"{relativa}: la regla de /health queda por debajo del catch-all y se lee mal."
    )
