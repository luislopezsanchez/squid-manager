"""Rate limiting simple en memoria para proteger la API (anti fuerza bruta)."""

import time
import logging
from collections import defaultdict, deque
from fastapi import Request, HTTPException

logger = logging.getLogger(__name__)

# Ventana de tiempo y máximo de peticiones por IP
WINDOW_SECONDS = 60
MAX_REQUESTS_PER_WINDOW = 60  # 1 petición/segundo de media

# Rate limit más estricto para el login (anti fuerza bruta)
LOGIN_MAX_REQUESTS = 20  # 20 intentos por minuto por IP (suficiente margen, aún protege)

# Estructura de datos: {ip: deque([timestamps])}
_requests = defaultdict(deque)


def _get_client_ip(request: Request) -> str:
    """Obtiene la IP del cliente desde los headers de proxy."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_rate_limit(ip: str, max_requests: int) -> bool:
    """Devuelve True si el cliente excede el límite."""
    now = time.time()
    window = _requests[ip]

    # Limpiar timestamps antiguos
    while window and now - window[0] > WINDOW_SECONDS:
        window.popleft()

    if len(window) >= max_requests:
        return True

    window.append(now)
    return False


async def rate_limit_middleware(request: Request, call_next):
    """Middleware de rate limiting por IP."""
    ip = _get_client_ip(request)
    path = request.url.path

    # Rate limit más estricto para el login
    if path.endswith("/auth/login"):
        if _check_rate_limit(ip, LOGIN_MAX_REQUESTS):
            logger.warning(f"Rate limit excedido en login para IP {ip}")
            raise HTTPException(status_code=429, detail="Demasiados intentos de login. Espera un minuto.")
    else:
        if _check_rate_limit(ip, MAX_REQUESTS_PER_WINDOW):
            raise HTTPException(status_code=429, detail="Demasiadas peticiones. Espera un momento.")

    return await call_next(request)
