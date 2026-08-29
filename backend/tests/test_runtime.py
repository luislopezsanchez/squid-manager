"""Pruebas del adaptador que aísla al panel de cómo esté desplegado Squid.

Lo que se protege aquí no es el código de cada modo —eso solo se comprueba de
verdad ejecutándolo— sino el contrato entre los dos: que se elige el runtime
correcto, que el puerto que acaba en el squid.conf es el que corresponde a cada
despliegue, y que los dos hablan el mismo idioma al reportar contadores.

El caso que motiva la tercera prueba: si el modo nativo emitiera las etiquetas
con otro nombre o en otro orden, el analizador de métricas no fallaría, se
quedaría a cero. Un panel a cero con el proxy funcionando ya nos costó una
avería silenciosa una vez.
"""

import pytest

from app.services import metrics_service
from app.services.runtime import get_runtime, reset_runtime
from app.services.runtime.base import INTERNAL_SQUID_PORT
from app.services.runtime.docker_runtime import DockerRuntime
from app.services.runtime.native_runtime import NativeRuntime


@pytest.fixture(autouse=True)
def runtime_limpio():
    """El runtime se cachea; cada prueba parte de cero."""
    reset_runtime()
    yield
    reset_runtime()


# ---------------------------------------------------------------------------
# Eleccion del modo
# ---------------------------------------------------------------------------
def test_por_defecto_es_docker(monkeypatch):
    """Las instalaciones que ya existen no deben cambiar de comportamiento."""
    from app.config import settings

    monkeypatch.setattr(settings, "DEPLOY_MODE", "docker")
    assert isinstance(get_runtime(), DockerRuntime)


def test_modo_native_selecciona_el_runtime_nativo(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "DEPLOY_MODE", "native")
    assert isinstance(get_runtime(), NativeRuntime)


def test_un_modo_desconocido_cae_en_docker(monkeypatch):
    """Ante un valor mal escrito, el modo seguro es el que ya funcionaba."""
    from app.config import settings

    monkeypatch.setattr(settings, "DEPLOY_MODE", "kubernetes")
    assert isinstance(get_runtime(), DockerRuntime)


# ---------------------------------------------------------------------------
# El puerto: la diferencia de fondo entre los dos modos
# ---------------------------------------------------------------------------
def test_en_docker_squid_escucha_en_el_puerto_interno():
    """Docker publica hacia fuera el puerto del panel y lo mapea contra este."""
    assert DockerRuntime().listen_port("8080") == INTERNAL_SQUID_PORT


def test_en_nativo_squid_escucha_donde_diga_el_panel():
    """Sin mapeo de por medio, un puerto interno fijo dejaría el proxy sordo."""
    assert NativeRuntime().listen_port("8080") == "8080"


def test_en_nativo_no_hay_segunda_copia_del_puerto_que_sincronizar():
    ok, _ = NativeRuntime().sync_port_state("8080")
    assert ok


# ---------------------------------------------------------------------------
# Lectura de puertos en escucha (sin depender de ss ni netstat)
# ---------------------------------------------------------------------------
def test_detecta_los_puertos_en_escucha(tmp_path):
    # Formato real de /proc/net/tcp: 0A es LISTEN, 01 es ESTABLISHED.
    # 0x0C38 = 3128, 0x1F90 = 8000, 0x0050 = 80.
    proc_tcp = tmp_path / "tcp"
    proc_tcp.write_text(
        "  sl  local_address rem_address   st tx_queue rx_queue tr tm->when retrnsmt\n"
        "   0: 00000000:0C38 00000000:0000 0A 00000000:00000000 00:00000000 00000000\n"
        "   1: 0100007F:1F90 00000000:0000 0A 00000000:00000000 00:00000000 00000000\n"
        "   2: 0100007F:0050 0100007F:B3A2 01 00000000:00000000 00:00000000 00000000\n"
    )

    puertos = NativeRuntime._listening_ports((str(proc_tcp),))

    assert 3128 in puertos
    assert 8000 in puertos
    # Una conexion establecida no es alguien escuchando.
    assert 80 not in puertos


def test_un_proc_ausente_no_revienta(tmp_path):
    assert NativeRuntime._listening_ports((str(tmp_path / "no-existe"),)) == set()


# ---------------------------------------------------------------------------
# Contrato de formato entre los dos modos
# ---------------------------------------------------------------------------
def test_las_metricas_entienden_el_formato_nativo(monkeypatch):
    """El texto que produce el modo nativo lo interpreta el mismo analizador.

    Si esto se rompe, el panel no da error: se queda a cero.
    """
    salida_nativa = "\n".join([
        "Inter-|   Receive                                                |  Transmit",
        " face |bytes    packets errs drop fifo frame compressed multicast|bytes",
        "    lo:    1000      10    0    0    0     0          0         0    1000",
        "  eth0: 5000000    4000    0    0    0     0          0         0  2500000",
        "#CG#",
        "memcur 104857600",
        "memmax max",
        "usage_usec 12345678",
        "inactive_file 4194304",
        "MemTotal:        4028432 kB",
    ])

    class RuntimeNativoFalso:
        name = "native"

        def read_stats_raw(self):
            return salida_nativa

    monkeypatch.setattr(metrics_service, "get_runtime", lambda: RuntimeNativoFalso())

    datos = metrics_service._read_container_stats_raw()

    # Se prefiere eth0 sobre la suma de todas las interfaces.
    assert datos["rx_bytes"] == 5000000
    assert datos["tx_bytes"] == 2500000
    # memory.current menos el cache inactivo, igual que hace `docker stats`.
    assert datos["mem_usage"] == 104857600 - 4194304
    # "max" no es un numero: no hay tope y se usa la RAM del equipo.
    assert datos["mem_limit"] == 0
    assert datos["host_mem"] == 4028432 * 1024
    assert datos["cpu_usec"] == 12345678
