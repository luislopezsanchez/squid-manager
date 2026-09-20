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


def _login(node, base: str) -> tuple[str | None, dict | None]:
    """(token, None) si el login funcionó, o (None, error) si no -mismo
    resultado de error que devuelve el resto de las funciones públicas de
    este módulo, para poder simplemente `return error` si no es None."""
    try:
        login = httpx.post(
            f"{base}/api/auth/login",
            data={"username": node.username, "password": node.password},
            timeout=_TIMEOUT,
        )
    except httpx.HTTPError as e:
        return None, _error(node, f"No se pudo conectar: {e}")

    if login.status_code == 401:
        return None, _error(node, "Usuario o contraseña rechazados por el nodo")
    if login.status_code != 200:
        return None, _error(node, f"El nodo respondió {login.status_code} al iniciar sesión")

    try:
        return login.json()["access_token"], None
    except (ValueError, KeyError):
        return None, _error(node, "Respuesta de login inesperada -¿la URL es de un SquidManager?")


def consultar_nodo(node) -> dict:
    """Login + dashboard de un nodo. Nunca lanza: cualquier fallo (nodo
    caído, credenciales inválidas, timeout, no es un SquidManager) se
    devuelve como parte del resultado, para que un nodo offline no tumbe
    la vista de los demás."""
    base = _base(node.url)
    token, error = _login(node, base)
    if error:
        return error

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


def sincronizar_configuracion(node, backup: dict) -> dict:
    """Empuja un backup (ver build_backup_dict en routes/backup.py) al
    nodo remoto, vía su propio POST /api/backup/restore -mismo mecanismo
    que restaurar un archivo descargado a mano, sin archivo intermedio.

    A diferencia de consultar_nodo() (solo lectura), esto SOBRESCRIBE la
    configuración del nodo remoto: hace falta que la cuenta guardada ahí
    tenga permisos de escritura (una cuenta "viewer" -la recomendada para
    solo monitorear- se rechaza acá con un 403, con un mensaje claro en
    vez de fallar en silencio)."""
    import json as _json

    base = _base(node.url)
    token, error = _login(node, base)
    if error:
        return error

    try:
        resp = httpx.post(
            f"{base}/api/backup/restore",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("sync.json", _json.dumps(backup).encode("utf-8"), "application/json")},
            timeout=httpx.Timeout(30.0, connect=4.0),  # una config grande tarda mas que leer un dashboard
        )
    except httpx.HTTPError as e:
        return _error(node, f"No se pudo enviar la configuración: {e}")

    if resp.status_code == 403:
        return _error(node, "La cuenta guardada para este nodo no tiene permisos de escritura ahí")
    if resp.status_code != 200:
        detalle = resp.text[:200]
        return _error(node, f"El nodo respondió {resp.status_code} al restaurar: {detalle}")

    try:
        resultado = resp.json()
    except ValueError:
        return _error(node, "La respuesta de restauración del nodo no es JSON válido")

    return {"id": node.id, "name": node.name, "url": node.url, "status": "ok", "data": resultado}
