"""Progreso de "Aplicar cambios", en memoria, para que el panel pueda
mostrar una barra mientras la petición POST /squid/apply sigue en curso.

No hay nada que persistir: es un solo apply a la vez (ver _apply_lock en
squid_service.py) y el propio proceso del backend es efímero entre
reinicios -si el backend se reinicia a mitad de un apply, no hay progreso
que reportar porque tampoco hay apply en curso. Un módulo en memoria como
config_state.py, no una tabla ni un archivo.
"""
import threading

_lock = threading.Lock()
_estado = {"activo": False, "paso": "", "pct": 0}

# (paso, porcentaje al COMENZAR ese paso). Los pasos siguen el mismo orden
# que _apply_squid_config en squid_service.py -si ese flujo cambia, esta
# lista también. El más lento con diferencia es "recargando" (squid -k
# parse + reconfigure vuelven a cargar cualquier ACL de archivo grande),
# así que se le deja el tramo más largo del progreso.
PASO_ARCHIVOS_ACL = ("archivos_acl", 5)
PASO_VALIDANDO = ("validando", 15)
PASO_DNS = ("dns", 35)
PASO_PROXY_PADRE = ("proxy_padre", 45)
PASO_ESCRIBIENDO = ("escribiendo", 55)
PASO_AUXILIARES = ("auxiliares", 65)
PASO_RECARGANDO = ("recargando", 75)


def iniciar() -> None:
    with _lock:
        _estado.update(activo=True, paso="iniciando", pct=0)


def avanzar(paso: tuple[str, int]) -> None:
    nombre, pct = paso
    with _lock:
        if _estado["activo"]:
            _estado.update(paso=nombre, pct=pct)


def finalizar() -> None:
    with _lock:
        _estado.update(activo=False, paso="", pct=100)


def estado() -> dict:
    with _lock:
        return dict(_estado)
