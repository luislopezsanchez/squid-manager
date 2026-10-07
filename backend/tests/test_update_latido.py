"""Latido del temporizador de actualizaciones.

Caso real (VPS con Docker desplegado a mano, sin install.sh): el panel dejaba aprobada la orden de
«Actualizar ahora», nadie la recogía porque el temporizador del host nunca se instaló, y el panel solo
lo notaba a los 3 minutos, mandando a revisar una unidad que ni existía. Ahora el temporizador anota la
hora en CADA tic y el panel lo lee para avisar de inmediato.
"""

import os
import subprocess
import time
from pathlib import Path

import pytest

from app.services import update_service as us

RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _estado_en_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(us, "ESTADO_PATH", tmp_path / ".update_state.json")
    monkeypatch.setattr(us.settings, "DEPLOY_MODE", "native")  # con .git propio: no es una instalación por imágenes


def _latido(tmp_path, hace_segundos):
    (tmp_path / ".update_heartbeat").write_text(f"{int(time.time()) - hace_segundos}\n")


def test_sin_archivo_de_latido_no_se_detecta_el_temporizador():
    assert us.estado_temporizador() == {"estado": "no_detectado", "ultimo_latido": None}


def test_latido_reciente_es_activo(tmp_path):
    _latido(tmp_path, 30)
    t = us.estado_temporizador()
    assert t["estado"] == "activo" and t["ultimo_latido"].endswith("Z")


def test_latido_viejo_es_detenido(tmp_path):
    _latido(tmp_path, 10 * 60)
    assert us.estado_temporizador()["estado"] == "detenido"


def test_latido_con_basura_cuenta_como_no_detectado(tmp_path):
    (tmp_path / ".update_heartbeat").write_text("no es un numero")
    assert us.estado_temporizador()["estado"] == "no_detectado"


def test_instalacion_por_imagenes_no_aplica(monkeypatch):
    monkeypatch.setattr(us, "instalacion_por_imagenes", lambda: True)
    assert us.estado_temporizador()["estado"] == "no_aplica"


def test_el_estado_del_panel_incluye_temporizador_y_directorio(tmp_path):
    e = us.estado_actual()
    assert e["temporizador"]["estado"] == "no_detectado"
    assert e["proyecto_dir"]


def _ejecutar(script, entorno_extra):
    entorno = {**os.environ, **entorno_extra}
    return subprocess.run(["bash", str(RAIZ / script)], env=entorno, capture_output=True, text=True, timeout=30)


@pytest.mark.parametrize("script,variable,latido", [
    ("docker-autoupdate-check.sh", "PROJECT_DIR", ".update_heartbeat"),
    ("autoupdate-check.sh", "INSTALL_DIR", "backend/.update_heartbeat"),
])
def test_los_scripts_del_host_escriben_el_latido_aunque_no_haya_nada_que_hacer(tmp_path, script, variable, latido):
    # Sin archivo de estado el script sale enseguida: el latido tiene que escribirse ANTES de esa salida.
    (tmp_path / "backend").mkdir()
    r = _ejecutar(script, {variable: str(tmp_path)})
    assert r.returncode == 0, r.stderr
    f = tmp_path / latido
    assert f.exists()
    assert abs(int(f.read_text().strip()) - time.time()) < 30
    assert oct(f.stat().st_mode)[-3:] == "644"


@pytest.mark.parametrize("script,variable", [
    ("docker-autoupdate-check.sh", "PROJECT_DIR"),
    ("autoupdate-check.sh", "INSTALL_DIR"),
])
def test_un_fallo_al_escribir_el_latido_no_rompe_el_script(tmp_path, script, variable):
    # Directorio inexistente: no se puede escribir el latido y el script debe terminar sin error igualmente.
    r = _ejecutar(script, {variable: str(tmp_path / "no-existe")})
    assert r.returncode == 0, r.stderr
