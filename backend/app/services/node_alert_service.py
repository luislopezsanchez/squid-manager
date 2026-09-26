"""Alertas de "nodo caído" para Monitoreo Centralizado -mismo patrón que
anomaly_service.py (hilo de fondo propio, con su propio "enfriamiento" y su
propio historial en memoria), pero mirando el estado de los nodos
configurados en vez del access.log.

Por qué hace falta un hilo aparte: Panel Central hoy es puramente PULL -el
navegador de un admin pide el árbol cada 30s mientras tiene esa pestaña
abierta, pero el backend no chequea nada por su cuenta. Sin este hilo, un
nodo que se cae a las 3 de la mañana nunca se nota hasta que alguien abra
el panel de nuevo. Se manda por los mismos canales que ya usa
Notificaciones, bajo el evento "node_down" (notify_on_node_down).

Un nodo puede estar en tres estados (mismo criterio que TarjetaNodo en el
frontend, ver PanelCentral.tsx):
- "en_linea": responde bien -y si es un SquidManager, Squid también.
- "squid_caido": el panel de SquidManager responde, pero su Squid no (el
  Cache Manager real no contestó) -solo aplica si el nodo remoto expone ese
  dato (`squid_uptime` presente en su dashboard); si no lo expone (versión
  vieja, o un nodo squid_basico sin la ACL opcional), no hay forma de
  saberlo y no se lo cuenta como caído por eso.
- "sin_conexion": no se pudo ni loguear ni leer el dashboard.

Solo se notifica en una TRANSICIÓN (de en_linea a cualquier otro, o de
cualquier otro a en_linea) -nunca en cada tick mientras el problema se
mantiene: eso ya lo evita el propio hecho de comparar contra el estado
anterior, sin necesitar un cooldown de tiempo como el de anomaly_service
(acá "la condición se mantiene" ya de por sí no genera una transición
nueva). Sí hay un cooldown mínimo por nodo para el caso de un nodo
inestable que sube y baja seguido (flapping): no more de una notificación
por nodo cada _COOLDOWN_SECONDS, así no se manda un alud de emails.

La primera vez que se ve un nodo (arranque del backend, o un nodo recién
agregado) no notifica nada -solo registra el estado inicial: no hay forma
de saber si "ya estaba caído desde antes" es una transición real o el
estado de siempre, y avisar en cada arranque del backend sería ruido."""

import logging
import threading
import time
from collections import deque

from app.database import SessionLocal
from app.models.central_config import CentralMonitorConfig
from app.models.monitored_node import MonitoredNode
from app.services.central_monitor_service import consultar_nodo
from app.services.notification_service import notify_now

logger = logging.getLogger(__name__)

_POLL_SECONDS = 60       # más seguido que anomaly_service: acá "caído" es
                         # binario y sin falsos positivos por ruido de
                         # tráfico, no hace falta esperar 5 minutos para
                         # confiar en el dato.
_COOLDOWN_SECONDS = 900  # 15 min: no repetir la misma alerta de un nodo
                         # inestable (flapping) en cada vuelta.

# node_id -> último estado visto ("en_linea"/"squid_caido"/"sin_conexion").
_estado_anterior: dict[int, str] = {}

# node_id -> timestamp de la última vez que se notificó ALGO de ese nodo.
_ultima_notificacion: dict[int, float] = {}

# Últimas transiciones notificadas -lo que consulta el aviso de Panel
# Central, para quien no tiene email/Telegram configurado (o no los
# revisa) también vea que algo pasó, sin sumar una tabla en la BD para
# esto. Mismo patrón que anomaly_service._historial.
_historial: deque[dict] = deque(maxlen=50)


def _estado_de(resultado: dict) -> str:
    if resultado.get("status") != "ok":
        return "sin_conexion"
    data = resultado.get("data") or {}
    if "squid_uptime" in data and data.get("squid_uptime") is None:
        return "squid_caido"
    return "en_linea"


_ETIQUETAS_ESTADO = {
    "en_linea": "en línea",
    "squid_caido": "con Squid caído (el panel responde, pero Squid no)",
    "sin_conexion": "sin conexión",
}


def _tick() -> None:
    ahora = time.time()
    db = SessionLocal()
    try:
        config = db.query(CentralMonitorConfig).first()
        if not config or not config.enabled:
            return  # feature apagada -nada que chequear ni que avisar.

        nodes = db.query(MonitoredNode).filter(MonitoredNode.enabled.is_(True)).all()
        ids_vigentes = {n.id for n in nodes}
        # Poda nodos borrados o deshabilitados -sin esto, un servidor de
        # muy larga vida acumula entradas de nodos que ya no existen.
        for coleccion in (_estado_anterior, _ultima_notificacion):
            for id_viejo in set(coleccion) - ids_vigentes:
                del coleccion[id_viejo]

        for node in nodes:
            resultado = consultar_nodo(node)
            estado = _estado_de(resultado)
            anterior = _estado_anterior.get(node.id)

            if anterior is None:
                _estado_anterior[node.id] = estado
                continue  # primera vez que se ve este nodo -solo registra.

            if estado == anterior:
                continue  # sin cambios.

            ultima = _ultima_notificacion.get(node.id)
            if ultima is not None and ahora - ultima < _COOLDOWN_SECONDS:
                # OJO: acá NO se actualiza _estado_anterior. Si se
                # actualizara igual (aunque no se notifique), la transición
                # quedaría "tragada" para siempre -el próximo tick
                # compararía contra un estado que ya coincide con la
                # realidad y nunca volvería a intentar avisar, ni pasado
                # el cooldown. Dejando `anterior` sin tocar, el tick
                # siguiente vuelve a ver la misma transición pendiente y
                # reintenta -recién ahí se resuelve, notificada o no.
                # Bug real, encontrado en vivo 2026-09-27: la recuperación
                # de un nodo justo después de notificar su caída no
                # avisaba nunca, ni pasados los 15 minutos del cooldown.
                continue

            if estado == "en_linea":
                asunto = f'SquidManager: el nodo "{node.name}" volvió a estar en línea'
                mensaje = f'El nodo "{node.name}" ({node.url}) volvió a estar en línea, tras estar {_ETIQUETAS_ESTADO[anterior]}.'
            else:
                asunto = f'SquidManager: el nodo "{node.name}" está {_ETIQUETAS_ESTADO[estado]}'
                detalle = resultado.get("message") or ""
                mensaje = f'El nodo "{node.name}" ({node.url}) pasó a estar {_ETIQUETAS_ESTADO[estado]}.' + (f" Detalle: {detalle}" if detalle else "")

            logger.warning(f"Monitoreo centralizado: nodo '{node.name}' -> {estado} (antes: {anterior})")
            notify_now(db, "node_down", asunto, mensaje)
            _estado_anterior[node.id] = estado
            _ultima_notificacion[node.id] = ahora
            _historial.append({
                "ts": ahora, "node_id": node.id, "node_name": node.name,
                "estado": estado, "asunto": asunto, "mensaje": mensaje,
            })
    finally:
        db.close()


def get_alertas_nodos_recientes(horas: float = 24, limit: int = 20) -> list[dict]:
    """Transiciones de estado notificadas dentro de las últimas `horas`
    -lo que muestra el aviso en Panel Central. Ordenadas de la más nueva a
    la más vieja, mismo criterio que anomaly_service.get_anomalias_recientes."""
    corte = time.time() - horas * 3600
    recientes = [a for a in _historial if a["ts"] >= corte]
    recientes.sort(key=lambda a: a["ts"], reverse=True)
    return recientes[:limit]


def _loop() -> None:
    logger.info("Monitor de alertas de nodos iniciado")
    while True:
        try:
            _tick()
        except Exception as e:
            logger.error(f"Error en el monitor de alertas de nodos: {e}")
        time.sleep(_POLL_SECONDS)


def start_node_alert_monitor() -> None:
    """Arranca el hilo de fondo una sola vez, al iniciar el backend."""
    thread = threading.Thread(target=_loop, name="node-alert-monitor", daemon=True)
    thread.start()
