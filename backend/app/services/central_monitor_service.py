"""Monitoreo centralizado: consulta el dashboard de otras instancias de
SquidManager ("nodos") desde esta, para verlas juntas en un solo panel.

Sin mecanismo de token propio: se autentica en cada nodo con su login
normal (POST /api/auth/login) y luego pide su GET /api/metrics/dashboard
ya existente -ningún cambio en el nodo remoto, ni en Squid, ni acoplamiento
entre instancias más allá de esa llamada HTTP. Se recomienda una cuenta
"viewer" (solo lectura) dedicada a esto en cada nodo hijo.

httpx sincrono (mismo criterio que ai_service.py/category_sync_service.py
en este proyecto): la cantidad de nodos esperada es chica (unas pocas
sucursales, no cientos), y un timeout corto por nodo evita que uno caído
demore la vista más que unos segundos.
"""

import logging

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(6.0, connect=4.0)


def _base(url: str) -> str:
    return url.rstrip("/")


def _error(node, mensaje: str) -> dict:
    logger.warning(f"Monitoreo centralizado: nodo '{node.name}' ({node.url}) -> {mensaje}")
    return {"id": node.id, "name": node.name, "url": node.url, "status": "error", "message": mensaje}


def consultar_nodo(node) -> dict:
    """Login + dashboard de un nodo. Nunca lanza: cualquier fallo (nodo
    caído, credenciales inválidas, timeout, no es un SquidManager) se
    devuelve como parte del resultado, para que un nodo offline no tumbe
    la vista de los demás."""
    base = _base(node.url)
    try:
        login = httpx.post(
            f"{base}/api/auth/login",
            data={"username": node.username, "password": node.password},
            timeout=_TIMEOUT,
        )
    except httpx.HTTPError as e:
        return _error(node, f"No se pudo conectar: {e}")

    if login.status_code == 401:
        return _error(node, "Usuario o contraseña rechazados por el nodo")
    if login.status_code != 200:
        return _error(node, f"El nodo respondió {login.status_code} al iniciar sesión")

    try:
        token = login.json()["access_token"]
    except (ValueError, KeyError):
        return _error(node, "Respuesta de login inesperada -¿la URL es de un SquidManager?")

    try:
        resp = httpx.get(
            f"{base}/api/metrics/dashboard",
            headers={"Authorization": f"Bearer {token}"},
            timeout=_TIMEOUT,
        )
    except httpx.HTTPError as e:
        return _error(node, f"No se pudo leer el dashboard: {e}")

    if resp.status_code != 200:
        return _error(node, f"El nodo respondió {resp.status_code} al pedir el dashboard")

    try:
        data = resp.json()
    except ValueError:
        return _error(node, "El dashboard del nodo no devolvió JSON válido")

    return {"id": node.id, "name": node.name, "url": node.url, "status": "ok", "data": data}


def consultar_todos(nodes: list) -> list[dict]:
    """Uno por uno, en orden -no hace falta paralelizar para unas pocas
    sucursales, y mantiene el mismo estilo sincrono que el resto del
    proyecto usa para llamadas salientes."""
    return [consultar_nodo(n) for n in nodes if n.enabled]
