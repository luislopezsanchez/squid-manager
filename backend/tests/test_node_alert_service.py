"""Alertas de "nodo caído" -ver app/services/node_alert_service.py.

Mismo criterio que test_anomaly_service.py: _tick() se prueba con
SessionLocal, consultar_nodo y notify_now mockeados (nunca hay una DB de
verdad en esta suite, ver conftest.py), y cada dict/deque de estado en
memoria se resetea a mano en cada test que lo necesita -son módulo-level,
no fixtures, así que un test no puede heredar el estado que dejó otro."""

from app.services import node_alert_service as nas
from app.models.central_config import CentralMonitorConfig
from app.models.monitored_node import MonitoredNode


def _resultado(status="ok", squid_uptime="__omitido__", message=None):
    """squid_uptime="__omitido__" (sentinel, no None) significa "ni
    siquiera está la clave" -el caso de un nodo squid_basico sin la ACL
    opcional, o un SquidManager de versión vieja."""
    data = {}
    if squid_uptime != "__omitido__":
        data["squid_uptime"] = squid_uptime
    resultado = {"status": status, "data": data}
    if message:
        resultado["message"] = message
    return resultado


# --- _estado_de --------------------------------------------------------

def test_estado_de_ok_con_traffic_es_en_linea():
    assert nas._estado_de({"status": "ok", "data": {"traffic": {}}}) == "en_linea"


def test_estado_de_ok_sin_squid_uptime_es_en_linea():
    """La clave ni existe -versión vieja o squid_basico sin la ACL
    opcional: "no lo sé" no es lo mismo que "está caído"."""
    assert nas._estado_de(_resultado(squid_uptime="__omitido__")) == "en_linea"


def test_estado_de_squid_uptime_presente_pero_null_es_squid_caido():
    assert nas._estado_de(_resultado(squid_uptime=None)) == "squid_caido"


def test_estado_de_squid_uptime_con_numero_es_en_linea():
    assert nas._estado_de(_resultado(squid_uptime=123.4)) == "en_linea"


def test_estado_de_status_error_es_sin_conexion():
    assert nas._estado_de({"status": "error", "message": "no se pudo conectar"}) == "sin_conexion"


# --- FakeDB para _tick() ------------------------------------------------

class _FakeQuery:
    def __init__(self, resultado):
        self._resultado = resultado

    def filter(self, *a, **k):
        return self

    def first(self):
        return self._resultado

    def all(self):
        return self._resultado


class _FakeDB:
    def __init__(self, config, nodes):
        self._config = config
        self._nodes = nodes

    def query(self, model):
        if model is CentralMonitorConfig:
            return _FakeQuery(self._config)
        return _FakeQuery(self._nodes)

    def close(self):
        pass


def _nodo(id=1, name="Sucursal Norte", url="http://10.0.0.5:3000", enabled=True):
    return MonitoredNode(id=id, name=name, url=url, username="viewer", password="secreta", enabled=enabled)


def _preparar(monkeypatch, config_enabled=True, nodes=None, resultados=None):
    """resultados: dict node_id -> resultado de consultar_nodo (o una lista
    de resultados sucesivos, para simular tick tras tick)."""
    nodes = nodes if nodes is not None else [_nodo()]
    config = CentralMonitorConfig(enabled=config_enabled)
    monkeypatch.setattr(nas, "SessionLocal", lambda: _FakeDB(config, nodes))
    monkeypatch.setattr(nas, "_estado_anterior", {})
    monkeypatch.setattr(nas, "_ultima_notificacion", {})
    monkeypatch.setattr(nas, "_historial", nas._historial.__class__(maxlen=50))

    llamadas = []
    monkeypatch.setattr(nas, "notify_now", lambda db, event_type, subject, message: llamadas.append((event_type, subject, message)))

    if resultados is not None:
        cola = list(resultados)
        monkeypatch.setattr(nas, "consultar_nodo", lambda node: cola.pop(0))

    return llamadas


# --- _tick ---------------------------------------------------------------

def test_tick_primera_vez_no_notifica_solo_registra(monkeypatch):
    llamadas = _preparar(monkeypatch, resultados=[_resultado()])
    nas._tick()
    assert llamadas == []
    assert nas._estado_anterior[1] == "en_linea"


def test_tick_detecta_transicion_a_caido_y_notifica(monkeypatch):
    llamadas = _preparar(monkeypatch, resultados=[
        _resultado(),                                    # primer tick: en línea
        {"status": "error", "message": "sin conexión"},   # segundo tick: cae
    ])
    nas._tick()
    nas._tick()
    assert len(llamadas) == 1
    event_type, subject, message = llamadas[0]
    assert event_type == "node_down"
    assert "Sucursal Norte" in subject


def test_tick_detecta_recuperacion_y_notifica(monkeypatch):
    llamadas = _preparar(monkeypatch, resultados=[
        {"status": "error", "message": "sin conexión"},
        _resultado(),
    ])
    nas._tick()
    nas._tick()
    assert len(llamadas) == 1
    assert "volvió a estar en línea" in llamadas[0][1]


def test_tick_no_notifica_si_no_hay_cambio_de_estado(monkeypatch):
    llamadas = _preparar(monkeypatch, resultados=[_resultado(), _resultado()])
    nas._tick()
    nas._tick()
    assert llamadas == []


def test_tick_respeta_cooldown_por_nodo(monkeypatch):
    llamadas = _preparar(monkeypatch, resultados=[
        _resultado(),
        {"status": "error", "message": "cae"},
        _resultado(),  # se recupera enseguida, todavía dentro del cooldown
    ])
    reloj = {"ahora": 1000.0}
    monkeypatch.setattr(nas.time, "time", lambda: reloj["ahora"])

    nas._tick()
    reloj["ahora"] += 10
    nas._tick()  # cae -> notifica
    reloj["ahora"] += 10  # todavía muy poco tiempo, dentro de _COOLDOWN_SECONDS
    nas._tick()  # se recupera, pero el cooldown lo frena

    assert len(llamadas) == 1


def test_tick_notifica_de_nuevo_tras_pasar_el_cooldown(monkeypatch):
    llamadas = _preparar(monkeypatch, resultados=[
        _resultado(),
        {"status": "error", "message": "cae"},
        _resultado(),
    ])
    reloj = {"ahora": 1000.0}
    monkeypatch.setattr(nas.time, "time", lambda: reloj["ahora"])

    nas._tick()
    reloj["ahora"] += 10
    nas._tick()
    reloj["ahora"] += nas._COOLDOWN_SECONDS + 1
    nas._tick()

    assert len(llamadas) == 2


def test_tick_transicion_suprimida_por_cooldown_no_se_pierde_para_siempre(monkeypatch):
    """Bug real encontrado en vivo, 2026-09-27: si la recuperación de un
    nodo coincide con el cooldown de la caída recién notificada, no debe
    perderse para siempre -debe reintentarse en un tick posterior, ya
    fuera del cooldown."""
    llamadas = _preparar(monkeypatch, resultados=[
        _resultado(),                              # tick1: en línea (primera vez, no notifica)
        {"status": "error", "message": "cae"},      # tick2: cae -> notifica, arranca cooldown
        _resultado(),                                # tick3: ya recuperado, pero DENTRO del cooldown
        _resultado(),                                # tick4: sigue recuperado, ya pasado el cooldown
    ])
    reloj = {"ahora": 1000.0}
    monkeypatch.setattr(nas.time, "time", lambda: reloj["ahora"])

    nas._tick()
    reloj["ahora"] += 10
    nas._tick()  # cae -> notifica (1)
    assert len(llamadas) == 1

    reloj["ahora"] += 10  # todavía dentro del cooldown
    nas._tick()  # recuperado, pero el cooldown lo frena -no debe perderse
    assert len(llamadas) == 1

    reloj["ahora"] += nas._COOLDOWN_SECONDS + 1  # ya pasó el cooldown
    nas._tick()  # ahora sí, la recuperación pendiente se notifica
    assert len(llamadas) == 2
    assert "volvió a estar en línea" in llamadas[1][1]


def test_tick_no_hace_nada_si_central_monitor_esta_deshabilitado(monkeypatch):
    llamadas = _preparar(monkeypatch, config_enabled=False, resultados=[_resultado()])
    nas._tick()
    assert llamadas == []
    assert nas._estado_anterior == {}


def test_tick_ignora_nodos_deshabilitados(monkeypatch):
    """db.query(MonitoredNode).filter(enabled==True) ya los saca -acá se
    verifica que consultar_nodo ni se llama para ellos."""
    llamado = {"n": 0}

    def _consultar(node):
        llamado["n"] += 1
        return _resultado()

    config = CentralMonitorConfig(enabled=True)
    monkeypatch.setattr(nas, "SessionLocal", lambda: _FakeDB(config, []))  # el filtro ya los excluyó
    monkeypatch.setattr(nas, "_estado_anterior", {})
    monkeypatch.setattr(nas, "_ultima_notificacion", {})
    monkeypatch.setattr(nas, "consultar_nodo", _consultar)
    monkeypatch.setattr(nas, "notify_now", lambda *a, **k: None)

    nas._tick()
    assert llamado["n"] == 0


def test_tick_poda_estado_de_nodos_borrados(monkeypatch):
    monkeypatch.setattr(nas, "_estado_anterior", {1: "en_linea", 99: "sin_conexion"})
    monkeypatch.setattr(nas, "_ultima_notificacion", {99: 123.0})
    llamadas = _preparar(monkeypatch, nodes=[_nodo(id=1)], resultados=[_resultado()])
    # _preparar pisa _estado_anterior con {} -reponemos el estado sucio
    # DESPUÉS, ya con el resto del entorno armado.
    nas._estado_anterior[99] = "sin_conexion"
    nas._ultima_notificacion[99] = 123.0

    nas._tick()

    assert 99 not in nas._estado_anterior
    assert 99 not in nas._ultima_notificacion
    assert llamadas == []


# --- get_alertas_nodos_recientes ----------------------------------------

def test_get_alertas_nodos_recientes_filtra_por_antiguedad(monkeypatch):
    ahora = 1_000_000.0
    monkeypatch.setattr(nas.time, "time", lambda: ahora)
    monkeypatch.setattr(nas, "_historial", nas._historial.__class__([
        {"ts": ahora - 3600, "node_name": "reciente", "estado": "sin_conexion", "mensaje": "hace 1h"},
        {"ts": ahora - 90000, "node_name": "vieja", "estado": "sin_conexion", "mensaje": "hace 25h"},
    ], maxlen=50))

    recientes = nas.get_alertas_nodos_recientes(horas=24)

    assert len(recientes) == 1
    assert recientes[0]["node_name"] == "reciente"


def test_get_alertas_nodos_recientes_ordena_de_la_mas_nueva_a_la_mas_vieja(monkeypatch):
    ahora = 1_000_000.0
    monkeypatch.setattr(nas.time, "time", lambda: ahora)
    monkeypatch.setattr(nas, "_historial", nas._historial.__class__([
        {"ts": ahora - 500, "node_name": "vieja", "estado": "sin_conexion", "mensaje": "..."},
        {"ts": ahora - 10, "node_name": "nueva", "estado": "sin_conexion", "mensaje": "..."},
    ], maxlen=50))

    recientes = nas.get_alertas_nodos_recientes()

    assert [r["node_name"] for r in recientes] == ["nueva", "vieja"]
