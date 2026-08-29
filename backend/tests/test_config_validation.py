"""Pruebas de la validación del squid.conf antes de aplicarlo.

El caso que motivó estas pruebas: `squid -k parse` avisa por ERROR de una
directiva obsoleta pero termina con éxito. Mirando solo el código de salida, la
configuración se daba por buena y la directiva quedaba escrita sin hacer nada,
con el único rastro de una línea en un log que nadie mira. Así se coló un
`dns_v4_first` que Squid 6 ya no soporta.

Ahora quien ejecuta el parse es el runtime, así que las pruebas lo sustituyen a
él en lugar de al cliente de Docker: valen igual para los dos despliegues.
"""

import pytest

from app.services import squid_service


class RuntimeDePrueba:
    """Runtime que devuelve un resultado de `squid -k parse` prefabricado."""

    name = "prueba"

    def __init__(self, exit_code: int, salida: str):
        self._exit_code = exit_code
        self._salida = salida
        self.ruta_recibida = None

    def parse_config(self, path: str) -> tuple[int, str]:
        self.ruta_recibida = path
        return self._exit_code, self._salida


@pytest.fixture
def candidato_en_tmp(tmp_path, monkeypatch):
    """Escribe la configuración candidata en un temporal, no en /etc/squid."""
    monkeypatch.setattr(
        squid_service.settings, "SQUID_CONFIG_PATH", str(tmp_path / "squid.conf")
    )
    return tmp_path


def _con_runtime(monkeypatch, exit_code, salida) -> RuntimeDePrueba:
    runtime = RuntimeDePrueba(exit_code, salida)
    monkeypatch.setattr(squid_service, "get_runtime", lambda: runtime)
    return runtime


def test_configuracion_limpia_es_valida(monkeypatch, candidato_en_tmp):
    _con_runtime(monkeypatch, 0, "Processing: http_port 3128\n")
    ok, mensaje = squid_service.validate_squid_config("http_port 3128\n")
    assert ok
    assert mensaje == "Configuración válida"


def test_directiva_obsoleta_se_rechaza_aunque_squid_termine_con_exito(
    monkeypatch, candidato_en_tmp
):
    """El fallo real: código de salida 0 pero ERROR en la salida."""
    salida = (
        "2026/08/25 12:25:34| Processing: dns_v4_first on\n"
        "2026/08/25 12:25:34| ERROR: Directive 'dns_v4_first' is obsolete.\n"
        "2026/08/25 12:25:34| dns_v4_first : Remove this line.\n"
    )
    _con_runtime(monkeypatch, 0, salida)

    ok, mensaje = squid_service.validate_squid_config("dns_v4_first on\n")
    assert not ok
    assert "obsolete" in mensaje


def test_error_de_sintaxis_se_rechaza(monkeypatch, candidato_en_tmp):
    salida = "FATAL: Bungled squid.conf line 4: http_port abc\n"
    _con_runtime(monkeypatch, 1, salida)

    ok, mensaje = squid_service.validate_squid_config("http_port abc\n")
    assert not ok
    assert "FATAL" in mensaje


def test_los_avisos_no_impiden_aplicar(monkeypatch, candidato_en_tmp):
    """Un WARNING informa, pero la configuración sigue siendo utilizable."""
    salida = "WARNING: ACL 'localnet' is not used in any http_access rule.\n"
    _con_runtime(monkeypatch, 0, salida)

    ok, mensaje = squid_service.validate_squid_config("http_port 3128\n")
    assert ok
    assert "WARNING" in mensaje


def test_no_se_toca_el_squid_conf_en_uso(monkeypatch, candidato_en_tmp):
    """La validación escribe en un fichero aparte, nunca sobre el que está activo.

    Es lo que evita que una configuración rota tumbe el proxy: si el parse
    falla, el fichero en uso sigue intacto.
    """
    en_uso = candidato_en_tmp / "squid.conf"
    en_uso.write_text("http_port 3128\n")

    runtime = _con_runtime(monkeypatch, 1, "FATAL: roto\n")
    ok, _ = squid_service.validate_squid_config("esto esta roto\n")

    assert not ok
    assert en_uso.read_text() == "http_port 3128\n"
    assert runtime.ruta_recibida.endswith(".candidate")
