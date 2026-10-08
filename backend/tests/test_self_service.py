"""Portal de autoservicio: un usuario local del proxy entra con su cuenta y cambia su contraseña.

Lo que importa de verdad es la frontera entre los dos tipos de sesión: el token de
un usuario del proxy NO puede abrir la API de administración (ni siquiera si su
nombre coincide con el de un admin), y el de un admin NO abre el portal.
"""

from datetime import timedelta
from types import SimpleNamespace

import pytest
from fastapi import BackgroundTasks
from fastapi import HTTPException

from app.services import auth_service as a
from app.services.auth_service import (
    create_access_token, create_proxy_user_token, get_current_admin,
    get_current_proxy_user, get_password_hash,
)
from app.utils import utcnow


def _usuario(nombre="ana", password="Clave-Segura-1", enabled=True, expires_at=None):
    return SimpleNamespace(
        username=nombre, password_hash=get_password_hash(password),
        enabled=enabled, expires_at=expires_at,
    )


class _Query:
    def __init__(self, fila):
        self.fila = fila

    def filter(self, *_a, **_k):
        return self

    def first(self):
        return self.fila


class _DB:
    def __init__(self, fila):
        self.fila = fila

    def query(self, _modelo):
        return _Query(self.fila)


def _peticion(path="/api/admins/"):
    return SimpleNamespace(url=SimpleNamespace(path=path))


def test_autentica_usuario_activo_y_rechaza_clave_mala():
    u = _usuario()
    assert a.authenticate_proxy_user(_DB(u), "ana", "Clave-Segura-1") is u
    assert a.authenticate_proxy_user(_DB(u), "ana", "otra") is None


def test_no_entra_si_esta_deshabilitado_o_caducado():
    assert a.authenticate_proxy_user(_DB(_usuario(enabled=False)), "ana", "Clave-Segura-1") is None
    ayer = utcnow() - timedelta(days=1)
    assert a.authenticate_proxy_user(_DB(_usuario(expires_at=ayer)), "ana", "Clave-Segura-1") is None
    assert a.authenticate_proxy_user(_DB(None), "nadie", "x") is None


def test_token_de_usuario_abre_el_portal():
    u = _usuario()
    token = create_proxy_user_token(u)
    assert get_current_proxy_user(token=token, db=_DB(u)) is u


def test_token_de_usuario_no_abre_la_api_de_admin_aunque_se_llame_igual():
    # Hay un admin "admin" y un usuario del proxy "admin": el token del segundo no vale como el primero.
    u = _usuario(nombre="admin")
    token = create_proxy_user_token(u)
    admin_falso = SimpleNamespace(
        username="admin", is_active=True, password_changed_at=None, must_change_password=False, role="superadmin",
    )
    with pytest.raises(HTTPException) as e:
        get_current_admin(request=_peticion(), token=token, db=_DB(admin_falso))
    assert e.value.status_code == 401


def test_token_de_admin_no_abre_el_portal():
    u = _usuario(nombre="admin")
    token = create_access_token({"sub": "admin"})
    with pytest.raises(HTTPException) as e:
        get_current_proxy_user(token=token, db=_DB(u))
    assert e.value.status_code == 401


def test_cambiar_la_contrasena_cierra_las_sesiones_abiertas():
    u = _usuario()
    token = create_proxy_user_token(u)
    u.password_hash = get_password_hash("Clave-Nueva-22")
    with pytest.raises(HTTPException) as e:
        get_current_proxy_user(token=token, db=_DB(u))
    assert e.value.status_code == 401


def test_usuario_deshabilitado_despues_de_entrar_pierde_la_sesion():
    u = _usuario()
    token = create_proxy_user_token(u)
    u.enabled = False
    with pytest.raises(HTTPException):
        get_current_proxy_user(token=token, db=_DB(u))


# --- Homónimos entre administradores y usuarios del proxy ---

from app.routes import admins as admins_routes, proxy_users as pu_routes
from app.routes.admins import AdminCreate
from app.schemas.proxy_user import ProxyUserCreate


class _DBPorModelo:
    """query(Modelo) devuelve la fila configurada para ese modelo (o None)."""

    def __init__(self, filas):
        self.filas = filas

    def query(self, modelo):
        return _Query(self.filas.get(modelo))


def test_no_se_crea_usuario_del_proxy_con_nombre_de_un_admin():
    db = _DBPorModelo({pu_routes.ProxyUser: None, pu_routes.Admin: SimpleNamespace(username="L.Lopez")})
    datos = ProxyUserCreate(username="l.lopez", password="ClaveInicial01")
    with pytest.raises(HTTPException) as e:
        pu_routes.create_proxy_user(datos, db=db, current_admin=SimpleNamespace(id=1, username="root"))
    assert e.value.status_code == 400
    assert "administrador" in e.value.detail


def test_no_se_crea_admin_con_nombre_de_un_usuario_del_proxy():
    db = _DBPorModelo({admins_routes.Admin: None, admins_routes.ProxyUser: SimpleNamespace(username="L.Lopez")})
    datos = AdminCreate(username="l.lopez", password="ClaveInicial01", role="admin")
    with pytest.raises(HTTPException) as e:
        admins_routes.create_admin(datos, db=db, current=SimpleNamespace(id=1, username="root"))
    assert e.value.status_code == 400
    assert "usuario del proxy" in e.value.detail


# --- Dashboard del usuario ---

from app.services import rollup_service as ru


def test_actividad_usuario_filtra_por_su_nombre_y_suma_por_dia(monkeypatch):
    consultas = []
    ahora = int(__import__("time").time())
    h = ru._hora(ahora)

    def falso_q(sql, params):
        consultas.append(params)
        return [(h, 1000, 10, 2), (h - 3600, 500, 5, 0)] if "ru_user" in sql else []

    monkeypatch.setattr(ru, "_q", falso_q)
    r = ru.actividad_usuario("ana", 7)
    assert consultas and all(c["u"] == "ana" for c in consultas)
    assert r["granularidad"] == "dia"
    assert r["totales"]["bytes"] == 1500
    assert r["totales"]["requests"] == 15
    assert r["totales"]["bloqueadas"] == 2
    assert r["totales"]["dias_activos"] >= 1
    assert len(r["puntos"]) == 7


def test_actividad_usuario_sin_datos_devuelve_la_rejilla_vacia(monkeypatch):
    monkeypatch.setattr(ru, "_q", lambda sql, params: [])
    r = ru.actividad_usuario("nadie", 7)
    assert r["totales"] == {"bytes": 0, "requests": 0, "bloqueadas": 0, "dias_activos": 0}
    assert len(r["puntos"]) == 7


def test_el_dashboard_usa_el_usuario_del_token(monkeypatch):
    from app.routes import self_service as ss

    pedidos = []
    monkeypatch.setattr(ss.rollup_service, "actividad_usuario",
                        lambda u, d: pedidos.append((u, d)) or {"granularidad": "dia", "puntos": [], "totales": {}})

    class _DBVacia:
        def query(self, *_a, **_k):
            return self

        def join(self, *_a, **_k):
            return self

        def filter(self, *_a, **_k):
            return self

        def order_by(self, *_a, **_k):
            return self

        def first(self):
            return None

        def all(self):
            return []

    r = ss.dashboard(ventana="30d", db=_DBVacia(), user=_usuario("ana"))
    assert pedidos == [("ana", 30)]
    assert r["cuota"] is None and r["grupos"] == []


# --- Módulo «autoservicio»: apagado por defecto ---

from app.services import modules_service


def test_el_modulo_autoservicio_viene_apagado():
    assert modules_service.MODULOS["autoservicio"][0] is False


def test_con_el_modulo_apagado_el_login_no_prueba_usuarios_del_proxy(monkeypatch):
    from app.routes import auth as auth_routes

    monkeypatch.setattr(auth_routes, "authenticate_admin", lambda *_a, **_k: None)
    monkeypatch.setattr(auth_routes.modules_service, "is_enabled", lambda *_a, **_k: False)
    llamadas = []
    monkeypatch.setattr(auth_routes, "authenticate_proxy_user", lambda *a, **k: llamadas.append(a))
    monkeypatch.setattr(auth_routes.time, "sleep", lambda _s: None)
    monkeypatch.setattr(auth_routes, "queue_notification", lambda *a, **k: None)

    class _DB:
        def add(self, _o): pass
        def commit(self): pass

    with pytest.raises(HTTPException) as e:
        auth_routes.login(request=SimpleNamespace(client=SimpleNamespace(host="198.51.100.1"), headers={}),
                          background_tasks=BackgroundTasks(),
                          form_data=SimpleNamespace(username="ana", password="x"), db=_DB())
    assert e.value.status_code == 401
    assert llamadas == []


def test_con_el_modulo_apagado_las_rutas_self_responden_401(monkeypatch):
    from app.routes import self_service as ss

    monkeypatch.setattr(ss.modules_service, "is_enabled", lambda *_a, **_k: False)
    with pytest.raises(HTTPException) as e:
        ss._portal_habilitado(db=None)
    assert e.value.status_code == 401

    monkeypatch.setattr(ss.modules_service, "is_enabled", lambda *_a, **_k: True)
    assert ss._portal_habilitado(db=None) is None
