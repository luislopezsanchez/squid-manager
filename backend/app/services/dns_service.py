"""Servidores DNS propios para las consultas de Squid.

Squid resuelve los nombres por su cuenta, no delega en el sistema, así que se
le puede indicar a qué servidores preguntar (`dns_nameservers`). Sirve, por
ejemplo, para que la navegación del proxy pase por un Pi-hole y herede su
filtrado.

Un servidor mal puesto aquí deja al proxy sin resolver ningún nombre: no falla
una web, fallan todas a la vez, y el síntoma no apunta a la causa. Por eso el
cambio se comprueba contra el servidor real antes de aplicarse, igual que el
squid.conf se valida con `squid -k parse` antes de escribirse.

La consulta DNS se construye a mano sobre un socket UDP en lugar de añadir una
librería: hace falta preguntar a un servidor concreto (no "resolver este
nombre como sea"), que es justo lo que las funciones normales de resolución no
permiten hacer.
"""

import ipaddress
import logging
import random
import socket
import struct

logger = logging.getLogger(__name__)

# Dominio de sondeo. Existe desde siempre y está reservado por la IANA para
# ejemplos y pruebas, así que no depende de la infraestructura de nadie.
DOMINIO_DE_PRUEBA = "example.com"

TIMEOUT_POR_DEFECTO = 3.0

# Motivos de rechazo del servidor (RCODE de la respuesta DNS).
_MOTIVOS_RCODE = {
    1: "la consulta llegó mal formada",
    2: "fallo interno del servidor",
    3: "el dominio de prueba no existe para ese servidor",
    4: "el servidor no soporta este tipo de consulta",
    5: "el servidor rechazó la consulta (¿solo acepta clientes de su red?)",
}


def parsear_lista(valor: str | None) -> list[str]:
    """Separa el valor guardado en una lista de servidores.

    Se aceptan espacios, comas o saltos de línea para que dé igual cómo lo
    escriba quien rellena el campo.
    """
    if not valor:
        return []
    normalizado = valor.replace(",", " ").replace("\n", " ").replace("\t", " ")
    return [t for t in normalizado.split() if t]


def validar_servidores(servidores: list[str]) -> tuple[bool, str]:
    """Comprueba que todos sean direcciones IP.

    `dns_nameservers` no admite nombres de host: Squid tiene que poder
    preguntar sin resolver nada primero, que es exactamente lo que aún no
    puede hacer.
    """
    for s in servidores:
        try:
            ipaddress.ip_address(s)
        except ValueError:
            return False, (
                f"«{s}» no es una dirección IP. Squid necesita la IP del "
                f"servidor DNS, no su nombre."
            )
    return True, "Direcciones válidas"


def _construir_consulta(dominio: str, identificador: int) -> bytes:
    """Arma una consulta DNS de tipo A."""
    # Cabecera: identificador, indicador de recursión deseada, una pregunta.
    cabecera = struct.pack(">HHHHHH", identificador, 0x0100, 1, 0, 0, 0)
    pregunta = b"".join(
        bytes([len(parte)]) + parte.encode("ascii")
        for parte in dominio.split(".") if parte
    ) + b"\x00"
    # QTYPE=1 (registro A), QCLASS=1 (Internet)
    return cabecera + pregunta + struct.pack(">HH", 1, 1)


def probar_servidor(
    ip: str,
    dominio: str = DOMINIO_DE_PRUEBA,
    timeout: float = TIMEOUT_POR_DEFECTO,
) -> tuple[bool, str]:
    """Pregunta de verdad a ese servidor y dice si sirve para navegar."""
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        return False, f"«{ip}» no es una dirección IP"

    identificador = random.randint(0, 0xFFFF)
    familia = socket.AF_INET6 if ":" in ip else socket.AF_INET

    sock = None
    try:
        sock = socket.socket(familia, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        sock.sendto(_construir_consulta(dominio, identificador), (ip, 53))
        respuesta, _ = sock.recvfrom(4096)
    except socket.timeout:
        return False, (
            f"{ip} no respondió en {timeout:g} s. Comprueba que el servidor "
            f"está encendido y que acepta consultas desde este equipo."
        )
    except OSError as e:
        return False, f"No se pudo consultar a {ip}: {e}"
    finally:
        if sock is not None:
            sock.close()

    if len(respuesta) < 12:
        return False, f"{ip} devolvió una respuesta incompleta"

    id_respuesta, indicadores, _, num_respuestas = struct.unpack(">HHHH", respuesta[:8])

    if id_respuesta != identificador:
        return False, f"{ip} contestó a una consulta distinta de la enviada"

    rcode = indicadores & 0x0F
    if rcode != 0:
        motivo = _MOTIVOS_RCODE.get(rcode, f"código de error {rcode}")
        return False, f"{ip} no atendió la consulta: {motivo}"

    if num_respuestas == 0:
        return False, (
            f"{ip} respondió, pero sin resultados para {dominio}. Responde a "
            f"consultas pero no está resolviendo nombres de Internet."
        )

    return True, f"{ip} responde correctamente"


def probar_servidores(servidores: list[str]) -> tuple[bool, str]:
    """Comprueba la lista entera y resume el resultado.

    Basta con que uno falle para rechazar el cambio: Squid reparte las
    consultas entre todos los servidores de la lista, así que uno caído no
    queda de reserva sin usar, sino que se lleva su parte de las consultas y
    hace fallar esa fracción de la navegación.
    """
    if not servidores:
        return True, "Sin servidores propios: se usará la resolución del sistema"

    fallos = []
    for ip in servidores:
        ok, mensaje = probar_servidor(ip)
        if not ok:
            fallos.append(mensaje)

    if fallos:
        return False, " / ".join(fallos)

    return True, f"Los {len(servidores)} servidores responden correctamente"
