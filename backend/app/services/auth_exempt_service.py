"""Dominios exentos de autenticación, sin importar quién los pida.

A diferencia de `origenes_service` (que exime por IP DE ORIGEN, pensado para
una cascada de proxies), esto exime por DOMINIO DE DESTINO. Caso de uso real:
Windows Update, telemetría de Office, o cualquier SaaS que no sepa presentar
credenciales de proxy — hoy la única exención posible era por IP de origen, lo
que no sirve si quien navega SÍ debe autenticarse para el resto del tráfico.

Es, igual que los orígenes de confianza, una exención de autenticación: un
valor demasiado amplio no da un error visible, simplemente deja pasar sin
pedir credenciales a cualquiera que apunte ahí.
"""

import logging

logger = logging.getLogger(__name__)

# Un dominio o comodín de subdominio (dstdomain de Squid) que, por sí solo,
# coincidiría con cualquier destino. Rechazarlos evita una exención total por
# un error de tipeo (una "." de más, o un intento de usar "*" como si fuera
# shell glob, que Squid no interpreta así).
_COMODINES_TOTALES = {"", ".", "*", ".*"}

# Squid trata "dstdomain .foo" como "foo y cualquier subdominio de foo". Con
# un solo nivel (".com", ".local", ".org"...) eso deja de ser "un dominio con
# subdominios" para ser "cualquier destino de ese TLD" -la misma clase de
# exencion total que _COMODINES_TOTALES ya bloquea, solo que a nivel de TLD en
# vez de todo Internet. Un dominio real de dos niveles o mas (".miempresa.com")
# sigue aceptandose sin problema.


def parsear_lista(valor: str | None) -> list[str]:
    """Separa dominios escritos con espacios, comas o saltos de línea."""
    if not valor:
        return []
    normalizado = valor.replace(",", " ").replace("\n", " ").replace("\t", " ")
    return [t for t in normalizado.split() if t]


def validar_dominios(dominios: list[str]) -> tuple[bool, str]:
    """Rechaza entradas que eximirían de golpe a todo el tráfico.

    No se valida que sea un dominio "bien formado" más allá de esto: Squid
    acepta desde `ejemplo.com` hasta `.ejemplo.com` (con subdominios) tal
    cual se escriba, y restringir de más aquí solo estorbaría casos válidos.
    """
    for dominio in dominios:
        if dominio.strip(".*") == "" or dominio in _COMODINES_TOTALES:
            return False, (
                f"«{dominio}» eximiría de autenticarse a CUALQUIER destino. "
                f"Indica dominios concretos (ejemplo.com, .ejemplo.com)."
            )
        # Un unico nivel con punto inicial (".com") exime a todo ese TLD.
        # Se pide al menos "algo.tld" (un punto en lo que queda tras quitar UN
        # punto inicial) para distinguirlo de un dominio real de dos niveles.
        sin_punto_inicial = dominio[1:] if dominio.startswith(".") else dominio
        if dominio.startswith(".") and "." not in sin_punto_inicial:
            return False, (
                f"«{dominio}» eximiría de autenticarse a cualquier destino "
                f"del dominio de nivel superior «{sin_punto_inicial}» entero. "
                f"Indica un dominio concreto (.miempresa.{sin_punto_inicial})."
            )
    return True, "Dominios válidos"
