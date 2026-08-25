"""Pruebas de la validación del squid.conf antes de aplicarlo.

El caso que motivó estas pruebas: `squid -k parse` avisa por ERROR de una
directiva obsoleta pero termina con éxito. Mirando solo el código de salida, la
configuración se daba por buena y la directiva quedaba escrita sin hacer nada,
con el único rastro de una línea en un log que nadie mira. Así se coló un
`dns_v4_first` que Squid 6 ya no soporta.
"""

from app.services import squid_service


class FakeResultado:
    def __init__(self, exit_code, salida):
        self.exit_code = exit_code
        self.output = salida.encode()


class FakeContenedor:
    status = "running"

    def __init__(self, resultado):
        self._resultado = resultado

    def exec_run(self, *args, **kwargs):
        return self._resultado


class FakeCliente:
    def __init__(self, resultado):
        self.containers = self
        self._resultado = resultado

    def get(self, nombre):
        return FakeContenedor(self._resultado)


def test_configuracion_limpia_es_valida(monkeypatch):
    monkeypatch.setattr(squid_service, "_get_docker_client",
                        lambda: FakeCliente(FakeResultado(0, "Processing: http_port 3128\n")))
    ok, mensaje = squid_service.validate_squid_config("http_port 3128\n")
    assert ok
    assert mensaje == "Configuración válida"


def test_directiva_obsoleta_se_rechaza_aunque_squid_termine_con_exito(monkeypatch):
    """El fallo real: código de salida 0 pero ERROR en la salida."""
    salida = (
        "2026/08/25 12:25:34| Processing: dns_v4_first on\n"
        "2026/08/25 12:25:34| ERROR: Directive 'dns_v4_first' is obsolete.\n"
        "2026/08/25 12:25:34| dns_v4_first : Remove this line.\n"
    )
    monkeypatch.setattr(squid_service, "_get_docker_client",
                        lambda: FakeCliente(FakeResultado(0, salida)))

    ok, mensaje = squid_service.validate_squid_config("dns_v4_first on\n")
    assert not ok
    assert "obsolete" in mensaje


def test_error_de_sintaxis_se_rechaza(monkeypatch):
    salida = "FATAL: Bungled squid.conf line 4: http_port abc\n"
    monkeypatch.setattr(squid_service, "_get_docker_client",
                        lambda: FakeCliente(FakeResultado(1, salida)))

    ok, mensaje = squid_service.validate_squid_config("http_port abc\n")
    assert not ok
    assert "FATAL" in mensaje


def test_los_avisos_no_impiden_aplicar(monkeypatch):
    """Un WARNING informa, pero la configuración sigue siendo utilizable."""
    salida = "WARNING: ACL 'localnet' is not used in any http_access rule.\n"
    monkeypatch.setattr(squid_service, "_get_docker_client",
                        lambda: FakeCliente(FakeResultado(0, salida)))

    ok, mensaje = squid_service.validate_squid_config("http_port 3128\n")
    assert ok
    assert "WARNING" in mensaje
