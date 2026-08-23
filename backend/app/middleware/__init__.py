"""Rate limiting simple en memoria para proteger la API (anti fuerza bruta).

La identificación del cliente NO confía en `X-Forwarded-For` a ciegas: esa
cabecera la controla quien hace la petición, así que rotándola se anula
cualquier límite por IP. Solo se acepta cuando la conexión llega desde un
proxy de confianza (el nginx del frontend), que es quien la escribe.
"""

import os
import time
import socket
import logging
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# Ventana de tiempo y máximo de peticiones por IP
WINDOW_SECONDS = 60
MAX_REQUESTS_PER_WINDOW = 120  # el dashboard hace polling; margen holgado

# Rate limit más estricto para el login (anti fuerza bruta)
LOGIN_MAX_REQUESTS = 10  # por IP y minuto
LOGIN_MAX_PER_USER = 5   # por cuenta y minuto (una IP rotada no lo esquiva)

# Purga de entradas inactivas para que el diccionario no crezca sin techo
_PRUNE_EVERY_SECONDS = 300

# Hosts cuyo X-Forwarded-For se acepta. Son los proxies que tenemos delante.
_TRUSTED_PROXY_HOSTS = [
    h.strip()
    for h in os.getenv("TRUSTED_PROXY_HOSTS", "frontend").split(",")
    if h.strip()
]
_TRUSTED_PROXY_TTL = 60

# Estructura de datos: {clave: deque([timestamps])}
_requests = defaultdict(deque)
_last_prune = time.time()

# Cache de IPs de los proxies de confianza: (timestamp, {ip, ...})
_trusted_cache: tuple[float, set[str]] = (0.0, set())


def _trusted_proxy_ips() -> set[str]:
    """Resuelve los hostnames de los proxies de confianza (con caché corta)."""
    global _trusted_cache
    now = time.time()
    cached_at, ips = _trusted_cache
    if now - cached_at < _TRUSTED_PROXY_TTL and ips:
        return ips

    resolved: set[str] = set()
    for host in _TRUSTED_PROXY_HOSTS:
        try:
            for info in socket.getaddrinfo(host, None):
                resolved.add(info[4][0])
        except OSError:
            # El contenedor puede no estar levantado todavía; se reintenta luego.
            continue

    _trusted_cache = (now, resolved)
    return resolved


def _get_client_ip(request: Request) -> str:
    """IP real del cliente.

    Solo se lee `X-Forwarded-For` si la conexión viene de un proxy de confianza;
    en cualquier otro caso se usa la IP del peer, que no se puede falsificar.
    """
    peer = request.client.host if request.client else "unknown"

    if peer in _trusted_proxy_ips():
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()

    return peer


def _prune(now: float) -> None:
    """Elimina las claves cuya ventana quedó vacía."""
    global _last_prune
    if now - _last_prune < _PRUNE_EVERY_SECONDS:
        return
    _last_prune = now
    for key in [k for k, w in _requests.items() if not w or now - w[-1] > WINDOW_SECONDS]:
        _requests.pop(key, None)


def _check_rate_limit(key: str, max_requests: int) -> bool:
    """Devuelve True si el cliente excede el límite."""
    now = time.time()
    _prune(now)
    window = _requests[key]

    # Limpiar timestamps antiguos
    while window and now - window[0] > WINDOW_SECONDS:
        window.popleft()

    if len(window) >= max_requests:
        return True

    window.append(now)
    return False


def _too_many(detail: str) -> JSONResponse:
    """Respuesta 429.

    Se devuelve en lugar de lanzar HTTPException: un middleware HTTP corre por
    fuera del ExceptionMiddleware de Starlette, así que una excepción lanzada
    aquí llegaría al cliente como un 500.
    """
    return JSONResponse(
        status_code=429,
        content={"detail": detail},
        headers={"Retry-After": str(WINDOW_SECONDS)},
    )


def check_login_attempts(username: str) -> bool:
    """Límite por cuenta, invocado desde el endpoint de login.

    Va en la ruta y no en el middleware porque leer el cuerpo de la petición
    desde un middleware consume el stream y la ruta se queda sin formulario.
    Rotar la IP de origen no esquiva este límite.

    Devuelve True si la cuenta excede el límite.
    """
    return _check_rate_limit(f"login-user:{username.strip().lower()}", LOGIN_MAX_PER_USER)


async def rate_limit_middleware(request: Request, call_next):
    """Middleware de rate limiting por IP."""
    ip = _get_client_ip(request)
    path = request.url.path

    if path.endswith("/auth/login"):
        if _check_rate_limit(f"login-ip:{ip}", LOGIN_MAX_REQUESTS):
            logger.warning(f"Rate limit de login excedido para IP {ip}")
            return _too_many("Demasiados intentos de login. Espera un minuto.")
    else:
        if _check_rate_limit(f"ip:{ip}", MAX_REQUESTS_PER_WINDOW):
            return _too_many("Demasiadas peticiones. Espera un momento.")

    return await call_next(request)
