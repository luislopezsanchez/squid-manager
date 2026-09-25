"""_actualizar_conectados(): "conectado desde" de los usuarios activos del
dashboard (ver metrics_service.py) -no es una sesión real, solo cuánto hace
que este backend viene viendo a cada usuario activo de forma consecutiva,
sondeo a sondeo (ver el comentario largo junto a la definición)."""

from app.services import metrics_service as ms


def _limpiar(monkeypatch):
    monkeypatch.setattr(ms, "_ultima_vez_activo", {})
    monkeypatch.setattr(ms, "_conectado_desde", {})


def test_primera_aparicion_cuenta_desde_ahora(monkeypatch):
    _limpiar(monkeypatch)
    monkeypatch.setattr(ms.time, "time", lambda: 1000.0)

    detalle = ms._actualizar_conectados({"juan"})

    assert detalle == [{"user": "juan", "conectado_desde_segundos": 0}]


def test_sondeos_seguidos_mantienen_el_inicio_de_la_racha(monkeypatch):
    _limpiar(monkeypatch)
    monkeypatch.setattr(ms.time, "time", lambda: 1000.0)
    ms._actualizar_conectados({"juan"})

    monkeypatch.setattr(ms.time, "time", lambda: 1030.0)
    detalle = ms._actualizar_conectados({"juan"})

    assert detalle == [{"user": "juan", "conectado_desde_segundos": 30}]


def test_hueco_largo_reinicia_la_racha(monkeypatch):
    _limpiar(monkeypatch)
    monkeypatch.setattr(ms.time, "time", lambda: 1000.0)
    ms._actualizar_conectados({"juan"})

    # Más de _HUECO_MAX_SEGUNDOS sin aparecer: la próxima vez es una
    # conexión "nueva", no sigue sumando desde la primera.
    monkeypatch.setattr(ms.time, "time", lambda: 1000.0 + ms._HUECO_MAX_SEGUNDOS + 1)
    detalle = ms._actualizar_conectados({"juan"})

    assert detalle == [{"user": "juan", "conectado_desde_segundos": 0}]


def test_usuario_que_ya_no_esta_activo_no_aparece_en_el_detalle(monkeypatch):
    _limpiar(monkeypatch)
    monkeypatch.setattr(ms.time, "time", lambda: 1000.0)
    ms._actualizar_conectados({"juan", "maria"})

    monkeypatch.setattr(ms.time, "time", lambda: 1010.0)
    detalle = ms._actualizar_conectados({"juan"})

    assert [d["user"] for d in detalle] == ["juan"]


def test_housekeeping_olvida_usuarios_inactivos_hace_mucho(monkeypatch):
    _limpiar(monkeypatch)
    monkeypatch.setattr(ms.time, "time", lambda: 1000.0)
    ms._actualizar_conectados({"juan"})

    # Mucho después, sin que "juan" vuelva a aparecer nunca: se olvida
    # (no queda para siempre en memoria).
    monkeypatch.setattr(ms.time, "time", lambda: 1000.0 + ms._OLVIDAR_TRAS_SEGUNDOS + 1)
    ms._actualizar_conectados(set())

    assert "juan" not in ms._ultima_vez_activo
    assert "juan" not in ms._conectado_desde


def test_ordena_del_que_lleva_mas_tiempo_al_recien_llegado(monkeypatch):
    _limpiar(monkeypatch)
    monkeypatch.setattr(ms.time, "time", lambda: 1000.0)
    ms._actualizar_conectados({"viejo"})

    monkeypatch.setattr(ms.time, "time", lambda: 1050.0)
    detalle = ms._actualizar_conectados({"viejo", "nuevo"})

    assert [d["user"] for d in detalle] == ["viejo", "nuevo"]
