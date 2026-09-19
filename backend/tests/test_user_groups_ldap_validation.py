"""Validación de grupos de LDAP/Active Directory —
ver app/routes/user_groups.py:_validar_origen_ldap."""

import pytest
from fastapi import HTTPException

from app.routes.user_groups import _validar_origen_ldap


class FakeLdapConfig:
    def __init__(self, enabled=True):
        self.enabled = enabled


class FakeQuery:
    def __init__(self, item):
        self._item = item

    def first(self):
        return self._item


class FakeDB:
    def __init__(self, ldap_config=None):
        self._ldap_config = ldap_config

    def query(self, model):
        return FakeQuery(self._ldap_config)


def test_origen_local_no_exige_nada():
    _validar_origen_ldap(FakeDB(), "local", None)  # no debe lanzar


def test_origen_invalido_rechazado():
    with pytest.raises(HTTPException) as exc:
        _validar_origen_ldap(FakeDB(), "windows_ad", None)
    assert exc.value.status_code == 400


def test_ldap_sin_nombre_de_grupo_rechazado():
    with pytest.raises(HTTPException) as exc:
        _validar_origen_ldap(FakeDB(ldap_config=FakeLdapConfig(enabled=True)), "ldap", "")
    assert "nombre del grupo" in exc.value.detail.lower()


def test_ldap_sin_configuracion_ldap_rechazado():
    with pytest.raises(HTTPException) as exc:
        _validar_origen_ldap(FakeDB(ldap_config=None), "ldap", "Ventas")
    assert "ldap no está activado" in exc.value.detail.lower()


def test_ldap_con_config_deshabilitada_rechazado():
    with pytest.raises(HTTPException) as exc:
        _validar_origen_ldap(FakeDB(ldap_config=FakeLdapConfig(enabled=False)), "ldap", "Ventas")
    assert exc.value.status_code == 400


def test_ldap_valido_no_lanza():
    _validar_origen_ldap(FakeDB(ldap_config=FakeLdapConfig(enabled=True)), "ldap", "Ventas")
