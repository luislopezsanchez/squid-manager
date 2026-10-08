"""Importación masiva en segundo plano: una tarea a la vez, progreso, informe entregado una sola vez, y el tope de filas."""

import time

import pytest

from app.services import import_jobs
from app.services import user_import_service as imp
from app.routes import proxy_users as rutas


@pytest.fixture(autouse=True)
def _limpio():
    import_jobs._JOBS.clear()
    yield
    import_jobs._JOBS.clear()


def _esperar(jid, estado_final="terminada", segs=5):
    t0 = time.time()
    while time.time() - t0 < segs:
        e = import_jobs.estado(jid)
        if e and e["estado"] != "en_curso":
            return e
        time.sleep(0.02)
    raise AssertionError("la tarea no terminó")


def test_tarea_con_progreso_e_informe_unico():
    def trabajo(progreso):
        for i in range(1, 4):
            progreso(i, "calculando")
        progreso(3, "guardando")
        return {"creados": 3, "credenciales": [{"usuario": "a", "password": "p"}]}

    jid = import_jobs.iniciar(3, trabajo)
    e = _esperar(jid)
    assert e["estado"] == "terminada" and e["hechos"] == 3 and e["informe"]["credenciales"]
    # El segundo sondeo ya no trae las contraseñas generadas.
    assert import_jobs.estado(jid)["informe"]["credenciales"] == []


def test_solo_una_importacion_a_la_vez():
    import threading
    liberar = threading.Event()
    primera = import_jobs.iniciar(1, lambda p: (liberar.wait(5), {})[1])
    assert primera and import_jobs.hay_en_curso()
    assert import_jobs.iniciar(1, lambda p: {}) is None
    liberar.set()
    _esperar(primera)
    assert import_jobs.iniciar(1, lambda p: {}) is not None


def test_un_fallo_se_ve_como_error_y_no_tumba_nada():
    def roto(progreso):
        raise RuntimeError("se cayó la base")
    e = _esperar(import_jobs.iniciar(1, roto))
    assert e["estado"] == "error" and "se cayó la base" in e["error"]


def test_tarea_desconocida():
    assert import_jobs.estado("no-existe") is None


def test_el_hash_en_paralelo_informa_del_avance(monkeypatch):
    monkeypatch.setattr(rutas, "_hashes", lambda u, p, r: ("h", "l", "d"))
    visto = []
    out = rutas._hashes_en_paralelo([(f"u{i}", "x") for i in range(10)], "realm", visto.append)
    assert len(out) == 10 and sorted(visto) == list(range(1, 11))


def test_tope_de_filas_5000_en_directo_y_20000_en_segundo_plano():
    cuerpo = "usuario\n" + "\n".join(f"u{i}" for i in range(6000))
    with pytest.raises(ValueError) as e:
        imp.parse_archivo("u.csv", cuerpo.encode())
    assert "5000" in str(e.value)
    filas, errores = imp.parse_archivo("u.csv", cuerpo.encode(), max_filas=imp.MAX_FILAS_SEGUNDO_PLANO)
    assert len(filas) == 6000 and not errores
    grande = "usuario\n" + "\n".join(f"u{i}" for i in range(20001))
    with pytest.raises(ValueError):
        imp.parse_archivo("u.csv", grande.encode(), max_filas=imp.MAX_FILAS_SEGUNDO_PLANO)
