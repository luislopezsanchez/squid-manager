"""Helper de ACL externa de Squid que siempre responde OK con un mensaje
fijo (squid/static_message_helper.py) -ver el motivo dinámico por regla en
config_generator.py.

Standalone respecto al backend a propósito, mismo patrón que
test_domain_block_helper.py.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

if sys.platform == "win32":
    pytest.skip(
        "squid/static_message_helper.py importa el módulo syslog (exclusivo de Unix)",
        allow_module_level=True,
    )


def _raiz_del_proyecto() -> Path | None:
    for base in Path(__file__).resolve().parents:
        if (base / "squid" / "static_message_helper.py").is_file():
            return base
    return None


def _cargar_modulo():
    raiz = _raiz_del_proyecto()
    assert raiz, "no se encontró squid/static_message_helper.py"
    ruta = raiz / "squid" / "static_message_helper.py"

    spec = importlib.util.spec_from_file_location("static_message_helper", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_devuelve_ok_con_una_sola_palabra():
    mod = _cargar_modulo()
    assert mod.handle("bloqueado") == 'OK message="bloqueado"'


def test_reconstruye_varias_palabras_sueltas_en_un_solo_texto():
    # Sin comillas en squid.conf (ver el porqué en el docstring del
    # módulo), el motivo llega partido en varios argumentos de %DATA, cada
    # uno URL-encoded por separado -Squid junta cada palabra suelta de la
    # línea `acl ...` en %DATA, separadas por espacio.
    mod = _cargar_modulo()
    assert mod.handle("Bloqueado por horario de oficina") == 'OK message="Bloqueado por horario de oficina"'


def test_decodifica_el_url_encoding_que_aplica_squid_por_palabra():
    mod = _cargar_modulo()
    assert mod.handle("Pol%C3%ADtica de red") == 'OK message="Política de red"'
