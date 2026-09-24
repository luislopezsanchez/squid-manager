"""Detección de anomalías por reglas simples -ver app/services/anomaly_service.py.

Cada regla se prueba como función pura (sin threading, sin DB, sin
notificaciones reales) y el enfriamiento se prueba aparte, igual que
_entradas() en test_metrics_service_rotacion.py separa el armado del
dato de la decisión de cuál camino tomar.
"""

from app.services import anomaly_service as asvc


def _entrada(ip="10.0.0.1", user="-", status=200, denied=False, bytes_=100):
    return {"client_ip": ip, "user": user, "status": status, "denied": denied, "bytes": bytes_}


# --- _detectar_fuerza_bruta --------------------------------------------------

def test_fuerza_bruta_detecta_ip_que_supera_el_umbral():
    entries = [_entrada(ip="1.1.1.1", status=407) for _ in range(asvc._UMBRAL_AUTH_FALLIDA)]
    alertas = asvc._detectar_fuerza_bruta(entries)
    assert len(alertas) == 1
    clave, asunto, mensaje = alertas[0]
    assert clave == "auth:1.1.1.1"
    assert "1.1.1.1" in mensaje


def test_fuerza_bruta_no_dispara_por_debajo_del_umbral():
    entries = [_entrada(ip="1.1.1.1", status=407) for _ in range(asvc._UMBRAL_AUTH_FALLIDA - 1)]
    assert asvc._detectar_fuerza_bruta(entries) == []


def test_fuerza_bruta_ignora_estados_que_no_son_407():
    entries = [_entrada(ip="1.1.1.1", status=403) for _ in range(asvc._UMBRAL_AUTH_FALLIDA + 5)]
    assert asvc._detectar_fuerza_bruta(entries) == []


# --- _detectar_bloqueos_en_racha --------------------------------------------

def test_bloqueos_en_racha_detecta_usuario_que_supera_el_umbral():
    entries = [_entrada(user="juan", denied=True) for _ in range(asvc._UMBRAL_BLOQUEOS_USUARIO)]
    alertas = asvc._detectar_bloqueos_en_racha(entries)
    assert len(alertas) == 1
    assert alertas[0][0] == "bloqueos:juan"


def test_bloqueos_en_racha_ignora_anonimos():
    # "-" es "sin usuario identificado" (ver log_service.parse_line) -no hay
    # a quién avisarle ni de quién hablar en la alerta.
    entries = [_entrada(user="-", denied=True) for _ in range(asvc._UMBRAL_BLOQUEOS_USUARIO + 5)]
    assert asvc._detectar_bloqueos_en_racha(entries) == []


def test_bloqueos_en_racha_ignora_peticiones_no_denegadas():
    entries = [_entrada(user="juan", denied=False) for _ in range(asvc._UMBRAL_BLOQUEOS_USUARIO + 5)]
    assert asvc._detectar_bloqueos_en_racha(entries) == []


# --- _detectar_pico_trafico ---------------------------------------------------

def test_pico_trafico_sin_baseline_no_dispara_pero_devuelve_el_total():
    entries = [_entrada(bytes_=10_000_000)]
    alertas, total = asvc._detectar_pico_trafico(entries, historial=[])
    assert alertas == []
    assert total == 10_000_000


def test_pico_trafico_dispara_si_supera_varias_veces_el_promedio():
    historial = [1000.0, 1000.0, 1000.0]
    entries = [_entrada(bytes_=10_000)]  # 10x el promedio, supera _UMBRAL_PICO_TRAFICO
    alertas, total = asvc._detectar_pico_trafico(entries, historial)
    assert total == 10_000
    assert len(alertas) == 1
    assert alertas[0][0] == "pico_trafico"


def test_pico_trafico_no_dispara_si_esta_dentro_de_lo_habitual():
    historial = [1000.0, 1000.0, 1000.0]
    entries = [_entrada(bytes_=1100)]
    alertas, _ = asvc._detectar_pico_trafico(entries, historial)
    assert alertas == []


# --- _aplicar_cooldown -------------------------------------------------------

def test_cooldown_deja_pasar_una_alerta_nueva():
    estado = {}
    pendientes = asvc._aplicar_cooldown([("clave1", "asunto", "mensaje")], ahora=1000.0, estado=estado)
    assert len(pendientes) == 1
    assert estado["clave1"] == 1000.0


def test_cooldown_bloquea_la_misma_clave_dentro_de_la_ventana():
    estado = {"clave1": 1000.0}
    pendientes = asvc._aplicar_cooldown(
        [("clave1", "asunto", "mensaje")], ahora=1000.0 + asvc._COOLDOWN_SECONDS - 1, estado=estado,
    )
    assert pendientes == []


def test_cooldown_deja_pasar_de_nuevo_tras_pasar_el_enfriamiento():
    estado = {"clave1": 1000.0}
    ahora = 1000.0 + asvc._COOLDOWN_SECONDS + 1
    pendientes = asvc._aplicar_cooldown([("clave1", "asunto", "mensaje")], ahora=ahora, estado=estado)
    assert len(pendientes) == 1
    assert estado["clave1"] == ahora


# --- _tick: integración con get_recent_entries y notify_now, todo mockeado --

def test_tick_notifica_cada_alerta_pendiente_y_no_revienta_sin_config(monkeypatch):
    entries = [_entrada(ip="2.2.2.2", status=407) for _ in range(asvc._UMBRAL_AUTH_FALLIDA)]
    monkeypatch.setattr(asvc, "get_recent_entries", lambda seconds: entries)
    monkeypatch.setattr(asvc, "_historial_bytes", asvc._historial_bytes.__class__(maxlen=12))
    monkeypatch.setattr(asvc, "_ultima_alerta", {})

    llamadas = []
    monkeypatch.setattr(asvc, "notify_now", lambda db, event_type, subject, message: llamadas.append((event_type, subject, message)))

    asvc._tick()

    assert len(llamadas) == 1
    event_type, subject, message = llamadas[0]
    assert event_type == "security_alert"
    assert "2.2.2.2" in message


def test_tick_no_repite_la_misma_alerta_en_el_siguiente_tick(monkeypatch):
    entries = [_entrada(ip="3.3.3.3", status=407) for _ in range(asvc._UMBRAL_AUTH_FALLIDA)]
    monkeypatch.setattr(asvc, "get_recent_entries", lambda seconds: entries)
    monkeypatch.setattr(asvc, "_historial_bytes", asvc._historial_bytes.__class__(maxlen=12))
    monkeypatch.setattr(asvc, "_ultima_alerta", {})

    llamadas = []
    monkeypatch.setattr(asvc, "notify_now", lambda db, event_type, subject, message: llamadas.append(1))

    asvc._tick()
    asvc._tick()

    assert len(llamadas) == 1
