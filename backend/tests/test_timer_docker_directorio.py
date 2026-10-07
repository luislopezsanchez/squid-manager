"""El directorio del temporizador de actualizaciones Docker.

Bug real: /usr/local/lib/squidmanager solo lo creaba install-nativo.sh. En un servidor Docker que nunca tuvo
una instalacion nativa, install.sh moria en el paso del temporizador (`install: cannot create regular file ...
No such file or directory`) y upgrade-docker.sh lo ignoraba en silencio: el temporizador no se instalaba nunca y
"Actualizar ahora" desde el panel no aplicaba nada. Visto instalando en limpio con el instalador oficial.
"""

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
DIR = "/usr/local/lib/squidmanager"


@pytest.mark.parametrize("script", ["install.sh", "upgrade-docker.sh"])
def test_el_directorio_se_crea_antes_de_copiar_los_scripts_del_temporizador(script):
    texto = (RAIZ / script).read_text()
    crear = re.search(r"install -d [^\n]*" + re.escape(DIR), texto)
    primera_copia = re.search(r"install -o root -g root -m 755 [^\n]*docker-autoupdate-check\.sh", texto)
    assert crear, f"{script} no crea {DIR}"
    assert primera_copia and crear.start() < primera_copia.start(), f"{script}: el directorio se crea despues de usarlo"


def test_upgrade_docker_ya_no_oculta_los_errores_de_instalacion_del_temporizador():
    texto = (RAIZ / "upgrade-docker.sh").read_text()
    bloque = texto.split("=== 3. Configurando el temporizador")[1].split("=== 4.")[0]
    codigo = [l for l in bloque.split("cat >")[0].splitlines() if not l.strip().startswith("#")]
    assert "2>/dev/null || true" not in "\n".join(codigo)
