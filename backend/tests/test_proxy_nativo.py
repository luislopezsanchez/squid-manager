"""Instalacion nativa detras de un proxy corporativo (install-tras-proxy.sh --nativo y proxy.env)."""
import pathlib
import subprocess

import pytest

RAIZ = pathlib.Path(__file__).parents[2]


def _leer(rel):
    p = RAIZ / rel
    if not p.exists():
        pytest.skip(f"{rel} no accesible desde aqui")
    return p.read_text(encoding="utf-8")


def test_el_script_de_proxy_tiene_modo_nativo_sin_capas_de_docker():
    t = _leer("install-tras-proxy.sh")
    assert "--nativo)" in t and "NATIVO=1" in t
    # las capas 2 y 3 (demonio y builds de Docker) solo corren fuera del modo nativo
    i = t.index("# 5. Capa 2")
    assert "if [[ $NATIVO -eq 0 ]]; then" in t[i - 200:i]
    assert "exec bash \"$SCRIPT_DIR/install-nativo.sh\"" in t


def test_proxy_env_es_solo_de_root():
    t = _leer("install-tras-proxy.sh")
    assert "/etc/squidmanager/proxy.env" in t
    assert "umask 077" in t and "chmod 600 /etc/squidmanager/proxy.env.tmp" in t


@pytest.mark.parametrize("script", ["install-nativo.sh", "upgrade-nativo.sh", "autoupdate-check.sh"])
def test_los_scripts_de_root_leen_proxy_env_como_datos(script, tmp_path):
    t = _leer(script)
    inicio = t.index("if [ -r /etc/squidmanager/proxy.env ]; then")
    fin = t.index("done < /etc/squidmanager/proxy.env\nfi\n") + len("done < /etc/squidmanager/proxy.env\nfi\n")
    cargador = t[inicio:fin]
    assert "source" not in cargador and "eval" not in cargador
    marca = tmp_path / "PWNED"
    fichero = tmp_path / "proxy.env"
    fichero.write_text(f"https_proxy=http://u:p%40x@h:3128\nno_proxy=localhost\nOTRA=nada\nhttp_proxy=$(touch {marca})\n")
    r = subprocess.run(["bash", "-c", cargador.replace("/etc/squidmanager/proxy.env", str(fichero)) + '\necho "$https_proxy|$no_proxy|${OTRA:-vacia}"'],
                       capture_output=True, text=True)
    assert r.stdout.strip() == "http://u:p%40x@h:3128|localhost|vacia"
    assert not marca.exists()


def test_las_unidades_del_panel_y_de_actualizacion_leen_proxy_env():
    t = _leer("install-nativo.sh")
    assert t.count("EnvironmentFile=-/etc/squidmanager/proxy.env") == 2


def test_install_nativo_guarda_el_proxy_exportado_a_mano():
    t = _leer("install-nativo.sh")
    assert "_PROXY_ENTORNO" in t and "[ ! -f /etc/squidmanager/proxy.env ]" in t


def test_npm_9_con_credenciales_de_proxy_usa_npm_10():
    t = _leer("install-nativo.sh")
    assert "npm-10.9.2.tgz" in t and "NPM_CMD" in t
