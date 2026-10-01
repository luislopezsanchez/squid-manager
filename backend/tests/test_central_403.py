"""Panel central: una cuenta de nodo con la contraseña pendiente de cambiar no debe verse como un fallo misterioso."""
import pytest


class Resp:
    def __init__(self, status, cuerpo=None):
        self.status_code = status
        self._cuerpo = cuerpo

    def json(self):
        if self._cuerpo is None:
            raise ValueError("sin json")
        return self._cuerpo


class Nodo:
    username = "squid"
    name = "Sucursal"


def test_403_por_contrasena_pendiente_explica_que_hacer():
    from app.services.central_monitor_service import _respuesta_no_ok
    msg = _respuesta_no_ok(Nodo(), Resp(403, {"detail": "Debes cambiar tu contraseña antes de continuar."}), "al pedir el dashboard")
    assert "«squid»" in msg and "pendiente de cambiar" in msg and "Pedir que cambie la contraseña" in msg
    assert "respondió 403" not in msg


@pytest.mark.parametrize("resp", [Resp(403, {"detail": "Se requieren permisos de escritura"}), Resp(403), Resp(500, {"detail": "x"})])
def test_otras_respuestas_conservan_el_mensaje_generico(resp):
    from app.services.central_monitor_service import _respuesta_no_ok
    assert _respuesta_no_ok(Nodo(), resp, "al pedir el dashboard") == f"El nodo respondió {resp.status_code} al pedir el dashboard"


def test_crear_admin_permite_no_exigir_el_cambio_de_contrasena():
    from app.routes.admins import AdminCreate
    assert AdminCreate(username="a", password="x" * 12).require_password_change is True
    assert AdminCreate(username="a", password="x" * 12, require_password_change=False).require_password_change is False
    import inspect
    from app.routes import admins
    assert "must_change_password=data.require_password_change" in inspect.getsource(admins.create_admin)
