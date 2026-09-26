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
import time

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(6.0, connect=4.0)

# Cache de tokens de login por nodo, en memoria -sin esto, CADA refresco del
# árbol (el temporizador de 30s, cada clic en "Actualizar", cada "Ver más")
# se logueaba de nuevo contra cada nodo remoto. Unos pocos minutos de uso
# activo del panel ya acumulan más de los 10 intentos de login por IP y
# minuto que el propio proyecto acepta en el remoto (ver LOGIN_MAX_REQUESTS
# en app/middleware/__init__.py) -no por credenciales mal puestas, sino por
# demasiados refrescos LEGÍTIMOS seguidos. El nodo remoto quedaba viéndose
# "Sin conexión" (429) sin que nada estuviera roto de verdad. Reportado en
# vivo, 2026-09-26.
#
# TTL bien por debajo de las 8 horas de vida del JWT (ACCESS_TOKEN_EXPIRE_
# MINUTES): 5 minutos alcanza de sobra para absorber cualquier ráfaga de
# refrescos, y sigue siendo corto como para que un usuario/contraseña
# editado en "Nodos configurados" tome efecto pronto, no recién en 8 horas.
#
# Clave (url, username, password): si cualquiera de los tres cambia -se
# edita el nodo-, la clave cambia sola y la entrada vieja del cache
# simplemente deja de usarse nunca más, sin necesitar invalidarla a mano.
_TTL_CACHE_TOKEN = 300
_cache_tokens: dict[tuple[str, str, str], tuple[str, float]] = {}


def _base(url: str) -> str:
    return url.rstrip("/")


def _tipo_de(node) -> str:
    return getattr(node, "tipo", None) or "squidmanager"


def _error(node, mensaje: str) -> dict:
    logger.warning(f"Monitoreo centralizado: nodo '{node.name}' ({node.url}) -> {mensaje}")
    return {"id": node.id, "name": node.name, "tipo": _tipo_de(node), "url": node.url, "status": "error", "message": mensaje}


def _login(node, base: str) -> tuple[str | None, dict | None]:
    """(token, None) si el login funcionó (o ya había uno en cache vigente),
    o (None, error) si no -mismo resultado de error que devuelve el resto
    de las funciones públicas de este módulo, para poder simplemente
    `return error` si no es None."""
    clave = (node.url, node.username, node.password)
    cacheado = _cache_tokens.get(clave)
    if cacheado and cacheado[1] > time.monotonic():
        return cacheado[0], None

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
    if login.status_code == 429:
        # El propio nodo remoto está frenando los logins -reintentar en el
        # momento no ayuda, el mensaje debe ser distinto al de "credenciales
        # rechazadas" para no hacer sospechar del usuario/contraseña.
        return None, _error(node, "El nodo remoto está limitando los intentos de login (demasiados refrescos seguidos). Probá de nuevo en un minuto.")
    if login.status_code != 200:
        return None, _error(node, f"El nodo respondió {login.status_code} al iniciar sesión")

    try:
        token = login.json()["access_token"]
    except (ValueError, KeyError):
        return None, _error(node, "Respuesta de login inesperada -¿la URL es de un SquidManager?")

    _cache_tokens[clave] = (token, time.monotonic() + _TTL_CACHE_TOKEN)
    return token, None


def _pedir_dashboard_plano(node, base: str, token: str) -> dict:
    """GET /api/metrics/dashboard ya autenticado -sin loguearse, recibe el
    token ya obtenido. Separado de consultar_nodo() para que
    consultar_arbol() pueda reusar el mismo login cuando el nodo remoto no
    tiene /api/central/dashboard todavía (404): antes ese caso volvía a
    loguearse una segunda vez contra el mismo nodo en la misma consulta,
    redundante -encontrado en pruebas en vivo, 2026-09-25."""
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

    return {"id": node.id, "name": node.name, "tipo": "squidmanager", "url": node.url, "status": "ok", "data": data}


def consultar_nodo(node) -> dict:
    """Login + dashboard de un nodo. Nunca lanza: cualquier fallo (nodo
    caído, credenciales inválidas, timeout, no es un SquidManager) se
    devuelve como parte del resultado, para que un nodo offline no tumbe
    la vista de los demás."""
    if _tipo_de(node) == "squid_basico":
        return consultar_nodo_basico(node)
    base = _base(node.url)
    token, error = _login(node, base)
    if error:
        return error
    return _pedir_dashboard_plano(node, base, token)


def consultar_nodo_basico(node) -> dict:
    """Nodo "Squid básico" (sin SquidManager encima): sin login -no hay
    cuenta que validar-, se lee directo el Cache Manager de Squid
    (mgr:info) contra `node.url`, que acá es el host:puerto DEL PROPIO
    SQUID, no de un panel. Mismo mecanismo que cada SquidManager usa
    contra SU PROPIO Squid en 127.0.0.1 (ver runtime/native_runtime.py,
    cache_manager_report), apuntando ahora a otra IP -por eso requiere que
    el squid.conf remoto tenga una ACL que permita esta consulta desde
    este servidor: Squid por defecto solo la permite desde localhost.

    `data` trae mucho menos que un nodo SquidManager -ni tráfico en
    tiempo real ni usuarios activos: eso sale de la base de datos y los
    logs de SquidManager, que un Squid puro no tiene- pero sí lo esencial
    para saber si está arriba: si responde, hace cuánto tiempo, su
    versión, y cuántos clientes tiene conectados en este momento (dato
    real del propio Squid, no inventado). Pedido en vivo, 2026-09-26:
    "no siempre el squid a monitorear será un squidmanager"."""
    base = _base(node.url)
    try:
        resp = httpx.get(
            f"{base}/squid-internal-mgr/info",
            headers={"Host": "localhost"},
            timeout=_TIMEOUT,
        )
    except httpx.HTTPError as e:
        return _error(node, f"No se pudo conectar: {e}")

    if resp.status_code == 403:
        return _error(
            node,
            "Squid rechazó la consulta al Cache Manager. Para monitorear un Squid básico, su "
            "squid.conf necesita una ACL que permita esta consulta desde este servidor -por "
            "defecto Squid solo la permite desde localhost. Por ejemplo: agregar "
            "\"acl monitoreo_central src <IP de este servidor>\" y \"http_access allow manager "
            "monitoreo_central\" ANTES del \"http_access deny manager\" ya existente, y recargar "
            "Squid (squid -k reconfigure).",
        )
    if resp.status_code != 200:
        return _error(node, f"Squid respondió {resp.status_code} al pedir el Cache Manager")

    from app.services.cache_manager_service import _parsear_info
    info = _parsear_info(resp.text)

    return {
        "id": node.id, "name": node.name, "tipo": "squid_basico", "url": node.url, "status": "ok",
        "data": {
            "squid_uptime": info.get("uptime_segundos"),
            "squid_version": info.get("version"),
            "clientes_conectados": info.get("clientes_activos"),
        },
    }


def consultar_todos(nodes: list) -> list[dict]:
    """Uno por uno, en orden -no hace falta paralelizar para unas pocas
    sucursales, y mantiene el mismo estilo sincrono que el resto del
    proyecto usa para llamadas salientes."""
    return [consultar_nodo(n) for n in nodes if n.enabled]


def _chequear_monitoreo_habilitado(base: str, token: str) -> bool | None:
    """True/False si se pudo determinar si el REMOTO tiene el módulo de
    monitoreo centralizado habilitado; None si no se pudo determinar (una
    versión anterior a este endpoint, por ejemplo) -en ese caso no hay nada
    que advertir: el fallback plano de consultar_arbol ya cubre ese caso
    sin que haga falta un aviso aparte acá.

    profundidad=0 a propósito: alcanza con la respuesta (200 o 403), no
    hace falta que el remoto recorra sus propios nodos para este chequeo."""
    try:
        resp = httpx.get(
            f"{base}/api/central/dashboard",
            headers={"Authorization": f"Bearer {token}"},
            params={"profundidad": 0},
            timeout=_TIMEOUT,
        )
    except httpx.HTTPError:
        return None
    if resp.status_code == 403:
        return False
    if resp.status_code == 200:
        return True
    return None


def probar_nodo(node) -> dict:
    """Login + dashboard plano de un nodo, más un chequeo de si el módulo
    de monitoreo centralizado está habilitado en ese remoto -para "Probar
    conexión" al agregar o editar un nodo.

    Antes esto llamaba directo a consultar_nodo() (login + solo
    /api/metrics/dashboard), que no depende para nada del interruptor de
    monitoreo centralizado del remoto: la prueba daba "conexión exitosa"
    aunque el remoto tuviera ese módulo apagado, y la tarjeta del árbol
    terminaba en "Sin conexión" sin que nada lo hubiera avisado antes -bug
    real, reportado en vivo 2026-09-26 (se repitió al querer volver a
    agregar un nodo que antes andaba bien). Un solo login, reusado para
    los dos pedidos -mismo criterio que ya usa consultar_arbol() con su
    fallback plano.

    Un nodo "squid_basico" no tiene login que probar ni módulo de
    monitoreo centralizado que chequear -consultar_nodo_basico() ya es en
    sí mismo la prueba completa de conexión para ese tipo."""
    if _tipo_de(node) == "squid_basico":
        return consultar_nodo_basico(node)

    base = _base(node.url)
    token, error = _login(node, base)
    if error:
        return error

    resultado = _pedir_dashboard_plano(node, base, token)
    if resultado["status"] != "ok":
        return resultado

    resultado["monitoreo_centralizado_remoto"] = _chequear_monitoreo_habilitado(base, token)
    return resultado


# --- Árbol de monitoreo (jerarquía multi-nivel) -----------------------------
#
# consultar_nodo() de arriba pide /api/metrics/dashboard: un solo nivel,
# sin hijos, y así se queda (lo sigue usando /test, que solo necesita
# confirmar que las credenciales andan). Esto de acá pide
# /api/central/dashboard, que YA arma "self + children" del lado del nodo
# remoto -si ese nodo tiene sus propios nodos configurados y habilitados,
# vienen incluidos, sin que este servidor los conozca ni tenga sus
# credenciales: cada servidor solo necesita las credenciales de SUS
# nodos directos, nunca las de un nieto.

# Cuántos niveles por debajo del que pregunta se resuelven si no se pide
# otra cosa, y el tope absoluto que se acepta aunque lo pida el que llama
# -una cadena mas profunda que esto en la practica ya es una red mal
# pensada, y sin tope una cadena circular mal configurada (A monitorea a B,
# B a A) generaria una cantidad de llamadas HTTP que crece con cada nivel.
PROFUNDIDAD_DEFECTO = 3
PROFUNDIDAD_MAXIMA = 5


def consultar_arbol(node, profundidad_restante: int = PROFUNDIDAD_DEFECTO) -> dict:
    """Login + árbol de un nodo remoto: su propio dashboard (`data`) y, si
    profundidad_restante > 0, el de sus propios nodos (`children`),
    recursivamente -resuelto DEL LADO DEL NODO REMOTO, en una sola llamada
    HTTP desde acá.

    La profundidad viaja en la URL (?profundidad=N) y CADA salto la
    decrementa antes de volver a pedir un nivel mas: eso es lo unico que
    hace falta para que la recursion nunca sea infinita, ni siquiera ante
    una cadena circular (A monitorea a B, B monitorea a A, ...) -quien
    decide cuanto mas recursar es siempre quien hace la llamada saliente
    (cada servidor, sobre SUS propios nodos), nunca el nodo remoto que
    responde; un nodo remoto mal configurado -o directamente hostil- no
    puede forzar mas profundidad que la que se le pidio, como mucho puede
    mentir sobre sus propios datos.

    Nodo remoto con una version de SquidManager anterior a este endpoint
    (404), o con una version intermedia que YA tiene /api/central/dashboard
    pero con el esquema viejo de esa ruta (de antes de existir la jerarquia
    self+children, un simple {"nodes": [...]} -asi que responde 200, no
    404): en los dos casos cae a consultar_nodo() plano, sin hijos -sigue
    mostrando ese nodo, sin jerarquia, en vez de fingir que todo salio bien
    con status "ok" y los datos vacios. Este segundo caso es real, no
    hipotetico: encontrado en vivo 2026-09-25 contra un nodo con esa version
    intermedia.

    Un nodo "squid_basico" nunca tiene /api/central/dashboard que pedir
    -no es un SquidManager-, así que se resuelve directo con
    consultar_nodo_basico() y `children` siempre vacío: un Squid puro no
    tiene nodos propios que monitorear."""
    if _tipo_de(node) == "squid_basico":
        resultado = consultar_nodo_basico(node)
        resultado["children"] = []
        resultado["instance_id"] = None
        resultado["squid_port"] = None
        return resultado

    base = _base(node.url)
    token, error = _login(node, base)
    if error:
        error["children"] = []
        return error

    def _fallback_plano() -> dict:
        # Reusa el token ya obtenido arriba -no vuelve a loguearse.
        plano = _pedir_dashboard_plano(node, base, token)
        plano["children"] = []
        plano["instance_id"] = None
        plano["squid_port"] = None
        return plano

    try:
        resp = httpx.get(
            f"{base}/api/central/dashboard",
            headers={"Authorization": f"Bearer {token}"},
            params={"profundidad": max(profundidad_restante, 0)},
            timeout=_TIMEOUT,
        )
    except httpx.HTTPError as e:
        error = _error(node, f"No se pudo leer el dashboard: {e}")
        error["children"] = []
        return error

    if resp.status_code == 404:
        return _fallback_plano()

    if resp.status_code != 200:
        error = _error(node, f"El nodo respondió {resp.status_code} al pedir el dashboard")
        error["children"] = []
        return error

    try:
        remoto = resp.json()
    except ValueError:
        error = _error(node, "El dashboard del nodo no devolvió JSON válido")
        error["children"] = []
        return error

    self_remoto = remoto.get("self")
    if not isinstance(self_remoto, dict) or "data" not in self_remoto:
        return _fallback_plano()

    return {
        "id": node.id,
        "name": node.name,
        "tipo": "squidmanager",
        "url": node.url,
        "instance_id": self_remoto.get("instance_id"),
        "squid_port": self_remoto.get("squid_port"),
        "status": "ok",
        "data": self_remoto.get("data"),
        "children": remoto.get("children") or [],
    }


def consultar_arbol_de_todos(nodes: list, profundidad_restante: int = PROFUNDIDAD_DEFECTO) -> list[dict]:
    """Mismo criterio que consultar_todos(): en orden, uno por uno, solo los
    habilitados."""
    return [consultar_arbol(n, profundidad_restante) for n in nodes if n.enabled]


def sincronizar_configuracion(node, backup: dict) -> dict:
    """Empuja un backup (ver build_backup_dict en routes/backup.py) al
    nodo remoto, vía su propio POST /api/backup/restore -mismo mecanismo
    que restaurar un archivo descargado a mano, sin archivo intermedio.

    A diferencia de consultar_nodo() (solo lectura), esto SOBRESCRIBE la
    configuración del nodo remoto: hace falta que la cuenta guardada ahí
    tenga permisos de escritura (una cuenta "viewer" -la recomendada para
    solo monitorear- se rechaza acá con un 403, con un mensaje claro en
    vez de fallar en silencio).

    Un nodo "squid_basico" no tiene panel de SquidManager al que
    restaurarle nada -es Squid puro-, así que esto se rechaza antes de
    intentar ningún login (no tiene cuenta que usar)."""
    if _tipo_de(node) == "squid_basico":
        return _error(node, "Este nodo es un Squid básico: no tiene panel de SquidManager para sincronizarle configuración.")

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


def consultar_detalle_nodo(node) -> dict:
    """Top usuarios, top dominios y últimas conexiones de un nodo remoto,
    para el modal "Ver más" de Panel Central -mismos endpoints que ya
    expone cualquier SquidManager (/api/metrics/top-users, etc.), pedidos
    con la MISMA cuenta ya guardada para ese nodo. El token del nodo remoto
    nunca llega al navegador: este backend hace de intermediario, igual que
    ya hace con el dashboard agregado (consultar_arbol) -así el modal no es
    una superficie nueva de riesgo, es "más de lo mismo" técnicamente.

    Nunca lanza: un fallo puntual en uno de los tres pedidos (por ejemplo,
    un nodo tan viejo que todavía no tenía /top-domains) deja ese campo en
    None sin tumbar los otros dos.

    Un nodo "squid_basico" no tiene esta API -ni base de datos propia de
    usuarios/dominios que consultar-, así que los tres campos quedan en
    None con un mensaje que lo explica, sin intentar loguearse (no tiene
    cuenta que probar)."""
    if _tipo_de(node) == "squid_basico":
        return {
            "id": node.id, "name": node.name, "status": "ok",
            "message": (
                "Este nodo es un Squid básico (sin SquidManager): no tiene usuarios, dominios ni "
                "conexiones registrados para mostrar acá -esos datos los calcula SquidManager, y "
                "este Squid no lo tiene instalado."
            ),
            "top_users": None, "top_domains": None, "connections": None,
        }

    base = _base(node.url)
    token, error = _login(node, base)
    if error:
        error["top_users"] = None
        error["top_domains"] = None
        error["connections"] = None
        return error

    headers = {"Authorization": f"Bearer {token}"}

    def _pedir(path: str):
        try:
            resp = httpx.get(f"{base}{path}", headers=headers, timeout=_TIMEOUT)
        except httpx.HTTPError:
            return None
        if resp.status_code != 200:
            return None
        try:
            return resp.json()
        except ValueError:
            return None

    return {
        "id": node.id,
        "name": node.name,
        "status": "ok",
        "top_users": _pedir("/api/metrics/top-users?limit=10&ventana=24h&sort_by=bytes"),
        "top_domains": _pedir("/api/metrics/top-domains?limit=10&ventana=24h&sort_by=requests"),
        "connections": _pedir("/api/metrics/connections?limit=15"),
    }


def _detalle_error(node, mensaje: str) -> dict:
    error = _error(node, mensaje)
    error["top_users"] = None
    error["top_domains"] = None
    error["connections"] = None
    return error


def consultar_detalle_relay(node, resto: list[int]) -> dict:
    """Detalle de un nieto o bisnieto (nivel 3+ del árbol): loguea en `node`
    -el siguiente salto de la ruta- y le pide a SU MISMO endpoint
    /central/nodes/detalle-por-ruta que resuelva el resto, con el resto de
    la ruta (sin el id que este salto ya consumió).

    Mismo principio que consultar_arbol() ya usa para el árbol de
    dashboards: cada servidor resuelve el PRIMER id con sus propias
    credenciales y, si queda más ruta, se la reenvía tal cual a ESE nodo
    -así el detalle de un nodo profundo se arma sin que este servidor
    necesite jamás las credenciales de nada más allá de sus propios nodos
    directos. `resto` nunca llega vacío acá: ese caso (último salto) lo
    resuelve la ruta directamente con consultar_detalle_nodo(), ver
    routes/central.py.

    Un nodo "squid_basico" nunca puede ser este salto intermedio -nunca
    tiene children, ver consultar_arbol()-, pero se cubre igual por las
    dudas: no tiene login que hacer ni ruta propia que reenviar."""
    if _tipo_de(node) == "squid_basico":
        return _detalle_error(
            node,
            "Este nodo es un Squid básico: no tiene nodos propios, no puede reenviar el pedido.",
        )

    base = _base(node.url)
    token, error = _login(node, base)
    if error:
        error["top_users"] = None
        error["top_domains"] = None
        error["connections"] = None
        return error

    ruta_restante = ",".join(str(i) for i in resto)
    try:
        resp = httpx.get(
            f"{base}/api/central/nodes/detalle-por-ruta",
            headers={"Authorization": f"Bearer {token}"},
            params={"ruta": ruta_restante},
            timeout=_TIMEOUT,
        )
    except httpx.HTTPError as e:
        return _detalle_error(node, f"No se pudo reenviar el pedido de detalle: {e}")

    if resp.status_code == 404:
        # Nodo intermedio con una versión anterior a esta ruta -no puede
        # reenviar más allá de sí mismo. Mismo criterio que el resto del
        # proyecto ante una versión vieja: un mensaje claro, no un error
        # generico de "JSON inválido".
        return _detalle_error(
            node,
            f"«{node.name}» tiene una versión de SquidManager anterior a esta función: "
            "no puede reenviar el pedido de detalle a sus propios nodos.",
        )
    if resp.status_code != 200:
        return _detalle_error(node, f"El nodo respondió {resp.status_code} al reenviar el pedido de detalle")

    try:
        return resp.json()
    except ValueError:
        return _detalle_error(node, "La respuesta reenviada del detalle no es JSON válido")
