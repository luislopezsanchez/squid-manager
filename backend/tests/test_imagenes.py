"""Imagenes de Docker publicadas: compose generado, instalador rapido y aviso en Actualizaciones."""
import os
import pathlib
import stat
import subprocess
import sys

import pytest

RAIZ = pathlib.Path(__file__).parents[2]


def _leer(rel):
    p = RAIZ / rel
    if not p.exists():
        pytest.skip(f"{rel} no accesible desde aqui")
    return p.read_text(encoding="utf-8")


def test_el_compose_de_imagenes_esta_al_dia():
    script = RAIZ / ".github" / "scripts" / "generar_compose_imagenes.py"
    if not script.exists():
        pytest.skip("script no accesible")
    r = subprocess.run([sys.executable, str(script), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_el_compose_de_imagenes_no_construye_nada():
    t = _leer("docker-compose.images.yml")
    sin_comentarios = "\n".join(linea.split("#")[0] for linea in t.splitlines())
    assert "build:" not in sin_comentarios
    for s in ("backend", "squid", "frontend"):
        assert f"squid-manager-{s}:${{SQUIDMANAGER_VERSION:-latest}}" in t
    # lo demas es identico al compose normal: mismos servicios y misma red
    base = _leer("docker-compose.yml")
    for pista in ("squidmgr-backend", "squidmgr-proxy", "squidmgr-frontend", "proxynet",
                  "DOCKER_HOST: tcp://docker-socket-proxy:2375"):
        assert pista in t and pista in base


def test_el_flujo_de_publicacion_prueba_antes_de_publicar():
    yaml = pytest.importorskip("yaml")
    wf = yaml.safe_load(_leer(".github/workflows/publicar-imagenes.yml"))
    jobs = wf["jobs"]
    assert jobs["probar"]["needs"] == "construir" and jobs["publicar"]["needs"] == "probar"
    assert wf["permissions"]["packages"] == "write"
    assert set(jobs["construir"]["strategy"]["matrix"]["servicio"]) == {"backend", "squid", "frontend"}


@pytest.mark.skipif(not hasattr(os, "geteuid") or os.geteuid() != 0, reason="el instalador exige root")
def test_install_imagenes_crea_env_y_arranca(tmp_path):
    texto = _leer("install-imagenes.sh")
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    llamadas = tmp_path / "docker.log"
    docker = [
        "#!/bin/bash",
        f'echo "$*" >> {llamadas}',
        'if [ "$1 $2" = "compose logs" ]; then',
        "  printf 'Administrador inicial\\n  Usuario: admin\\n  Contraseña: Abc123xyz\\n'",
        "fi",
        "exit 0",
    ]
    (bin_ / "docker").write_text("\n".join(docker) + "\n", encoding="utf-8")
    (bin_ / "curl").write_text("#!/bin/bash\nexit 0\n")
    for f in bin_.iterdir():
        f.chmod(f.stat().st_mode | stat.S_IEXEC)
    fuente = tmp_path / "fuente"
    fuente.mkdir()
    (fuente / "docker-compose.images.yml").write_text(_leer("docker-compose.images.yml"))
    (fuente / ".env.example").write_text(_leer(".env.example"))
    destino = tmp_path / "instalacion"
    script = tmp_path / "install-imagenes.sh"
    script.write_text(texto)
    env = {**os.environ, "PATH": f"{bin_}:{os.environ['PATH']}", "SQUIDMGR_DIR": str(destino),
           "SQUIDMGR_FUENTE": str(fuente), "SQUIDMANAGER_VERSION": "9.9.9", "WEB_PORT": "3999", "PROXY_PORT": "3199"}
    r = subprocess.run(["bash", str(script)], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    envf = (destino / ".env").read_text()
    lineas = dict(linea.split("=", 1) for linea in envf.splitlines() if "=" in linea and not linea.startswith("#"))
    assert len(lineas["SECRET_KEY"]) == 64 and len(lineas["DATA_KEY"]) == 64 and len(lineas["DB_PASS"]) == 32
    assert lineas["PROJECT_DIR"] == str(destino) and lineas["SQUIDMANAGER_VERSION"] == "9.9.9"
    assert lineas["WEB_PORT"] == "3999" and lineas["PROXY_PORT"] == "3199"
    assert (destino / ".env").stat().st_mode & 0o777 == 0o600
    assert (destino / "docker-compose.yml").exists()
    log = llamadas.read_text()
    assert "compose pull" in log and "compose up -d --no-build" in log
    assert "Abc123xyz" in r.stdout and "http://" in r.stdout
    # una segunda ejecucion conserva las claves
    r2 = subprocess.run(["bash", str(script)], capture_output=True, text=True, env=env)
    assert r2.returncode == 0, r2.stdout + r2.stderr
    segunda = dict(linea.split("=", 1) for linea in (destino / ".env").read_text().splitlines() if "=" in linea and not linea.startswith("#"))
    assert segunda["SECRET_KEY"] == lineas["SECRET_KEY"] and segunda["DB_PASS"] == lineas["DB_PASS"]


def test_una_instalacion_con_imagenes_no_ofrece_actualizar_por_git(tmp_path, monkeypatch):
    from app.services import update_service as us
    monkeypatch.setattr(us, "_es_nativo", lambda: False)
    monkeypatch.setattr(us, "_raiz_proyecto", lambda: tmp_path)
    assert us.instalacion_por_imagenes() is True
    (tmp_path / ".git").mkdir()
    assert us.instalacion_por_imagenes() is False
    # nativo: nunca es "por imagenes"
    monkeypatch.setattr(us, "_es_nativo", lambda: True)
    (tmp_path / ".git").rmdir()
    assert us.instalacion_por_imagenes() is False


def test_comprobar_en_instalacion_por_imagenes_explica_como_actualizar(monkeypatch):
    from app.services import update_service as us
    monkeypatch.setattr(us, "instalacion_por_imagenes", lambda: True)
    guardado = {}
    monkeypatch.setattr(us, "_escribir_estado", lambda e: guardado.update(e))
    monkeypatch.setattr(us, "leer_estado", us._estado_por_defecto)
    r = us.comprobar_actualizacion()
    assert r["check"]["update_available"] is False
    assert "docker compose pull" in r["check"]["last_check_error"]
    assert guardado["check"]["last_check_error"] == us.MENSAJE_IMAGENES
