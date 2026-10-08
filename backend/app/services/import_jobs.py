"""Tareas largas en segundo plano con progreso (importación masiva de usuarios).

Calcular el hash de miles de contraseñas tarda minutos (5000 usuarios ≈ 9 min en un servidor de 2 núcleos), más que
cualquier tiempo de espera razonable de una petición HTTP. La petición solo arranca la tarea y el panel pregunta cómo
va. El estado vive en memoria del proceso (el backend corre con un único worker); si el backend se reinicia a mitad de
una importación, la tarea se pierde y el panel lo ve como «desconocida».

Las contraseñas generadas se guardan en memoria SOLO hasta que el panel las recoge una vez (o 30 minutos): igual que antes,
no se guardan en claro en ningún otro sitio.
"""

import threading
import time
import uuid
from typing import Callable

_LOCK = threading.Lock()
_JOBS: dict[str, dict] = {}
_TTL = 30 * 60


def _limpiar(ahora: float) -> None:
    for jid in [j for j, d in _JOBS.items() if d["estado"] != "en_curso" and ahora - d["actualizado"] > _TTL]:
        _JOBS.pop(jid, None)


def hay_en_curso() -> bool:
    with _LOCK:
        return any(d["estado"] == "en_curso" for d in _JOBS.values())


def iniciar(total: int, trabajo: Callable[[Callable[[int, str], None]], dict]) -> str | None:
    """Arranca `trabajo(progreso)` en un hilo. Devuelve el id, o None si ya hay otra importación en curso.

    `progreso(hechos, fase)` actualiza lo que ve el panel; `trabajo` devuelve el informe final.
    """
    with _LOCK:
        ahora = time.time()
        _limpiar(ahora)
        if any(d["estado"] == "en_curso" for d in _JOBS.values()):
            return None
        jid = uuid.uuid4().hex
        _JOBS[jid] = {"estado": "en_curso", "fase": "calculando", "hechos": 0, "total": total,
                      "informe": None, "error": None, "iniciado": ahora, "actualizado": ahora}

    def progreso(hechos: int, fase: str = "calculando") -> None:
        with _LOCK:
            d = _JOBS.get(jid)
            if d:
                d.update(hechos=hechos, fase=fase, actualizado=time.time())

    def correr() -> None:
        try:
            informe = trabajo(progreso)
            with _LOCK:
                _JOBS[jid].update(estado="terminada", fase="listo", informe=informe, hechos=_JOBS[jid]["total"],
                                  actualizado=time.time())
        except Exception as e:  # el panel muestra el motivo; el detalle va al log
            import logging
            logging.getLogger(__name__).exception("Falló la importación masiva")
            with _LOCK:
                _JOBS[jid].update(estado="error", error=str(e) or type(e).__name__, actualizado=time.time())

    threading.Thread(target=correr, name=f"import-usuarios-{jid[:8]}", daemon=True).start()
    return jid


def estado(jid: str) -> dict | None:
    """Estado de la tarea. El informe con las contraseñas generadas se entrega una sola vez."""
    with _LOCK:
        d = _JOBS.get(jid)
        if d is None:
            return None
        salida = {k: d[k] for k in ("estado", "fase", "hechos", "total", "error")}
        salida["segundos"] = int(time.time() - d["iniciado"])
        if d["estado"] == "terminada" and d["informe"] is not None:
            salida["informe"] = d["informe"]
            d["informe"] = {**d["informe"], "credenciales": []}  # ya entregadas: no se conservan
        return salida
