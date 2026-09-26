"""Tests de central_monitor_service.py: login + dashboard de un nodo remoto,
con httpx simulado -no hay servidor real en los tests, solo se verifica que
cada combinación de respuesta (éxito, timeout, credenciales rechazadas,
respuesta rara) se traduce al resultado esperado sin lanzar nunca."""

import httpx
import pytest

import app.services.central_monitor_service as central_monitor_service
from app.services.central_monitor_service import (
    consultar_nodo, consultar_todos, sincronizar_configuracion, consultar_arbol,
    consultar_detalle_nodo, consultar_detalle_relay, probar_nodo, consultar_nodo_basico,
)


@pytest.fixture(autouse=True)
def _cache_de_tokens_limpio():
    """_login() ahora cachea el token por (url, username, password) -sin
    limpiar esto entre tests, el primer test que loguea con éxito contra el
    FakeNode() por defecto deja el token en cache, y CUALQUIER test
    posterior con esos mismos valores por defecto reusaría ese token en vez
    de llamar al httpx.post monkeypateado de ESE test, rompiendo el
    aislamiento entre tests."""
    central_monitor_service._cache_tokens.clear()
    yield
    central_monitor_service._cache_tokens.clear()


class FakeNode:
    def __init__(self, id=1, name="Sucursal Norte", url="http://10.0.0.5:8000",
                 username="viewer", password="secreta", enabled=True):
        self.id = id
        self.name = name
        self.url = url
        self.username = username
        self.password = password
        self.enabled = enabled


class FakeNodeBasico:
    """Nodo "squid_basico": sin username/password, un Squid puro agregado
    a mano -ver MonitoredNode.tipo."""
    def __init__(self, id=2, name="Sucursal Sur (Squid puro)", url="http://10.0.0.9:3128", enabled=True):
        self.id = id
        self.name = name
        self.tipo = "squid_basico"
        self.url = url
        self.username = None
        self.password = None
        self.enabled = enabled


class FakeResponse:
    def __init__(self, status_code=200, json_data=None, json_error=False, text=""):
        self.status_code = status_code
        self._json_data = json_data
        self._json_error = json_error
        self.text = text

    def json(self):
        if self._json_error:
            raise ValueError("no es JSON")
        return self._json_data


def test_error_de_conexion_en_el_login(monkeypatch):
    def _falla(*a, **k):
        raise httpx.ConnectError("no se pudo conectar")

    monkeypatch.setattr(central_monitor_service.httpx, "post", _falla)
    resultado = consultar_nodo(FakeNode())
    assert resultado["status"] == "error"
    assert "no se pudo conectar" in resultado["message"].lower()


def test_login_rechazado_401(monkeypatch):
    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: FakeResponse(401))
    resultado = consultar_nodo(FakeNode())
    assert resultado["status"] == "error"
    assert "usuario o contraseña" in resultado["message"].lower()


def test_login_con_codigo_inesperado(monkeypatch):
    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: FakeResponse(500))
    resultado = consultar_nodo(FakeNode())
    assert resultado["status"] == "error"
    assert "500" in resultado["message"]


def test_login_con_429_da_mensaje_distinto_a_credenciales_rechazadas(monkeypatch):
    """El propio nodo remoto limitando los logins (demasiados refrescos
    seguidos) no es lo mismo que credenciales mal puestas -mensajes
    distintos, para no hacer sospechar del usuario/contraseña en vano."""
    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: FakeResponse(429))
    resultado = consultar_nodo(FakeNode())
    assert resultado["status"] == "error"
    assert "limitando" in resultado["message"].lower()
    assert "contraseña" not in resultado["message"].lower()


# --- Cache de tokens: no se loguea de nuevo en cada refresco ---------------
#
# Antes CADA refresco del árbol (el temporizador de 30s, cada clic en
# "Actualizar", cada "Ver más") se logueaba de nuevo contra cada nodo. Unos
# pocos minutos de uso activo del panel ya acumulan más de los 10 intentos
# de login por IP y minuto que el propio proyecto acepta en el remoto -el
# nodo terminaba respondiendo 429 sin que las credenciales tuvieran nada de
# malo. Reportado en vivo, 2026-09-26.

def test_segunda_consulta_al_mismo_nodo_no_vuelve_a_loguearse(monkeypatch):
    logins = {"n": 0}

    def _post(*a, **k):
        logins["n"] += 1
        return FakeResponse(200, json_data={"access_token": "tok123"})

    monkeypatch.setattr(central_monitor_service.httpx, "post", _post)
    monkeypatch.setattr(central_monitor_service.httpx, "get", lambda *a, **k: FakeResponse(200, json_data={"traffic": {}}))
    consultar_nodo(FakeNode())
    consultar_nodo(FakeNode())
    consultar_nodo(FakeNode())
    assert logins["n"] == 1


def test_nodo_distinto_no_comparte_el_token_cacheado(monkeypatch):
    logins = {"n": 0}

    def _post(*a, **k):
        logins["n"] += 1
        return FakeResponse(200, json_data={"access_token": "tok123"})

    monkeypatch.setattr(central_monitor_service.httpx, "post", _post)
    monkeypatch.setattr(central_monitor_service.httpx, "get", lambda *a, **k: FakeResponse(200, json_data={"traffic": {}}))
    consultar_nodo(FakeNode())
    consultar_nodo(FakeNode(url="http://10.0.0.9:8000"))
    assert logins["n"] == 2


def test_token_cacheado_vence_pasado_el_ttl(monkeypatch):
    logins = {"n": 0}

    def _post(*a, **k):
        logins["n"] += 1
        return FakeResponse(200, json_data={"access_token": "tok123"})

    monkeypatch.setattr(central_monitor_service.httpx, "post", _post)
    monkeypatch.setattr(central_monitor_service.httpx, "get", lambda *a, **k: FakeResponse(200, json_data={"traffic": {}}))

    reloj = {"ahora": 1000.0}
    monkeypatch.setattr(central_monitor_service.time, "monotonic", lambda: reloj["ahora"])

    consultar_nodo(FakeNode())
    reloj["ahora"] += central_monitor_service._TTL_CACHE_TOKEN + 1
    consultar_nodo(FakeNode())
    assert logins["n"] == 2


def test_login_devuelve_json_sin_access_token(monkeypatch):
    monkeypatch.setattr(
        central_monitor_service.httpx, "post",
        lambda *a, **k: FakeResponse(200, json_data={"algo": "raro"}),
    )
    resultado = consultar_nodo(FakeNode())
    assert resultado["status"] == "error"
    assert "SquidManager" in resultado["message"]


def test_login_ok_pero_falla_la_conexion_al_pedir_el_dashboard(monkeypatch):
    monkeypatch.setattr(
        central_monitor_service.httpx, "post",
        lambda *a, **k: FakeResponse(200, json_data={"access_token": "tok123"}),
    )

    def _falla(*a, **k):
        raise httpx.ReadTimeout("tardó demasiado")

    monkeypatch.setattr(central_monitor_service.httpx, "get", _falla)
    resultado = consultar_nodo(FakeNode())
    assert resultado["status"] == "error"
    assert "dashboard" in resultado["message"].lower()


def test_dashboard_responde_con_codigo_de_error(monkeypatch):
    monkeypatch.setattr(
        central_monitor_service.httpx, "post",
        lambda *a, **k: FakeResponse(200, json_data={"access_token": "tok123"}),
    )
    monkeypatch.setattr(central_monitor_service.httpx, "get", lambda *a, **k: FakeResponse(403))
    resultado = consultar_nodo(FakeNode())
    assert resultado["status"] == "error"
    assert "403" in resultado["message"]


def test_exito_de_punta_a_punta(monkeypatch):
    monkeypatch.setattr(
        central_monitor_service.httpx, "post",
        lambda *a, **k: FakeResponse(200, json_data={"access_token": "tok123"}),
    )
    monkeypatch.setattr(
        central_monitor_service.httpx, "get",
        lambda *a, **k: FakeResponse(200, json_data={"traffic": {"total_bytes_per_second": 1000}}),
    )
    resultado = consultar_nodo(FakeNode(name="Sucursal Sur"))
    assert resultado["status"] == "ok"
    assert resultado["name"] == "Sucursal Sur"
    assert resultado["data"]["traffic"]["total_bytes_per_second"] == 1000


def test_el_login_usa_la_url_sin_barra_final(monkeypatch):
    urls_llamadas = []

    def _post(url, **k):
        urls_llamadas.append(url)
        return FakeResponse(200, json_data={"access_token": "tok"})

    def _get(url, **k):
        urls_llamadas.append(url)
        return FakeResponse(200, json_data={})

    monkeypatch.setattr(central_monitor_service.httpx, "post", _post)
    monkeypatch.setattr(central_monitor_service.httpx, "get", _get)
    consultar_nodo(FakeNode(url="http://10.0.0.5:8000/"))
    assert urls_llamadas == [
        "http://10.0.0.5:8000/api/auth/login",
        "http://10.0.0.5:8000/api/metrics/dashboard",
    ]


def test_consultar_todos_omite_los_deshabilitados(monkeypatch):
    monkeypatch.setattr(
        central_monitor_service.httpx, "post",
        lambda *a, **k: FakeResponse(200, json_data={"access_token": "tok"}),
    )
    monkeypatch.setattr(central_monitor_service.httpx, "get", lambda *a, **k: FakeResponse(200, json_data={}))
    nodos = [FakeNode(id=1, enabled=True), FakeNode(id=2, enabled=False)]
    resultados = consultar_todos(nodos)
    assert [r["id"] for r in resultados] == [1]


def test_json_de_login_invalido_no_lanza(monkeypatch):
    monkeypatch.setattr(
        central_monitor_service.httpx, "post",
        lambda *a, **k: FakeResponse(200, json_data=None, json_error=True),
    )
    resultado = consultar_nodo(FakeNode())
    assert resultado["status"] == "error"


# --- sincronizar_configuracion: empujar el backup a un nodo remoto ---------

def _post_login_y_luego(respuesta_restore):
    """login siempre exitoso; la SEGUNDA llamada a httpx.post (el restore
    real) responde lo que se le pida -ambos pasos usan httpx.post, a
    diferencia de consultar_nodo() que usa httpx.get para el segundo."""
    llamadas = {"n": 0}

    def _post(url, **k):
        llamadas["n"] += 1
        if llamadas["n"] == 1:
            return FakeResponse(200, json_data={"access_token": "tok"})
        return respuesta_restore

    return _post


def test_sincronizar_exito(monkeypatch):
    monkeypatch.setattr(
        central_monitor_service.httpx, "post",
        _post_login_y_luego(FakeResponse(200, json_data={"users": 3, "acls": 10})),
    )
    resultado = sincronizar_configuracion(FakeNode(), {"metadata": {}})
    assert resultado["status"] == "ok"
    assert resultado["data"]["users"] == 3


def test_sincronizar_login_rechazado_no_llega_a_restaurar(monkeypatch):
    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: FakeResponse(401))
    resultado = sincronizar_configuracion(FakeNode(), {"metadata": {}})
    assert resultado["status"] == "error"
    assert "contraseña" in resultado["message"].lower()


def test_sincronizar_cuenta_sin_permisos_de_escritura(monkeypatch):
    monkeypatch.setattr(
        central_monitor_service.httpx, "post",
        _post_login_y_luego(FakeResponse(403)),
    )
    resultado = sincronizar_configuracion(FakeNode(), {"metadata": {}})
    assert resultado["status"] == "error"
    assert "permisos de escritura" in resultado["message"]


def test_sincronizar_error_generico_incluye_el_detalle(monkeypatch):
    monkeypatch.setattr(
        central_monitor_service.httpx, "post",
        _post_login_y_luego(FakeResponse(400, text="Archivo JSON inválido")),
    )
    resultado = sincronizar_configuracion(FakeNode(), {"metadata": {}})
    assert resultado["status"] == "error"
    assert "400" in resultado["message"]
    assert "Archivo JSON inválido" in resultado["message"]


def test_sincronizar_respuesta_no_json_no_lanza(monkeypatch):
    monkeypatch.setattr(
        central_monitor_service.httpx, "post",
        _post_login_y_luego(FakeResponse(200, json_data=None, json_error=True)),
    )
    resultado = sincronizar_configuracion(FakeNode(), {"metadata": {}})
    assert resultado["status"] == "error"


# --- consultar_arbol: jerarquía multi-nivel ---------------------------------

def test_arbol_pide_central_dashboard_no_metrics_dashboard(monkeypatch):
    urls_llamadas = []

    def _get(url, **k):
        urls_llamadas.append(url)
        return FakeResponse(200, json_data={"self": {"instance_id": "id-b", "data": {}}, "children": []})

    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: FakeResponse(200, json_data={"access_token": "tok"}))
    monkeypatch.setattr(central_monitor_service.httpx, "get", _get)
    consultar_arbol(FakeNode())
    assert urls_llamadas == ["http://10.0.0.5:8000/api/central/dashboard"]


def test_arbol_pasa_la_profundidad_decrementada_como_parametro(monkeypatch):
    params_recibidos = {}

    def _get(url, params=None, **k):
        params_recibidos.update(params or {})
        return FakeResponse(200, json_data={"self": {"instance_id": "id-b", "data": {}}, "children": []})

    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: FakeResponse(200, json_data={"access_token": "tok"}))
    monkeypatch.setattr(central_monitor_service.httpx, "get", _get)
    consultar_arbol(FakeNode(), profundidad_restante=2)
    assert params_recibidos == {"profundidad": 2}


def test_arbol_nunca_manda_profundidad_negativa(monkeypatch):
    """Aunque a consultar_arbol() se le pida con profundidad_restante
    negativa (no debería pasar con el tope del router, pero por las dudas),
    lo que viaja en la URL nunca es negativo -evita que un nodo remoto mal
    escrito interprete "profundidad: -1" como "sin límite"."""
    params_recibidos = {}

    def _get(url, params=None, **k):
        params_recibidos.update(params or {})
        return FakeResponse(200, json_data={"self": {"instance_id": "id-b", "data": {}}, "children": []})

    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: FakeResponse(200, json_data={"access_token": "tok"}))
    monkeypatch.setattr(central_monitor_service.httpx, "get", _get)
    consultar_arbol(FakeNode(), profundidad_restante=-3)
    assert params_recibidos == {"profundidad": 0}


def test_arbol_extrae_self_e_hijos_de_la_respuesta(monkeypatch):
    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: FakeResponse(200, json_data={"access_token": "tok"}))
    monkeypatch.setattr(
        central_monitor_service.httpx, "get",
        lambda *a, **k: FakeResponse(200, json_data={
            "self": {"instance_id": "id-b", "data": {"traffic": {"total_bytes_per_second": 42}}},
            "children": [{"id": 9, "name": "Nieto", "status": "ok", "data": {}, "children": []}],
        }),
    )
    resultado = consultar_arbol(FakeNode(name="Sucursal Sur"))
    assert resultado["status"] == "ok"
    assert resultado["instance_id"] == "id-b"
    assert resultado["data"]["traffic"]["total_bytes_per_second"] == 42
    assert len(resultado["children"]) == 1
    assert resultado["children"][0]["name"] == "Nieto"


def test_arbol_nodo_viejo_sin_endpoint_cae_a_dashboard_plano(monkeypatch):
    """Un SquidManager anterior a esta función no tiene /api/central/dashboard
    (404): cae a /api/metrics/dashboard y sigue mostrando ese nodo con su
    dashboard plano, sin jerarquía, en vez de romper toda la vista -bug real
    visto en pruebas en vivo contra un nodo viejo, 2026-09-25."""
    def _get(url, **k):
        if "central/dashboard" in url:
            return FakeResponse(404)
        return FakeResponse(200, json_data={"traffic": {"total_bytes_per_second": 500}})

    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: FakeResponse(200, json_data={"access_token": "tok"}))
    monkeypatch.setattr(central_monitor_service.httpx, "get", _get)
    resultado = consultar_arbol(FakeNode())
    assert resultado["status"] == "ok"
    assert resultado["children"] == []
    assert resultado["instance_id"] is None
    assert resultado["data"]["traffic"]["total_bytes_per_second"] == 500


def test_arbol_nodo_version_intermedia_sin_self_cae_a_dashboard_plano(monkeypatch):
    """Un SquidManager con una versión intermedia -de antes de existir
    self+children- YA tiene /api/central/dashboard, así que responde 200,
    no 404: pero con el esquema viejo de esa ruta ({"nodes": [...]}, sin
    "self"). Sin este chequeo, remoto.get("self") daba None y el resultado
    quedaba con status "ok" fabricado y todos los campos vacíos -bug real,
    visto en pruebas en vivo contra un nodo con esa versión, 2026-09-25."""
    def _get(url, **k):
        if "central/dashboard" in url:
            return FakeResponse(200, json_data={"nodes": [{"id": 0, "name": "(este servidor)"}]})
        return FakeResponse(200, json_data={"traffic": {"total_bytes_per_second": 777}})

    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: FakeResponse(200, json_data={"access_token": "tok"}))
    monkeypatch.setattr(central_monitor_service.httpx, "get", _get)
    resultado = consultar_arbol(FakeNode())
    assert resultado["status"] == "ok"
    assert resultado["children"] == []
    assert resultado["instance_id"] is None
    assert resultado["squid_port"] is None
    assert resultado["data"]["traffic"]["total_bytes_per_second"] == 777


def test_arbol_nodo_viejo_no_se_loguea_dos_veces(monkeypatch):
    """La caída a /api/metrics/dashboard reusa el login ya hecho para pedir
    /api/central/dashboard -antes se loguaba una segunda vez contra el mismo
    nodo en la misma consulta, redundante (encontrado en pruebas en vivo,
    2026-09-25)."""
    logins = {"n": 0}

    def _post(url, **k):
        logins["n"] += 1
        return FakeResponse(200, json_data={"access_token": "tok"})

    def _get(url, **k):
        if "central/dashboard" in url:
            return FakeResponse(404)
        return FakeResponse(200, json_data={})

    monkeypatch.setattr(central_monitor_service.httpx, "post", _post)
    monkeypatch.setattr(central_monitor_service.httpx, "get", _get)
    consultar_arbol(FakeNode())
    assert logins["n"] == 1


def test_arbol_nodo_viejo_realmente_caido_no_es_falso_ok(monkeypatch):
    """Si /api/metrics/dashboard TAMBIÉN falla (nodo viejo pero además
    caído), el resultado debe seguir siendo un error de verdad, no un "ok"
    fabricado solo porque hubo una caída de endpoint."""
    def _get(url, **k):
        return FakeResponse(404)  # también 404 en el plano, no solo en central

    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: FakeResponse(200, json_data={"access_token": "tok"}))
    monkeypatch.setattr(central_monitor_service.httpx, "get", _get)
    resultado = consultar_arbol(FakeNode())
    assert resultado["status"] == "error"
    assert resultado["children"] == []


def test_arbol_login_fallido_incluye_children_vacio(monkeypatch):
    """El resultado de un nodo caído tiene que tener siempre la misma forma
    (con 'children'), para que el frontend no tenga que distinguir casos al
    recorrer el árbol."""
    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: FakeResponse(401))
    resultado = consultar_arbol(FakeNode())
    assert resultado["status"] == "error"
    assert resultado["children"] == []


def test_arbol_error_al_pedir_el_dashboard_incluye_children_vacio(monkeypatch):
    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: FakeResponse(200, json_data={"access_token": "tok"}))
    monkeypatch.setattr(central_monitor_service.httpx, "get", lambda *a, **k: FakeResponse(500))
    resultado = consultar_arbol(FakeNode())
    assert resultado["status"] == "error"
    assert resultado["children"] == []


# --- consultar_detalle_nodo: datos del modal "Ver más" ----------------------

def test_detalle_nodo_pide_los_tres_endpoints_con_el_mismo_token(monkeypatch):
    urls_llamadas = []

    def _get(url, **k):
        urls_llamadas.append(url)
        return FakeResponse(200, json_data=[])

    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: FakeResponse(200, json_data={"access_token": "tok"}))
    monkeypatch.setattr(central_monitor_service.httpx, "get", _get)
    consultar_detalle_nodo(FakeNode())
    assert len(urls_llamadas) == 3
    assert all(u.startswith("http://10.0.0.5:8000/api/metrics/") for u in urls_llamadas)


def test_detalle_nodo_exito(monkeypatch):
    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: FakeResponse(200, json_data={"access_token": "tok"}))
    monkeypatch.setattr(
        central_monitor_service.httpx, "get",
        lambda url, **k: FakeResponse(200, json_data=[{"user": "llopez"}] if "top-users" in url else [{"domain": "github.com"}] if "top-domains" in url else [{"ip": "10.0.0.9"}]),
    )
    resultado = consultar_detalle_nodo(FakeNode())
    assert resultado["status"] == "ok"
    assert resultado["top_users"] == [{"user": "llopez"}]
    assert resultado["top_domains"] == [{"domain": "github.com"}]
    assert resultado["connections"] == [{"ip": "10.0.0.9"}]


def test_detalle_nodo_login_fallido_no_lanza(monkeypatch):
    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: FakeResponse(401))
    resultado = consultar_detalle_nodo(FakeNode())
    assert resultado["status"] == "error"
    assert resultado["top_users"] is None
    assert resultado["top_domains"] is None
    assert resultado["connections"] is None


def test_detalle_nodo_un_endpoint_caido_no_tumba_los_otros(monkeypatch):
    """Un nodo tan viejo que le falta uno de los tres endpoints (o que
    responde mal en ese instante) no debe perder los otros dos."""
    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: FakeResponse(200, json_data={"access_token": "tok"}))
    monkeypatch.setattr(
        central_monitor_service.httpx, "get",
        lambda url, **k: FakeResponse(404) if "top-domains" in url else FakeResponse(200, json_data=[{"ok": True}]),
    )
    resultado = consultar_detalle_nodo(FakeNode())
    assert resultado["status"] == "ok"
    assert resultado["top_domains"] is None
    assert resultado["top_users"] == [{"ok": True}]


# --- consultar_detalle_relay: detalle de un nieto/bisnieto (nivel 3+) ------

def test_detalle_relay_reenvia_el_resto_de_la_ruta_al_siguiente_salto(monkeypatch):
    urls_llamadas = []

    def _get(url, **k):
        urls_llamadas.append((url, k.get("params")))
        return FakeResponse(200, json_data={"id": 9, "status": "ok", "top_users": []})

    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: FakeResponse(200, json_data={"access_token": "tok"}))
    monkeypatch.setattr(central_monitor_service.httpx, "get", _get)
    resultado = consultar_detalle_relay(FakeNode(), resto=[1, 1])
    assert resultado == {"id": 9, "status": "ok", "top_users": []}
    assert len(urls_llamadas) == 1
    url, params = urls_llamadas[0]
    assert url == "http://10.0.0.5:8000/api/central/nodes/detalle-por-ruta"
    assert params == {"ruta": "1,1"}


def test_detalle_relay_login_fallido_no_lanza(monkeypatch):
    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: FakeResponse(401))
    resultado = consultar_detalle_relay(FakeNode(), resto=[1])
    assert resultado["status"] == "error"
    assert resultado["top_users"] is None
    assert resultado["top_domains"] is None
    assert resultado["connections"] is None


def test_detalle_relay_nodo_intermedio_sin_esta_ruta_da_mensaje_claro(monkeypatch):
    """El nodo intermedio tiene una versión anterior a esta función
    (404 en /central/nodes/detalle-por-ruta): no puede reenviar más allá de
    sí mismo -mensaje claro, no un error genérico de JSON inválido."""
    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: FakeResponse(200, json_data={"access_token": "tok"}))
    monkeypatch.setattr(central_monitor_service.httpx, "get", lambda *a, **k: FakeResponse(404))
    resultado = consultar_detalle_relay(FakeNode(), resto=[1])
    assert resultado["status"] == "error"
    assert "versión de SquidManager anterior" in resultado["message"]
    assert resultado["top_users"] is None


def test_detalle_relay_error_al_reenviar_incluye_los_tres_campos_none(monkeypatch):
    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: FakeResponse(200, json_data={"access_token": "tok"}))
    monkeypatch.setattr(central_monitor_service.httpx, "get", lambda *a, **k: FakeResponse(500))
    resultado = consultar_detalle_relay(FakeNode(), resto=[1])
    assert resultado["status"] == "error"
    assert resultado["top_users"] is None
    assert resultado["top_domains"] is None
    assert resultado["connections"] is None


# --- probar_nodo: "Probar conexión" también detecta el módulo apagado -----
#
# Antes "Probar conexión" solo llamaba a /api/metrics/dashboard, que no
# depende del interruptor de monitoreo centralizado del remoto: la prueba
# decía "conexión exitosa" aunque ESE módulo estuviera apagado del otro
# lado, y la tarjeta del árbol terminaba en "Sin conexión" sin que nada lo
# hubiera avisado antes -bug real, reportado en vivo 2026-09-26.

def test_probar_nodo_exito_con_monitoreo_habilitado_remoto(monkeypatch):
    def _get(url, **k):
        if "central/dashboard" in url:
            assert k["params"] == {"profundidad": 0}
            return FakeResponse(200, json_data={"self": {}, "children": []})
        return FakeResponse(200, json_data={"traffic": {}})

    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: FakeResponse(200, json_data={"access_token": "tok"}))
    monkeypatch.setattr(central_monitor_service.httpx, "get", _get)
    resultado = probar_nodo(FakeNode())
    assert resultado["status"] == "ok"
    assert resultado["monitoreo_centralizado_remoto"] is True


def test_probar_nodo_detecta_monitoreo_deshabilitado_remoto(monkeypatch):
    def _get(url, **k):
        if "central/dashboard" in url:
            return FakeResponse(403)
        return FakeResponse(200, json_data={"traffic": {}})

    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: FakeResponse(200, json_data={"access_token": "tok"}))
    monkeypatch.setattr(central_monitor_service.httpx, "get", _get)
    resultado = probar_nodo(FakeNode())
    assert resultado["status"] == "ok"
    assert resultado["monitoreo_centralizado_remoto"] is False


def test_probar_nodo_version_vieja_sin_ese_endpoint_no_marca_nada(monkeypatch):
    """Un SquidManager anterior a /api/central/dashboard (404, no 403) no
    tiene nada que advertir acá -ese caso ya lo cubre el fallback plano de
    consultar_arbol, sin jerarquía propia pero sin error."""
    def _get(url, **k):
        if "central/dashboard" in url:
            return FakeResponse(404)
        return FakeResponse(200, json_data={"traffic": {}})

    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: FakeResponse(200, json_data={"access_token": "tok"}))
    monkeypatch.setattr(central_monitor_service.httpx, "get", _get)
    resultado = probar_nodo(FakeNode())
    assert resultado["status"] == "ok"
    assert resultado["monitoreo_centralizado_remoto"] is None


def test_probar_nodo_login_fallido_no_llega_a_chequear_nada(monkeypatch):
    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: FakeResponse(401))
    resultado = probar_nodo(FakeNode())
    assert resultado["status"] == "error"
    assert "monitoreo_centralizado_remoto" not in resultado


def test_probar_nodo_un_solo_login_para_los_dos_pedidos(monkeypatch):
    logins = {"n": 0}

    def _post(url, **k):
        logins["n"] += 1
        return FakeResponse(200, json_data={"access_token": "tok"})

    monkeypatch.setattr(central_monitor_service.httpx, "post", _post)
    monkeypatch.setattr(
        central_monitor_service.httpx, "get",
        lambda url, **k: FakeResponse(200, json_data={"self": {}, "children": []}) if "central/dashboard" in url else FakeResponse(200, json_data={"traffic": {}}),
    )
    probar_nodo(FakeNode())
    assert logins["n"] == 1


# --- Nodo "squid_basico": sin SquidManager, se lee el Cache Manager de -----
# Squid directo (mgr:info), sin login. Pedido en vivo, 2026-09-26: "no
# siempre el squid a monitorear será un squidmanager".

_MGR_INFO_TEXTO = """Squid Object Cache: Version 6.14
Build Info: Ubuntu linux
Service Name: squid
Start Time:\tSat, 26 Sep 2026 15:10:57 GMT
Current Time:\tSat, 26 Sep 2026 15:26:11 GMT
Connection information for squid:
\tNumber of clients accessing cache:\t3
\tNumber of HTTP requests received:\t120
Resource usage for squid:
\tUP Time:\t914.143 seconds
"""


def test_consultar_nodo_basico_exito_parsea_uptime_version_y_clientes(monkeypatch):
    llamadas = []

    def _get(url, **k):
        llamadas.append((url, k))
        return FakeResponse(200, text=_MGR_INFO_TEXTO)

    monkeypatch.setattr(central_monitor_service.httpx, "get", _get)
    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("squid_basico no debería intentar login")))

    resultado = consultar_nodo_basico(FakeNodeBasico())

    assert resultado["status"] == "ok"
    assert resultado["data"]["squid_uptime"] == 914.143
    assert resultado["data"]["squid_version"] == "6.14"
    assert resultado["data"]["clientes_conectados"] == 3
    assert llamadas[0][0].endswith("/squid-internal-mgr/info")
    assert llamadas[0][1]["headers"]["Host"] == "localhost"


def test_consultar_nodo_basico_403_no_es_error_squid_esta_vivo(monkeypatch):
    """Un 403 al pedir el Cache Manager significa "Squid está arriba, pero
    no me deja ver esto" -no "Squid no responde". Squid por defecto solo
    permite esa consulta desde localhost, y no debería hacer falta tocar
    su squid.conf solo para poder agregarlo como nodo. Pedido en vivo,
    2026-09-26."""
    monkeypatch.setattr(central_monitor_service.httpx, "get", lambda *a, **k: FakeResponse(403))

    resultado = consultar_nodo_basico(FakeNodeBasico())

    assert resultado["status"] == "ok"
    assert "squid_uptime" not in resultado["data"]
    assert "ACL" in resultado["message"] or "opcional" in resultado["message"].lower()


def test_consultar_nodo_basico_cualquier_respuesta_http_prueba_que_esta_vivo(monkeypatch):
    monkeypatch.setattr(central_monitor_service.httpx, "get", lambda *a, **k: FakeResponse(500))

    resultado = consultar_nodo_basico(FakeNodeBasico())

    assert resultado["status"] == "ok"
    assert resultado["data"] == {}


def test_consultar_nodo_basico_sin_conexion(monkeypatch):
    def _get(*a, **k):
        raise httpx.ConnectError("No route to host")

    monkeypatch.setattr(central_monitor_service.httpx, "get", _get)

    resultado = consultar_nodo_basico(FakeNodeBasico())

    assert resultado["status"] == "error"
    assert "No se pudo conectar" in resultado["message"]


def test_consultar_nodo_despacha_a_basico_sin_loguearse(monkeypatch):
    monkeypatch.setattr(central_monitor_service.httpx, "get", lambda *a, **k: FakeResponse(200, text=_MGR_INFO_TEXTO))
    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no debería loguearse")))

    resultado = consultar_nodo(FakeNodeBasico())
    assert resultado["status"] == "ok"
    assert resultado["data"]["squid_uptime"] == 914.143


def test_probar_nodo_despacha_a_basico(monkeypatch):
    monkeypatch.setattr(central_monitor_service.httpx, "get", lambda *a, **k: FakeResponse(200, text=_MGR_INFO_TEXTO))
    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no debería loguearse")))

    resultado = probar_nodo(FakeNodeBasico())
    assert resultado["status"] == "ok"
    # Un squid_basico no tiene módulo de monitoreo centralizado que chequear.
    assert "monitoreo_centralizado_remoto" not in resultado


def test_consultar_arbol_de_basico_nunca_trae_hijos(monkeypatch):
    monkeypatch.setattr(central_monitor_service.httpx, "get", lambda *a, **k: FakeResponse(200, text=_MGR_INFO_TEXTO))

    resultado = consultar_arbol(FakeNodeBasico())
    assert resultado["status"] == "ok"
    assert resultado["children"] == []
    assert resultado["instance_id"] is None
    assert resultado["squid_port"] is None


def test_consultar_detalle_nodo_basico_no_intenta_loguearse(monkeypatch):
    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("squid_basico no tiene cuenta que probar")))

    resultado = consultar_detalle_nodo(FakeNodeBasico())
    assert resultado["status"] == "ok"
    assert resultado["top_users"] is None
    assert resultado["top_domains"] is None
    assert resultado["connections"] is None
    assert "Squid básico" in resultado["message"]


def test_sincronizar_configuracion_rechaza_nodo_basico_sin_loguearse(monkeypatch):
    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("squid_basico no tiene cuenta que probar")))

    resultado = sincronizar_configuracion(FakeNodeBasico(), backup={})
    assert resultado["status"] == "error"
    assert "Squid básico" in resultado["message"]


def test_consultar_detalle_relay_rechaza_nodo_basico_como_salto_intermedio(monkeypatch):
    monkeypatch.setattr(central_monitor_service.httpx, "post", lambda *a, **k: (_ for _ in ()).throw(AssertionError("squid_basico no tiene cuenta que probar")))

    resultado = consultar_detalle_relay(FakeNodeBasico(), resto=[5])
    assert resultado["status"] == "error"
    assert resultado["top_users"] is None
