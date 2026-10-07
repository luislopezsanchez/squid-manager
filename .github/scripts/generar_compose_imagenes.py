#!/usr/bin/env python3
"""Genera docker-compose.images.yml a partir de docker-compose.yml.

Es el mismo compose, pero cada servicio que se construye (backend, squid, frontend) usa una imagen publicada en
ghcr.io en vez de `build:`. Se genera por texto (no con un parser YAML) para conservar todos los comentarios.

Uso:   python3 .github/scripts/generar_compose_imagenes.py          # escribe docker-compose.images.yml
       python3 .github/scripts/generar_compose_imagenes.py --check  # sale con 1 si el fichero esta desactualizado
"""
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[2]
ORIGEN = RAIZ / "docker-compose.yml"
DESTINO = RAIZ / "docker-compose.images.yml"

CABECERA = """# ============================================================================
# GENERADO de docker-compose.yml con .github/scripts/generar_compose_imagenes.py. NO lo edites a mano.
#
# Igual que docker-compose.yml, pero usa las imagenes ya construidas de ghcr.io/luislopezsanchez
# (squid-manager-backend, -squid y -frontend) en vez de compilarlas en tu servidor.
# Lo instala install-imagenes.sh con el nombre docker-compose.yml. Ver docs/docker-imagenes.md.
# ============================================================================
"""

# Desde el encabezado del servicio hasta justo antes de la seccion de volumenes.
BLOQUE_UPDATER = re.compile(r"  # =+\n  # Updater - .*?(?=# =+\n# Vol)", re.S)

PATRON = re.compile(r"^    build:\n      context: \./(backend|squid|frontend)\n      dockerfile: Dockerfile\n", re.M)


def generar() -> str:
    texto = ORIGEN.read_text(encoding="utf-8")
    sustituidos = []

    def cambiar(m):
        sustituidos.append(m.group(1))
        return ("    image: ${SQUIDMANAGER_REGISTRY:-ghcr.io/luislopezsanchez}/squid-manager-%s:${SQUIDMANAGER_VERSION:-latest}\n"
                % m.group(1))

    resultado = PATRON.sub(cambiar, texto)
    # El servicio `updater` aplica actualizaciones con git sobre la carpeta del proyecto: en esta variante no hay
    # carpeta de proyecto ni .git (se actualiza con `docker compose pull`), asi que no se incluye.
    resultado, quitados = BLOQUE_UPDATER.subn("", resultado)
    if quitados != 1 or "updater:" in re.sub(r"#.*", "", resultado):
        raise SystemExit("No se pudo quitar el servicio updater del compose de imagenes (ver BLOQUE_UPDATER).")
    if sorted(sustituidos) != ["backend", "frontend", "squid"]:
        raise SystemExit(f"No se encontraron los tres bloques build (backend, squid, frontend): {sustituidos}")
    if "build:" in re.sub(r"#.*", "", resultado):
        raise SystemExit("Quedo algun 'build:' sin sustituir en el compose de imagenes.")
    return CABECERA + resultado


if __name__ == "__main__":
    nuevo = generar()
    if "--check" in sys.argv:
        actual = DESTINO.read_text(encoding="utf-8") if DESTINO.exists() else ""
        if actual != nuevo:
            print("docker-compose.images.yml esta desactualizado: ejecuta .github/scripts/generar_compose_imagenes.py")
            sys.exit(1)
        print("docker-compose.images.yml esta al dia")
    else:
        DESTINO.write_text(nuevo, encoding="utf-8")
        print(f"Escrito {DESTINO}")
