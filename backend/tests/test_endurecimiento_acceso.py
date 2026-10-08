"""Contraseñas largas, retraso creciente y aviso ante intentos fallidos de inicio de sesión (auditoría 05-008 / 05-009)."""

import time
from types import SimpleNamespace as N

import pytest
from fastapi import BackgroundTasks, HTTPException
from pydantic import ValidationError

from app.middleware import _requests, failed_login_count, login_failure_delay, record_failed_login, LOGIN_MAX_PER_USER
from app.routes import auth as rutas_auth
from app.schemas.proxy_user import ProxyUserCreate, ProxyUserUpdate
from app.services import user_import_service as imp
from app.services.auth_service import validar_largo_bcrypt


@pytest.fixture(autouse=True)
def _limpiar():
    _requests.clear()
    yield
    _requests.clear()


# ---- 05-009: bcrypt trunca en 72 bytes ----------------------------------------------------------------------
def test_72_bytes_pasan_y_73_no():
    assert validar_largo_bcrypt("a" * 72) == "a" * 72
    with pytest.raises(ValueError):
        validar_largo_bcrypt("a" * 73)


def test_los_acentos_cuentan_por_bytes():
    assert validar_largo_bcrypt("ñ" * 36)  # 72 bytes
    with pytest.raises(ValueError):
        validar_largo_bcrypt("ñ" * 37)     # 74 bytes, aunque sean 37 caracteres


def test_los_esquemas_de_usuario_rechazan_lo_que_bcrypt_truncaria():
    with pytest.raises(ValidationError):
        ProxyUserCreate(username="ana", password="ñ" * 40)
    with pytest.raises(ValidationError):
        ProxyUserUpdate(password="x" * 90)
    assert ProxyUserCreate(username="ana", password="x" * 72).password == "x" * 72
    assert ProxyUserUpdate().password is None


def test_la_importacion_rechaza_la_fila_con_clave_demasiado_larga():
    csv = ("usuario,contraseña\nana," + "x" * 80 + "\nluis,ClaveCorrecta1\n").encode()
    filas, errores = imp.parse_archivo("u.csv", csv)
    assert [f["username"] for f in filas] == ["luis"]
    assert errores and "72 bytes" in errores[0]["motivo"]


def test_el_tope_de_filas_explica_como_seguir():
    cuerpo = "usuario\n" + "\n".join(f"u{i}" for i in range(imp.MAX_FILAS + 1))
    with pytest.raises(ValueError) as e:
        imp.parse_archivo("u.csv", cuerpo.encode())
    assert str(imp.MAX_FILAS) in str(e.value) and "Divide el archivo" in str(e.value)


# ---- 05-008: retraso creciente y aviso -----------------------------------------------------------------------
def test_retraso_creciente_con_tope():
    assert [login_failure_delay(n) for n in (0, 1, 2, 3, 4, 5, 6, 20)] == [0, 0, 0, 1, 2, 4, 8, 8]


def test_contador_de_fallos_no_registra_nada_por_leerlo():
    assert failed_login_count("ana") == 0
    record_failed_login("ana")
    record_failed_login("ana")
    assert failed_login_count("ana") == 2 == failed_login_count("ana")


class _DBFalsa:
    def add(self, _): pass
    def commit(self): pass


def _fallar(monkeypatch, usuario="admin"):
    esperas, avisos = [], []
    monkeypatch.setattr(rutas_auth, "authenticate_admin", lambda *a: None)
    monkeypatch.setattr(rutas_auth.modules_service, "is_enabled", lambda *a, **k: False)
    monkeypatch.setattr(rutas_auth.time, "sleep", esperas.append)
    monkeypatch.setattr(rutas_auth, "queue_notification", lambda bt, db, ev, asunto, msg: avisos.append((ev, asunto, msg)))
    peticion = N(client=N(host="203.0.113.9"), headers={})
    form = N(username=usuario, password="mala")
    with pytest.raises(HTTPException) as exc:
        rutas_auth.login(request=peticion, background_tasks=BackgroundTasks(), form_data=form, db=_DBFalsa())
    return exc.value.status_code, esperas, avisos


def test_el_quinto_fallo_avisa_una_sola_vez_y_los_primeros_no_esperan(monkeypatch):
    todas_las_esperas, todos_los_avisos = [], []
    for n in range(1, LOGIN_MAX_PER_USER + 3):
        codigo, esperas, avisos = _fallar(monkeypatch)
        todas_las_esperas += esperas
        todos_los_avisos += avisos
    # 7 fallos: del 3.º al 7.º hay espera (1, 2, 4, 8, 8 s); los dos primeros contestan al instante.
    assert todas_las_esperas == [1, 2, 4, 8, 8]
    assert len(todos_los_avisos) == 1
    ev, asunto, msg = todos_los_avisos[0]
    assert ev == "security_alert" and "admin" in msg and "203.0.113.9" in msg


def test_el_nombre_de_cuenta_del_aviso_se_sanea(monkeypatch):
    for _ in range(LOGIN_MAX_PER_USER - 1):
        record_failed_login("x" * 200)
    _, _, avisos = _fallar(monkeypatch, usuario="x" * 200)
    assert avisos and "x" * 65 not in avisos[0][2]


def test_una_contrasena_correcta_sigue_sin_esperar(monkeypatch):
    for _ in range(10):
        record_failed_login("admin")
    admin = N(id=1, username="admin", role="superadmin", must_change_password=False, last_login=None)
    esperas = []
    monkeypatch.setattr(rutas_auth, "authenticate_admin", lambda *a: admin)
    monkeypatch.setattr(rutas_auth.time, "sleep", esperas.append)
    out = rutas_auth.login(request=N(client=N(host="1.1.1.1"), headers={}), background_tasks=BackgroundTasks(),
                           form_data=N(username="admin", password="ok"), db=_DBFalsa())
    assert "access_token" in out and esperas == []
