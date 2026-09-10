"""La base de datos en modo Docker se inicializa con locale C.UTF-8.

Motivo: hasta 0.21.0 la imagen era `postgres:16-alpine` (musl), que
inicializaba `en_US.utf8` SIN registrar version de collation. Al pasar a
`pgvector/pgvector:pg16` (glibc), Postgres no emite ningun warning -no hay
version previa que comparar- pero el orden de comparacion de texto cambia:
los indices btree de columnas de texto (entre ellos el UNIQUE de
proxy_users.username) quedan ordenados con el criterio viejo y son
logicamente corruptos. Confirmado con amcheck en vivo (172.30.36.42,
2026-09-10): "item order invariant violated".

`--locale=C.UTF-8` da orden por byte (como `--lc-collate=C` que ya usa
`install-nativo.sh` en modo nativo) con ctype UTF-8, y NO tiene version de
collation: una base creada asi es inmune a cualquier cambio futuro de
imagen o de libc. Para las bases ya existentes, `upgrade-docker.sh` corre
`REINDEX DATABASE` una vez.

No levanta Postgres de verdad: comprueba la propiedad del `docker-compose.yml`
que no debe perderse en un cambio futuro.
"""

from pathlib import Path

import pytest
import yaml


def _raiz() -> Path | None:
    for base in Path(__file__).resolve().parents:
        if (base / "docker-compose.yml").is_file():
            return base
    return None


@pytest.fixture
def compose() -> dict:
    raiz = _raiz()
    if raiz is None:
        pytest.skip("el proyecto no esta accesible desde aqui")
    with open(raiz / "docker-compose.yml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_db_se_inicializa_con_locale_sin_version_de_collation(compose):
    env = compose["services"]["db"]["environment"]
    args = env.get("POSTGRES_INITDB_ARGS", "")
    assert "--locale=C.UTF-8" in args or (
        "--lc-collate=C" in args and "--lc-ctype=C" in args
    ), (
        "La base Docker debe inicializarse con un locale sin version de "
        "collation (C.UTF-8 o C) para no quedar fragil ante un cambio de "
        f"imagen de Postgres. POSTGRES_INITDB_ARGS actual: {args!r}"
    )


def test_la_imagen_de_db_sigue_siendo_pgvector(compose):
    """El asistente de IA necesita la extension; y si alguien vuelve a
    postgres:16-alpine, el locale C.UTF-8 de arriba deja de aplicar igual
    pero el motivo del test de arriba (fragilidad del collation) reaparece."""
    assert compose["services"]["db"]["image"].startswith("pgvector/pgvector:")
