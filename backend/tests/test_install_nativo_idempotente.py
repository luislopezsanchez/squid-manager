"""Volver a correr install-nativo.sh (la forma recomendada de actualizar una
instalación nativa, ver docs/actualizacion.md) no debe pisar la
configuración de una instalación que ya existía.

Bug real encontrado probando el upgrade en vivo: el script reescribía el
.env entero con valores de fábrica en cada corrida -rotaba SECRET_KEY
(cerraba la sesión de todo el mundo sin aviso) y podía perder un
CORS_ORIGINS o un WEB_PORT personalizados-, además de no instalar nunca la
extensión pgvector en una actualización (solo en una instalación nueva).

Mismo criterio que test_consolidate_monthly_logs.py: no ejecuta el script
-corre en la máquina de destino, no en la suite-, pero comprueba las
propiedades que no deben perderse.
"""

from pathlib import Path

import pytest

MARCADOR = Path("install-nativo.sh")


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


def test_preserva_secret_key_de_una_instalacion_previa():
    contenido = _script()
    assert 'for _VAR in SECRET_KEY' in contenido
    assert 'grep -m1 "^${_VAR}=" "$_ENV_PREVIO"' in contenido


def test_no_preserva_lo_que_ya_vino_explicito_del_invocador():
    """BRANCH=pruebas sudo -E ./install-nativo.sh no debe perderse: solo se
    lee del .env previo lo que NO llegó ya seteado desde afuera."""
    contenido = _script()
    assert 'if [ -z "${!_VAR:-}" ]; then' in contenido


def test_extrae_db_pass_de_database_url_no_de_una_linea_propia():
    """DB_PASS no se escribe como línea suelta en el .env -vive embebida en
    DATABASE_URL-; buscarla con el mismo grep genérico que el resto de las
    variables nunca la habría encontrado."""
    contenido = _script()
    assert "DATABASE_URL=" in contenido
    assert "_DB_PASS_PREVIA" in contenido


def test_el_env_escrito_usa_los_valores_preservados_no_literales_fijos():
    """Antes, CORS_ORIGINS/TRUSTED_PROXY_HOSTS/DEBUG/BCRYPT_COST estaban
    escritos a fuego en el heredoc del .env -aunque el valor se hubiera
    preservado más arriba, el archivo final los pisaba igual-."""
    contenido = _script()
    assert "CORS_ORIGINS=${CORS_ORIGINS:-}" in contenido
    assert "TRUSTED_PROXY_HOSTS=${TRUSTED_PROXY_HOSTS}" in contenido
    assert "DEBUG=${DEBUG}" in contenido
    assert "BCRYPT_COST=${BCRYPT_COST}" in contenido


def test_pgvector_se_instala_tambien_en_una_actualizacion():
    """No debe depender de que sea instalación nueva: install-nativo.sh
    corre el mismo bloque de Postgres (rol, base, extensión) siempre, así
    que una actualización que lo vuelva a correr repara el hueco real de
    pgvector encontrado en el hallazgo de la auditoría."""
    contenido = _script()
    assert "postgresql-${PG_MAJOR}-pgvector" in contenido
    assert 'CREATE EXTENSION IF NOT EXISTS vector' in contenido


def test_mensaje_final_distingue_actualizacion_de_instalacion_nueva():
    """Sin esto, actualizar una instalación ya en uso mostraba una 'Clave'
    de admin nueva y aleatoria que no era la contraseña real (el admin ya
    la había cambiado hace tiempo) -confuso para quien lee la salida."""
    contenido = _script()
    assert 'ES_ACTUALIZACION=1' in contenido
    assert 'if [ "${ES_ACTUALIZACION:-0}" = "1" ]; then' in contenido


def test_arranque_final_reinicia_de_verdad_no_solo_enable_now():
    """`systemctl enable --now` no reinicia un servicio que ya estaba
    activo -es un no-op-, así que en una actualización el código quedaba
    escrito en disco pero el proceso viejo seguía corriendo, sirviendo la
    versión y las migraciones de ANTES sin ningún error visible. Bug real,
    confirmado en vivo probando upgrade-nativo.sh en 172.30.36.63
    (2026-09-08): `restart` fuerza el reinicio siempre y también sirve para
    arrancar el servicio la primera vez, así que no hace falta distinguir
    instalación nueva de actualización aquí."""
    contenido = _script()
    assert "systemctl restart squid " in contenido
    assert "systemctl restart squidmanager " in contenido
    # Con el espacio final a propósito: "squidmanager-autoupdate.timer" (otra
    # unidad, sin el problema que esto protege -no es un proceso persistente
    # que pueda quedarse corriendo código viejo, se invoca fresco desde disco
    # en cada tic-) no debe hacer fallar esto por coincidir el prefijo.
    assert "systemctl enable --now squid " not in contenido
    assert "systemctl enable --now squidmanager " not in contenido
