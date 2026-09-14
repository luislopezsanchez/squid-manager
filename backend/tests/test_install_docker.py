"""install.sh: instalador del modo Docker.

Mismo criterio que el resto de tests de scripts de este proyecto: no ejecuta
el script -corre en la máquina de destino, no en la suite-, pero comprueba
las propiedades que no deben perderse.
"""

from pathlib import Path

import pytest

MARCADOR = Path("install.sh")


def _raiz_del_proyecto() -> Path | None:
    for base in Path(__file__).resolve().parents:
        if (base / MARCADOR).is_file():
            return base

    from app.services.squid_service import _project_dir

    base = _project_dir()
    return base if base and (base / MARCADOR).is_file() else None


def _script() -> str:
    raiz = _raiz_del_proyecto()
    if raiz is None:
        pytest.skip("el proyecto no esta accesible desde aqui")
    return (raiz / MARCADOR).read_text(encoding="utf-8")


def test_falla_seguro():
    assert "set -euo pipefail" in _script()


def test_rechaza_una_ruta_que_el_backend_no_puede_alcanzar_antes_de_levantar_nada():
    """El backend corre como uid 999 dentro del contenedor y lee
    docker-compose.yml y .env por el bind-mount. Si el proyecto está bajo un
    directorio sin 'x' para "otros" (clonar en /root, que es 700), ese
    usuario no llega al fichero: el panel arranca pero NO aplica la config a
    Squid y el proxy se queda en el arranque provisional. Confirmado en vivo
    (172.30.36.42, 2026-09-10). La comprobación tiene que estar ANTES del
    `docker compose up`."""
    contenido = _script()
    assert "ruta_accesible_para_otros" in contenido
    pos_check = contenido.index("ruta_accesible_para_otros \"$INSTALL_DIR\"")
    # el comando real está a principio de línea; hay otra mención dentro de un
    # mensaje de aviso ("  3) docker compose up -d") que no cuenta.
    pos_up = contenido.index("\ndocker compose up -d")
    assert pos_check < pos_up
    # el mensaje de error orienta a la solución
    assert "/opt/squid-manager" in contenido
    assert "chmod o+x /root" in contenido


def test_declara_el_directorio_como_safe_para_git():
    """git 2.35.2+ aborta con "detected dubious ownership": el entrypoint del
    backend hace chown del proyecto a uid 999 y el admin corre git como root.
    Se declara safe, idempotente, en la instalación -no solo en el upgrade-."""
    contenido = _script()
    assert "safe.directory" in contenido
    assert "--get-all safe.directory" in contenido


def test_no_canaliza_a_bash_desde_internet():
    """La cabecera insiste en descargar-revisar-ejecutar, no `curl | bash`."""
    contenido = _script()
    assert "less install.sh" in contenido


# Variables de .env.example que compose NO reenvia tal cual al backend, a
# proposito: las de la base las combina en DATABASE_URL, TOKEN_EXPIRE se
# traduce a ACCESS_TOKEN_EXPIRE_MINUTES, WEB_PORT/PROXY_PORT son mapeos de
# puertos del host, y DEPLOY_MODE/NATIVE_SQUID_SERVICE solo tienen sentido
# en la instalacion nativa (en Docker el backend usa su valor por defecto).
_NO_SE_REENVIAN = {
    "DB_NAME", "DB_USER", "DB_PASS", "TOKEN_EXPIRE", "WEB_PORT", "PROXY_PORT",
    "DEPLOY_MODE", "NATIVE_SQUID_SERVICE",
}


def test_compose_pasa_al_backend_toda_variable_del_env_example():
    """Compose solo inyecta en el contenedor lo que lista en `environment`:

    una variable que install.sh escribe en el .env pero no figura ahi llega
    vacia al backend, y este arranca igual con su valor por defecto -sin
    ningun error que lo delate-. Asi DATA_KEY estuvo generandose en cada
    instalacion Docker sin que el cifrado en reposo operara nunca
    (auditoria 2026-09-14, hallazgo 05-005).
    """
    raiz = _raiz_del_proyecto()
    if raiz is None:
        pytest.skip("el proyecto no esta accesible desde aqui")
    env_example = (raiz / ".env.example").read_text(encoding="utf-8")
    compose = (raiz / "docker-compose.yml").read_text(encoding="utf-8")

    # Solo el bloque environment del servicio backend.
    bloque = compose.split("  backend:", 1)[1].split("    volumes:", 1)[0]
    reenviadas = {
        linea.strip().split(":", 1)[0]
        for linea in bloque.splitlines()
        if linea.startswith("      ") and ":" in linea and not linea.strip().startswith("#")
    }

    declaradas = {
        linea.split("=", 1)[0].strip()
        for linea in env_example.splitlines()
        if "=" in linea and not linea.lstrip().startswith("#")
    }
    faltan = sorted(declaradas - _NO_SE_REENVIAN - reenviadas)
    assert not faltan, f"variables del .env.example que el backend nunca recibe en Docker: {faltan}"
