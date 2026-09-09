"""Límite de intentos de login por cuenta: no debe poder usarse para negar
el acceso al admin real.

Bug real: la versión anterior comprobaba el límite por cuenta ANTES de
validar la contraseña. Cualquiera, sin acertar nunca ni moverse de IP, podía
mandar unas pocas contraseñas mal escritas contra 'admin' y dejar al admin
real recibiendo 429 en vez de poder entrar con su contraseña correcta -una
denegación de servicio dirigida y gratis contra una cuenta puntual. El
límite ahora solo se aplica DESPUÉS de comprobar la contraseña, y solo a los
intentos que ya son incorrectos: uno correcto siempre pasa.
"""

import asyncio

import pytest
from fastapi import HTTPException

from app.middleware import (
    _requests,
    login_attempts_exceeded,
    record_failed_login,
    LOGIN_MAX_PER_USER,
)
from app.routes.auth import login as login_route


@pytest.fixture(autouse=True)
def _limpiar_contadores():
    """Cada prueba parte de cero: el límite vive en un dict de proceso."""
    _requests.clear()
    yield
    _requests.clear()


class _FormDataFalso:
    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password


class _DBFalsa:
    """No hace falta una base real: login() solo llama add()/commit()."""

    def add(self, _obj):
        pass

    def commit(self):
        pass


def _ejecutar_login(username: str, password: str, admin_service, monkeypatch):
    monkeypatch.setattr("app.routes.auth.authenticate_admin", admin_service)
    form = _FormDataFalso(username, password)
    return asyncio.run(login_route(form_data=form, db=_DBFalsa()))


# --- El núcleo del bug: contraseña correcta nunca debe bloquearse ----------

class _AdminFalso:
    id = 1
    username = "admin"
    role = "superadmin"
    must_change_password = False
    last_login = None


def test_password_correcta_pasa_aunque_la_cuenta_este_al_limite(monkeypatch):
    admin_falso = _AdminFalso()

    # Agotar el límite con intentos FALLIDOS contra la misma cuenta.
    for _ in range(LOGIN_MAX_PER_USER):
        record_failed_login("admin")
    assert login_attempts_exceeded("admin")

    # La próxima petición trae la contraseña CORRECTA: tiene que pasar, no
    # recibir 429 solo por la mala suerte de compartir cuenta con un
    # atacante que venía fallando antes.
    resultado = _ejecutar_login(
        "admin", "la-correcta", lambda db, u, p: admin_falso, monkeypatch,
    )
    assert "access_token" in resultado


def test_password_incorrecta_da_401_normal_por_debajo_del_limite(monkeypatch):
    with pytest.raises(HTTPException) as exc:
        _ejecutar_login("admin", "mal", lambda db, u, p: None, monkeypatch)
    assert exc.value.status_code == 401


def test_password_incorrecta_da_429_una_vez_superado_el_limite(monkeypatch):
    for _ in range(LOGIN_MAX_PER_USER):
        with pytest.raises(HTTPException) as exc:
            _ejecutar_login("admin", "mal", lambda db, u, p: None, monkeypatch)
        assert exc.value.status_code == 401

    # El intento número LOGIN_MAX_PER_USER + 1, todavía incorrecto, ya debe
    # frenarse con 429 en vez de seguir dejando adivinar.
    with pytest.raises(HTTPException) as exc:
        _ejecutar_login("admin", "mal", lambda db, u, p: None, monkeypatch)
    assert exc.value.status_code == 429


def test_cuentas_distintas_no_se_afectan_entre_si(monkeypatch):
    for _ in range(LOGIN_MAX_PER_USER + 1):
        record_failed_login("admin")
    assert login_attempts_exceeded("admin")
    assert not login_attempts_exceeded("otro_admin")


# --- Las funciones del middleware, sueltas ---------------------------------

def test_login_attempts_exceeded_no_registra_nada_por_si_sola():
    """Consultar el límite no debe contar como un intento nuevo."""
    for _ in range(10):
        login_attempts_exceeded("admin")
    assert not login_attempts_exceeded("admin")


def test_case_insensitive_y_espacios():
    for _ in range(LOGIN_MAX_PER_USER):
        record_failed_login("  Admin  ")
    assert login_attempts_exceeded("admin")
    assert login_attempts_exceeded("ADMIN")
