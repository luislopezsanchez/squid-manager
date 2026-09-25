"""Detección de anomalías por reglas simples -nada de IA opaca: cada alerta
sale de una condición concreta y explicable (ver cada regla abajo), sobre
los mismos datos de access.log que ya alimentan Actividad de red. Se manda
por los mismos canales que ya usa Notificaciones, bajo el evento
"security_alert" -el mismo toggle (notify_on_security_alert) que hasta
ahora existía en Notificaciones sin que nada lo disparara nunca: la regla
de fuerza bruta reutiliza la lógica que ya vivía sin usar en
routes/logs.py::security_alerts. No agrega ninguna tarjeta nueva al
dashboard -la idea es avisar activamente, no sumar otro lugar más para ir
a mirar por las dudas.

Reglas activas:
- Fuerza bruta: una IP con demasiadas 407 (autenticación fallida) en poco
  tiempo.
- Bloqueos en racha: un usuario con demasiadas peticiones denegadas en
  poco tiempo -alguien insistiendo contra la política, no el ruido normal
  de un enlace viejo o una redirección puntual.
- Pico de tráfico: la ventana reciente transfiere varias veces más que el
  promedio de las ventanas anteriores -un volumen que se sale de lo
  habitual para ESTA red, sin necesidad de fijar a mano un umbral
  absoluto que no tiene sentido de una instalación a otra.

Cada regla tiene su propio "enfriamiento" (_COOLDOWN_SECONDS): una vez
avisada una entidad (IP/usuario), no se repite la misma alerta en cada
tick mientras la condición se mantenga -una sola vez por hora como mucho,
no una notificación cada 5 minutos mientras dure el problema. El estado
de enfriamiento y el historial del pico de tráfico viven en memoria, no en
disco: si el backend reinicia, en el peor caso se manda una alerta de más
o se tarda un rato en tener de nuevo base de comparación -no justifica ni
una tabla nueva ni un archivo de estado.
"""

import logging
import threading
import time
from collections import Counter, deque

from app.database import SessionLocal
from app.services.log_service import get_recent_entries
from app.services.notification_service import notify_now

logger = logging.getLogger(__name__)

_POLL_SECONDS = 300      # cada 5 minutos alcanza -no es un vigilante en vivo.
_VENTANA_SEGUNDOS = 600  # 10 minutos de logs para evaluar las reglas.

_UMBRAL_AUTH_FALLIDA = 5       # 407 de la misma IP en la ventana
_UMBRAL_BLOQUEOS_USUARIO = 10  # denegadas del mismo usuario en la ventana
_UMBRAL_PICO_TRAFICO = 3.0     # veces el promedio de baldes anteriores
_MIN_BALDES_BASELINE = 3       # baldes de historial antes de evaluar el pico

_COOLDOWN_SECONDS = 3600  # no repetir la misma alerta antes de una hora

# Historial de bytes transferidos por balde de _POLL_SECONDS, para comparar
# el balde actual contra "lo habitual" en vez de un umbral fijo -~1h de
# historial con ticks de 5 minutos.
_historial_bytes: deque[float] = deque(maxlen=12)

# f"{regla}:{entidad}" -> timestamp de la última vez que se avisó.
_ultima_alerta: dict[str, float] = {}

# Últimas anomalías que de verdad se notificaron (no cada tick: solo cuando
# _aplicar_cooldown las deja pasar) -lo que consulta el aviso del dashboard,
# para quien no tiene email/Telegram configurado (o no los revisa) también
# vea que algo se detectó, sin tener que sumar una tabla en la BD para esto.
_historial: deque[dict] = deque(maxlen=50)


def _formatear_bytes(n: float) -> str:
    for unidad in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unidad}" if unidad != "B" else f"{n:.0f} {unidad}"
        n /= 1024
    return f"{n:.1f} PB"


def _detectar_fuerza_bruta(entries: list[dict]) -> list[tuple[str, str, str]]:
    fallidos = Counter(e["client_ip"] for e in entries if e["status"] == 407)
    minutos = _VENTANA_SEGUNDOS // 60
    return [
        (
            f"auth:{ip}",
            "SquidManager: posible fuerza bruta",
            f"La IP {ip} tuvo {n} intentos de autenticación fallidos (407) "
            f"en los últimos {minutos} minutos.",
        )
        for ip, n in fallidos.items() if n >= _UMBRAL_AUTH_FALLIDA
    ]


def _detectar_bloqueos_en_racha(entries: list[dict]) -> list[tuple[str, str, str]]:
    bloqueos = Counter(e["user"] for e in entries if e["denied"] and e["user"] and e["user"] != "-")
    minutos = _VENTANA_SEGUNDOS // 60
    return [
        (
            f"bloqueos:{user}",
            "SquidManager: bloqueos repetidos",
            f"El usuario {user} tuvo {n} peticiones bloqueadas en los "
            f"últimos {minutos} minutos.",
        )
        for user, n in bloqueos.items() if n >= _UMBRAL_BLOQUEOS_USUARIO
    ]


def _detectar_pico_trafico(entries: list[dict], historial: list[float]) -> tuple[list[tuple[str, str, str]], float]:
    """Devuelve las alertas (a lo sumo una) y el total de bytes de esta
    ventana -separado del historial real para poder probar la detección
    sin ensuciarlo (quien llama decide si lo agrega, ver _tick)."""
    total_bytes = sum(e["bytes"] for e in entries)
    if len(historial) < _MIN_BALDES_BASELINE:
        return [], total_bytes
    promedio = sum(historial) / len(historial)
    if promedio <= 0 or total_bytes < promedio * _UMBRAL_PICO_TRAFICO:
        return [], total_bytes
    return [(
        "pico_trafico",
        "SquidManager: pico de tráfico",
        f"La ventana reciente transfirió {_formatear_bytes(total_bytes)}, "
        f"frente a un promedio de {_formatear_bytes(promedio)} en las "
        f"ventanas anteriores.",
    )], total_bytes


def _aplicar_cooldown(
    alertas: list[tuple[str, str, str]], ahora: float, estado: dict[str, float],
) -> list[tuple[str, str, str]]:
    pendientes = []
    for clave, asunto, mensaje in alertas:
        ultima = estado.get(clave)
        if ultima is not None and ahora - ultima < _COOLDOWN_SECONDS:
            continue
        estado[clave] = ahora
        pendientes.append((clave, asunto, mensaje))
    return pendientes


def _tick() -> None:
    ahora = time.time()
    entries = get_recent_entries(_VENTANA_SEGUNDOS)

    alertas = _detectar_fuerza_bruta(entries) + _detectar_bloqueos_en_racha(entries)
    pico, total_bytes = _detectar_pico_trafico(entries, list(_historial_bytes))
    alertas += pico
    _historial_bytes.append(total_bytes)

    pendientes = _aplicar_cooldown(alertas, ahora, _ultima_alerta)
    if not pendientes:
        return

    db = SessionLocal()
    try:
        for clave, asunto, mensaje in pendientes:
            logger.warning(f"Anomalía detectada ({clave}): {mensaje}")
            notify_now(db, "security_alert", asunto, mensaje)
            _historial.append({"ts": ahora, "clave": clave, "asunto": asunto, "mensaje": mensaje})
    finally:
        db.close()


def get_anomalias_recientes(horas: float = 24, limit: int = 20) -> list[dict]:
    """Anomalías notificadas dentro de las últimas `horas` -lo que muestra el
    aviso del dashboard. Ordenadas de la más nueva a la más vieja."""
    corte = time.time() - horas * 3600
    recientes = [a for a in _historial if a["ts"] >= corte]
    recientes.sort(key=lambda a: a["ts"], reverse=True)
    return recientes[:limit]


def _loop() -> None:
    logger.info("Detector de anomalías iniciado")
    while True:
        try:
            _tick()
        except Exception as e:
            logger.error(f"Error en el detector de anomalías: {e}")
        time.sleep(_POLL_SECONDS)


def start_anomaly_detector() -> None:
    """Arranca el hilo de fondo una sola vez, al iniciar el backend."""
    thread = threading.Thread(target=_loop, name="anomaly-detector", daemon=True)
    thread.start()
