"""start_squid() -botón "Iniciar Squid" del aviso del dashboard cuando el
servicio está caído (ver app/services/squid_service.py). No hay una
operación "start" propia en la interfaz de runtime (runtime/base.py): un
`restart` sobre un servicio detenido lo arranca igual, así que start_squid()
es solo un wrapper con su propio logueo -se prueba que delega bien.
"""

from app.services import squid_service


class RuntimeDePrueba:
    name = "prueba"

    def __init__(self, ok: bool, mensaje: str):
        self._ok = ok
        self._mensaje = mensaje
        self.llamado = False

    def restart(self) -> tuple[bool, str]:
        self.llamado = True
        return self._ok, self._mensaje


def test_start_squid_delega_en_restart_del_runtime(monkeypatch):
    runtime = RuntimeDePrueba(True, "Squid reiniciado correctamente")
    monkeypatch.setattr(squid_service, "get_runtime", lambda: runtime)

    ok, mensaje = squid_service.start_squid()

    assert runtime.llamado is True
    assert ok is True
    assert mensaje == "Squid reiniciado correctamente"


def test_start_squid_propaga_el_error_del_runtime(monkeypatch):
    runtime = RuntimeDePrueba(False, "systemctl restart squid falló: unit not found")
    monkeypatch.setattr(squid_service, "get_runtime", lambda: runtime)

    ok, mensaje = squid_service.start_squid()

    assert ok is False
    assert "unit not found" in mensaje
