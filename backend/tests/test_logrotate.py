"""Que la rotacion diaria no deje al panel sin datos.

Un `logrotate` renombra access.log y, por `nocreate`, no crea uno nuevo: eso le
toca al `postrotate`, que avisa a Squid para que reabra. Cuando ese aviso falla,
Squid sigue escribiendo en el fichero renombrado y access.log deja de existir.

El sintoma es enganoso: la navegacion funciona igual, pero el panel se queda a
cero entero —tarjetas, graficas, registros, top de usuarios y de dominios salen
todos de ese fichero—. Solo sobrevive el trafico en tiempo real, que se lee de
las estadisticas de red de Docker.
"""

from pathlib import Path

import pytest

MARCADOR = Path("squid") / "squid-logrotate"


def _raiz_del_proyecto() -> Path | None:
    """Localiza la raiz del repositorio, se ejecute donde se ejecute.

    Los tests corren dentro del contenedor del backend, donde solo esta copiado
    `backend/`. El compose monta ademas el proyecto entero en la misma ruta que
    tiene en el host, asi que se busca primero hacia arriba y se recurre a ese
    montaje como respaldo.
    """
    for base in Path(__file__).resolve().parents:
        if (base / MARCADOR).is_file():
            return base

    from app.services.squid_service import _project_dir

    base = _project_dir()
    return base if base and (base / MARCADOR).is_file() else None


def _postrotate() -> str:
    raiz = _raiz_del_proyecto()
    if raiz is None:
        pytest.skip("el proyecto no esta accesible desde aqui")
    return (raiz / MARCADOR).read_text(encoding="utf-8")


def test_squid_se_invoca_con_ruta_absoluta():
    """cron usa un PATH minimo que no incluye /usr/sbin, donde esta el binario."""
    contenido = _postrotate()
    assert "/usr/sbin/squid -k rotate" in contenido, (
        "el postrotate debe llamar a Squid por su ruta absoluta: cron ejecuta "
        "logrotate con PATH=/usr/bin:/bin y «squid» a secas da «not found»"
    )


def test_el_fallo_al_reabrir_no_se_silencia():
    """Un `|| true` convirtio esto en un fallo diario que no dejaba rastro."""
    contenido = _postrotate()
    assert "squid -k rotate || true" not in contenido, (
        "sin aviso, el fallo pasa inadvertido: logrotate da la rotacion por "
        "buena y el panel se queda sin datos sin que nada lo registre"
    )
    assert "ERROR" in contenido, "el fallo debe quedar registrado en algun sitio"


def test_solo_rota_logrotate():
    """Con la rotacion interna de Squid activa, los dos renumeran a la vez."""
    from test_config_generator import FakeDB, FakeSetting
    from app.services.config_generator import generate_squid_config

    db = FakeDB(settings=[FakeSetting("http_port", "3128", "network")])
    assert "logfile_rotate 0" in generate_squid_config(db)
