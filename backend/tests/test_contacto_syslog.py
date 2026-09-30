"""Facility de syslog validado y escritura del estado de actualizaciones sin permiso de directorio."""
import json

import pytest
from fastapi import HTTPException

from app.routes import syslog as rs
from app.services import update_service as us
from app.services.syslog_service import _FACILITY_CODES


class _Cfg:
    def __init__(self, facility): self.enabled = False; self.host = None; self.port = 514; self.protocol = "udp"; self.rfc_format = "rfc3164"; self.facility = facility; self.log_format = "raw"


def test_facility_desconocido_se_rechaza_en_vez_de_caer_en_silencio_a_local0():
    with pytest.raises(HTTPException) as e:
        rs.update_config(rs.SyslogConfigIn(facility="inventado"), db=None, current_admin=None)
    assert e.value.status_code == 400 and "facility" in e.value.detail


def test_local0_a_local7_y_los_clasicos_son_validos():
    for f in ("local0", "local7", "user", "daemon", "auth", "authpriv"):
        assert f in _FACILITY_CODES


def test_estado_de_actualizaciones_se_escribe_aunque_no_se_pueda_crear_el_temporal(tmp_path, monkeypatch):
    ruta = tmp_path / ".update_state.json"
    ruta.write_text("{}")
    monkeypatch.setattr(us, "ESTADO_PATH", ruta)
    real = us.os.replace

    def sin_permiso(*a, **k):
        raise PermissionError("directorio de solo lectura")

    monkeypatch.setattr(us.os, "replace", sin_permiso)
    us._escribir_estado({"version": "1.2.3"})
    assert json.loads(ruta.read_text())["version"] == "1.2.3"
