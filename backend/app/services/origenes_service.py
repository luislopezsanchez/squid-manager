"""Orígenes de confianza: equipos que no tienen que autenticarse.

Pensado para poner SquidManager detrás de otro proxy, o delante de uno. Cuando
un proxy hijo reenvía tráfico a este, la autenticación de los usuarios finales
ya la hizo el hijo, y el padre no puede volver a pedirla: si el tráfico viaja
dentro de un túnel TLS interceptado, no hay forma de negociar un 407 —el hijo
cree que habla con el sitio de destino, no con un proxy—, así que la petición
se deniega con un 403 que no explica nada.

La salida estándar en una cascada de proxies es que el padre confíe en el hijo
por su dirección y le exima de autenticarse. Eso es lo que permite esta lista.

Es una exención de autenticación, así que conviene ser concreto: una IP suelta
o una red pequeña, nunca un rango amplio.
"""

import ipaddress
import logging

logger = logging.getLogger(__name__)


def parsear_lista(valor: str | None) -> list[str]:
    """Separa orígenes escritos con espacios, comas o saltos de línea."""
    if not valor:
        return []
    normalizado = valor.replace(",", " ").replace("\n", " ").replace("\t", " ")
    return [t for t in normalizado.split() if t]


def validar_origenes(origenes: list[str]) -> tuple[bool, str]:
    """Comprueba que sean direcciones o redes válidas.

    Se acepta tanto una IP suelta (`203.0.113.10`) como una red en notación
    CIDR (`203.0.113.0/24`), que es lo que entiende la ACL `src` de Squid.
    """
    for origen in origenes:
        try:
            # strict=False admite 192.168.1.5/24, que Squid tolera.
            ipaddress.ip_network(origen, strict=False)
        except ValueError:
            return False, (
                f"«{origen}» no es una dirección ni una red válida. Usa una IP "
                f"(203.0.113.10) o una red en notación CIDR (203.0.113.0/24)."
            )

    # Una exención de autenticación sobre media Internet no suele ser lo que
    # alguien pretende escribir.
    for origen in origenes:
        red = ipaddress.ip_network(origen, strict=False)
        if red.prefixlen == 0:
            return False, (
                f"«{origen}» abarca todas las direcciones: eso dejaría el proxy "
                f"abierto sin autenticación. Indica el origen concreto."
            )

    return True, "Orígenes válidos"
