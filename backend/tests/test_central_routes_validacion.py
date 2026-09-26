"""Tests de la validación de datos de app/routes/central.py."""

import pytest
from fastapi import HTTPException

import app.routes.central as central
from app.routes.central import (
    _validar_url, _to_response, test_node as _ruta_test_node, NodeTest,
    node_detalle_por_ruta as _ruta_detalle_por_ruta,
)
from app.models.monitored_node import MonitoredNode
from app.models.central_config import CentralMonitorConfig


def test_url_valida_http():
    assert _validar_url("http://10.0.0.5:8000") == "http://10.0.0.5:8000"


def test_url_valida_https():
    assert _validar_url("https://sucursal.empresa.com") == "https://sucursal.empresa.com"


def test_url_le_quita_la_barra_final():
    assert _validar_url("http://10.0.0.5:8000/") == "http://10.0.0.5:8000"


def test_url_sin_esquema_rechazada():
    with pytest.raises(HTTPException) as exc:
        _validar_url("10.0.0.5:8000")
    assert exc.value.status_code == 400


def test_url_vacia_rechazada():
    with pytest.raises(HTTPException):
        _validar_url("")


def test_respuesta_enmascara_la_contrasena():
    nodo = MonitoredNode(id=1, name="Norte", url="http://10.0.0.5:8000",
                          username="viewer", password="secreta_de_verdad", enabled=True)
    resp = _to_response(nodo)
    assert resp["password"] == "***"
    assert "secreta_de_verdad" not in str(resp)


# --- POST /central/test: resolución de la contraseña enmascarada ----------
#
# Bug real encontrado en revisión de código: probar la conexión de un nodo
# YA GUARDADO sin reescribir la contraseña mandaba el placeholder "***"
# literal como si fuera la contraseña real, y la prueba fallaba siempre por
# "credenciales rechazadas" aunque las guardadas fueran correctas.

class _FakeQueryUnNodo:
    def __init__(self, nodo):
        self._nodo = nodo

    def filter(self, *a, **k):
        return self

    def first(self):
        return self._nodo


# _requerir_habilitado() -que test_node() llama antes de hacer nada más-
# consulta CentralMonitorConfig, no MonitoredNode: sin esto, estos tests
# fallarían con un 403 antes de llegar a lo que en realidad quieren probar
# (la resolución de la contraseña enmascarada). Habilitado a propósito, para
# que esa parte no interfiera con lo que cada test realmente verifica.
_CONFIG_HABILITADA = CentralMonitorConfig(
    id=1, enabled=True, monitorizar_hijos=True, instance_id="00000000-0000-0000-0000-000000000000",
)


class FakeDBConNodo:
    def __init__(self, nodo):
        self._nodo = nodo

    def query(self, model):
        if model is CentralMonitorConfig:
            return _FakeQueryUnNodo(_CONFIG_HABILITADA)
        return _FakeQueryUnNodo(self._nodo)


def test_probar_con_mascara_y_id_usa_la_contrasena_guardada(monkeypatch):
    nodo = MonitoredNode(id=7, name="Norte", url="http://10.0.0.5:8000",
                          username="viewer", password="la_de_verdad", enabled=True)
    capturado = {}

    def _consultar_falso(nodo_temporal):
        capturado["password"] = nodo_temporal.password
        return {"status": "ok"}

    monkeypatch.setattr(central, "probar_nodo", _consultar_falso)
    data = NodeTest(url="http://10.0.0.5:8000", username="viewer", password="***", id=7)
    _ruta_test_node(data=data, db=FakeDBConNodo(nodo), _=None)
    assert capturado["password"] == "la_de_verdad"


def test_probar_con_mascara_sin_id_no_revienta(monkeypatch):
    """Un nodo nuevo (todavía sin guardar) no tiene id -no debería intentar
    resolver nada, solo mandar la máscara tal cual (y que el proveedor
    remoto la rechace, que es el comportamiento correcto ahí)."""
    capturado = {}

    def _consultar_falso(nodo_temporal):
        capturado["password"] = nodo_temporal.password
        return {"status": "error"}

    monkeypatch.setattr(central, "probar_nodo", _consultar_falso)
    data = NodeTest(url="http://10.0.0.5:8000", username="viewer", password="***", id=None)
    _ruta_test_node(data=data, db=FakeDBConNodo(None), _=None)
    assert capturado["password"] == "***"


def test_probar_con_contrasena_nueva_no_toca_la_guardada(monkeypatch):
    nodo = MonitoredNode(id=7, name="Norte", url="http://10.0.0.5:8000",
                          username="viewer", password="la_vieja", enabled=True)
    capturado = {}

    def _consultar_falso(nodo_temporal):
        capturado["password"] = nodo_temporal.password
        return {"status": "ok"}

    monkeypatch.setattr(central, "probar_nodo", _consultar_falso)
    data = NodeTest(url="http://10.0.0.5:8000", username="viewer", password="una_nueva", id=7)
    _ruta_test_node(data=data, db=FakeDBConNodo(nodo), _=None)
    assert capturado["password"] == "una_nueva"


# --- GET /central/nodes/detalle-por-ruta: detalle a cualquier nivel --------
#
# Reemplaza a la vieja GET /nodes/{id}/detalle (un id suelto, que solo podía
# alcanzar un hijo DIRECTO): un nieto o bisnieto llega con un id que
# pertenece a la tabla de OTRO servidor, y pedirle el detalle a este backend
# con ese id daba 404 -bug real, visto en pruebas en vivo con una jerarquía
# de 4 niveles, 2026-09-26.

def test_ruta_vacia_rechazada():
    with pytest.raises(HTTPException) as exc:
        _ruta_detalle_por_ruta(ruta="", db=FakeDBConNodo(None), _=None)
    assert exc.value.status_code == 400


def test_ruta_no_numerica_rechazada():
    with pytest.raises(HTTPException) as exc:
        _ruta_detalle_por_ruta(ruta="7,abc", db=FakeDBConNodo(None), _=None)
    assert exc.value.status_code == 400


def test_ruta_con_demasiados_saltos_rechazada():
    ruta = ",".join(str(i) for i in range(central.PROFUNDIDAD_MAXIMA + 1))
    with pytest.raises(HTTPException) as exc:
        _ruta_detalle_por_ruta(ruta=ruta, db=FakeDBConNodo(None), _=None)
    assert exc.value.status_code == 400


def test_ruta_primer_id_no_encontrado_da_404():
    with pytest.raises(HTTPException) as exc:
        _ruta_detalle_por_ruta(ruta="7,1", db=FakeDBConNodo(None), _=None)
    assert exc.value.status_code == 404


def test_ruta_de_un_solo_id_resuelve_directo(monkeypatch):
    """Un hijo directo (ruta de un solo id) se resuelve con
    consultar_detalle_nodo, sin reenviar nada -mismo comportamiento que
    tenía la vieja ruta de un solo salto."""
    nodo = MonitoredNode(id=7, name="Norte", url="http://10.0.0.5:8000",
                          username="viewer", password="secreta", enabled=True)
    capturado = {}

    def _detalle_falso(n):
        capturado["node"] = n
        return {"status": "ok"}

    monkeypatch.setattr(central, "consultar_detalle_nodo", _detalle_falso)
    resultado = _ruta_detalle_por_ruta(ruta="7", db=FakeDBConNodo(nodo), _=None)
    assert resultado == {"status": "ok"}
    assert capturado["node"] is nodo


def test_ruta_reenvio_rechazado_si_monitorizar_hijos_apagado():
    """Reenviar el resto de la ruta es "prestar" uno de mis propios nodos
    para que alguien vea a través de mí -si decidí no monitorizarlos,
    tampoco presto el acceso, aunque el nodo en sí siga configurado acá."""
    config = CentralMonitorConfig(
        id=1, enabled=True, monitorizar_hijos=False, instance_id="00000000-0000-0000-0000-000000000001",
    )

    class _FakeDBSoloConfig:
        def query(self, model):
            return _FakeQueryUnNodo(config)

    with pytest.raises(HTTPException) as exc:
        _ruta_detalle_por_ruta(ruta="7,1", db=_FakeDBSoloConfig(), _=None)
    assert exc.value.status_code == 403


def test_ruta_de_un_solo_id_no_depende_de_monitorizar_hijos(monkeypatch):
    """El caso base (mi propio hijo directo, sin reenviar nada) sigue
    andando aunque "monitorizar_hijos" esté apagado -ese interruptor solo
    afecta al REENVÍO hacia adentro, no a responder por mí mismo."""
    nodo = MonitoredNode(id=7, name="Norte", url="http://10.0.0.5:8000",
                          username="viewer", password="secreta", enabled=True)

    class _FakeDBConNodoYConfigApagada:
        def query(self, model):
            if model is CentralMonitorConfig:
                return _FakeQueryUnNodo(CentralMonitorConfig(
                    id=1, enabled=True, monitorizar_hijos=False,
                    instance_id="00000000-0000-0000-0000-000000000002",
                ))
            return _FakeQueryUnNodo(nodo)

    monkeypatch.setattr(central, "consultar_detalle_nodo", lambda n: {"status": "ok"})
    resultado = _ruta_detalle_por_ruta(ruta="7", db=_FakeDBConNodoYConfigApagada(), _=None)
    assert resultado == {"status": "ok"}


def test_ruta_de_varios_ids_reenvia_el_resto(monkeypatch):
    """Un nieto/bisnieto (ruta de más de un id) se resuelve con
    consultar_detalle_relay, pasándole el resto de la ruta sin el primer
    id (que este salto ya consumió)."""
    nodo = MonitoredNode(id=7, name="Norte", url="http://10.0.0.5:8000",
                          username="viewer", password="secreta", enabled=True)
    capturado = {}

    def _relay_falso(n, resto):
        capturado["node"] = n
        capturado["resto"] = resto
        return {"status": "ok"}

    monkeypatch.setattr(central, "consultar_detalle_relay", _relay_falso)
    resultado = _ruta_detalle_por_ruta(ruta="7,1,2", db=FakeDBConNodo(nodo), _=None)
    assert resultado == {"status": "ok"}
    assert capturado["node"] is nodo
    assert capturado["resto"] == [1, 2]


# --- GET /central/dashboard: monitorizar_hijos independiente de enabled ---
#
# Antes un único interruptor todo-o-nada obligaba a elegir entre "no me
# dejo monitorear" y "sigo monitoreando a mis nodos" -encontrado en vivo,
# 2026-09-26, al querer que un servidor siga siendo hijo de otro sin tener
# hijos propios. Con monitorizar_hijos apagado, `children` sale vacío para
# CUALQUIERA que pregunte (el propio panel o un padre): no hay forma de
# distinguirlos en la petición en sí, así que la única forma limpia de
# lograrlo es no recorrer los nodos en absoluto.

class _FakeQueryNodos:
    def __init__(self, nodos):
        self._nodos = nodos

    def order_by(self, *a, **k):
        return self

    def all(self):
        return self._nodos


class _FakeDBDashboard:
    def __init__(self, config, nodos):
        self._config = config
        self._nodos = nodos

    def query(self, model):
        if model is CentralMonitorConfig:
            return _FakeQueryUnNodo(self._config)
        if model is MonitoredNode:
            return _FakeQueryNodos(self._nodos)
        return _FakeQueryUnNodo(None)  # SquidSetting (_squid_port): sin puerto configurado


class _FakeRequestSinHeaders:
    class _Headers:
        def get(self, *a, **k):
            return None

    headers = _Headers()


def test_dashboard_con_monitorizar_hijos_apagado_no_recorre_nodos(monkeypatch):
    config = CentralMonitorConfig(
        id=1, enabled=True, monitorizar_hijos=False, instance_id="00000000-0000-0000-0000-000000000003",
    )
    nodo = MonitoredNode(id=1, name="Norte", url="http://10.0.0.5:8000",
                          username="viewer", password="secreta", enabled=True)
    capturado = {}

    def _consultar_arbol_falso(nodes, profundidad_restante):
        capturado["nodes"] = nodes
        return []

    monkeypatch.setattr(central, "consultar_arbol_de_todos", _consultar_arbol_falso)
    monkeypatch.setattr(central, "get_dashboard", lambda db=None: {})
    resultado = central.central_dashboard(
        request=_FakeRequestSinHeaders(), profundidad=3,
        db=_FakeDBDashboard(config, [nodo]), _=None,
    )
    assert capturado["nodes"] == []
    assert resultado["children"] == []


def test_dashboard_con_monitorizar_hijos_prendido_si_recorre_nodos(monkeypatch):
    config = CentralMonitorConfig(
        id=1, enabled=True, monitorizar_hijos=True, instance_id="00000000-0000-0000-0000-000000000004",
    )
    nodo = MonitoredNode(id=1, name="Norte", url="http://10.0.0.5:8000",
                          username="viewer", password="secreta", enabled=True)
    capturado = {}

    def _consultar_arbol_falso(nodes, profundidad_restante):
        capturado["nodes"] = nodes
        return []

    monkeypatch.setattr(central, "consultar_arbol_de_todos", _consultar_arbol_falso)
    monkeypatch.setattr(central, "get_dashboard", lambda db=None: {})
    central.central_dashboard(
        request=_FakeRequestSinHeaders(), profundidad=3,
        db=_FakeDBDashboard(config, [nodo]), _=None,
    )
    assert capturado["nodes"] == [nodo]


def test_dashboard_responde_aunque_enabled_este_apagado(monkeypatch):
    """"Dejarse monitorear" (que otro SquidManager consulte a este como
    nodo) nunca depende de `enabled` -antes central_dashboard() llamaba a
    _requerir_habilitado() y devolvía 403 acá, y un admin que apagaba el
    interruptor pensando "dejo de monitorear a mis nodos" de paso dejaba de
    responderle a SU PROPIO padre, sin haber tocado nada del lado del
    padre -confusión real, reportada en vivo 2026-09-26."""
    config = CentralMonitorConfig(
        id=1, enabled=False, monitorizar_hijos=True, instance_id="00000000-0000-0000-0000-000000000005",
    )
    monkeypatch.setattr(central, "get_dashboard", lambda db=None: {})

    resultado = central.central_dashboard(
        request=_FakeRequestSinHeaders(), profundidad=3,
        db=_FakeDBDashboard(config, []), _=None,
    )
    assert resultado["self"]["status"] == "ok"


def test_dashboard_con_enabled_apagado_no_recorre_nodos_propios(monkeypatch):
    """`children` sale vacío con `enabled` apagado, aunque `monitorizar_hijos`
    esté prendido -"dejarse monitorear" no implica exponer los nodos
    propios: son dos preguntas distintas (ver docstring de
    CentralMonitorConfig)."""
    config = CentralMonitorConfig(
        id=1, enabled=False, monitorizar_hijos=True, instance_id="00000000-0000-0000-0000-000000000006",
    )
    nodo = MonitoredNode(id=1, name="Norte", url="http://10.0.0.5:8000",
                          username="viewer", password="secreta", enabled=True)
    capturado = {}

    def _consultar_arbol_falso(nodes, profundidad_restante):
        capturado["nodes"] = nodes
        return []

    monkeypatch.setattr(central, "consultar_arbol_de_todos", _consultar_arbol_falso)
    monkeypatch.setattr(central, "get_dashboard", lambda db=None: {})
    central.central_dashboard(
        request=_FakeRequestSinHeaders(), profundidad=3,
        db=_FakeDBDashboard(config, [nodo]), _=None,
    )
    assert capturado["nodes"] == []


# --- Nodos "squid_basico": sin usuario/contraseña que exigir ni enmascarar -
#
# Pedido en vivo, 2026-09-26: "no siempre el squid a monitorear será un
# squidmanager". Un nodo squid_basico no tiene cuenta -_to_response no debe
# fingir una máscara de contraseña que no existe, y create/update_node
# deben exigir usuario+contraseña SOLO para el tipo squidmanager.

from app.routes.central import create_node as _ruta_create_node, update_node as _ruta_update_node, NodeCreate, NodeUpdate


class _FakeAdmin:
    id = 1
    username = "admin"


class _FakeDBEscribible:
    """DB falsa que además soporta add/flush/commit/refresh como no-ops
    -create_node/update_node los llaman, a diferencia de las rutas de solo
    lectura que ya cubre FakeDBConNodo."""
    def __init__(self, nodo=None):
        self._nodo = nodo

    def query(self, model):
        if model is CentralMonitorConfig:
            return _FakeQueryUnNodo(_CONFIG_HABILITADA)
        return _FakeQueryUnNodo(self._nodo)

    def add(self, obj):
        pass

    def flush(self):
        pass

    def commit(self):
        pass

    def refresh(self, obj):
        pass


def test_to_response_de_nodo_squid_basico_no_finge_contrasena():
    nodo = MonitoredNode(id=2, name="Sur", tipo="squid_basico", url="http://10.0.0.9:3128",
                          username=None, password=None, enabled=True)
    resp = _to_response(nodo)
    assert resp["tipo"] == "squid_basico"
    assert resp["username"] is None
    assert resp["password"] is None


def test_crear_nodo_squidmanager_sin_usuario_rechazado():
    data = NodeCreate(name="Norte", tipo="squidmanager", url="http://10.0.0.5:8000")
    with pytest.raises(HTTPException) as exc:
        _ruta_create_node(data=data, db=_FakeDBEscribible(), current_admin=_FakeAdmin())
    assert exc.value.status_code == 400


def test_crear_nodo_squidmanager_sin_contrasena_rechazado():
    data = NodeCreate(name="Norte", tipo="squidmanager", url="http://10.0.0.5:8000", username="viewer")
    with pytest.raises(HTTPException) as exc:
        _ruta_create_node(data=data, db=_FakeDBEscribible(), current_admin=_FakeAdmin())
    assert exc.value.status_code == 400


def test_crear_nodo_squid_basico_sin_usuario_ni_contrasena_ok():
    data = NodeCreate(name="Sur", tipo="squid_basico", url="http://10.0.0.9:3128")
    resp = _ruta_create_node(data=data, db=_FakeDBEscribible(), current_admin=_FakeAdmin())
    assert resp["tipo"] == "squid_basico"
    assert resp["username"] is None
    assert resp["password"] is None


def test_actualizar_nodo_a_squid_basico_limpia_credenciales():
    nodo = MonitoredNode(id=7, name="Norte", tipo="squidmanager", url="http://10.0.0.5:8000",
                          username="viewer", password="secreta", enabled=True)
    resp = _ruta_update_node(node_id=7, data=NodeUpdate(tipo="squid_basico"),
                              db=_FakeDBEscribible(nodo), current_admin=_FakeAdmin())
    assert resp["tipo"] == "squid_basico"
    assert nodo.username is None
    assert nodo.password is None


def test_actualizar_nodo_a_squidmanager_sin_credenciales_rechazado():
    nodo = MonitoredNode(id=7, name="Sur", tipo="squid_basico", url="http://10.0.0.9:3128",
                          username=None, password=None, enabled=True)
    with pytest.raises(HTTPException) as exc:
        _ruta_update_node(node_id=7, data=NodeUpdate(tipo="squidmanager"),
                           db=_FakeDBEscribible(nodo), current_admin=_FakeAdmin())
    assert exc.value.status_code == 400


def test_actualizar_nodo_a_squidmanager_con_credenciales_nuevas_ok():
    nodo = MonitoredNode(id=7, name="Sur", tipo="squid_basico", url="http://10.0.0.9:3128",
                          username=None, password=None, enabled=True)
    resp = _ruta_update_node(
        node_id=7,
        data=NodeUpdate(tipo="squidmanager", username="viewer", password="nueva_clave"),
        db=_FakeDBEscribible(nodo), current_admin=_FakeAdmin(),
    )
    assert resp["tipo"] == "squidmanager"
    assert resp["password"] == "***"
