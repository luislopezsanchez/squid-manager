"""Tests de EncryptedString/EncryptedBinary (crypto_service.py).

Cubren los tres comportamientos que importan: sin DATA_KEY configurada
todo funciona igual que antes (texto plano, ningún crash); con DATA_KEY
configurada, cifra al guardar y descifra al leer; y un valor preexistente
sin cifrar (de antes de configurar DATA_KEY) se sigue leyendo como texto
plano en vez de fallar -la migración de doble lectura que evita romper
instalaciones existentes (auditoría 2026-09-09, hallazgo 05-003).
"""

import pytest

from app.config import settings
from app.crypto_service import EncryptedBinary, EncryptedString


@pytest.fixture
def con_data_key(monkeypatch):
    monkeypatch.setattr(settings, "DATA_KEY", "clave-de-prueba-" + "a" * 40)
    yield


@pytest.fixture
def sin_data_key(monkeypatch):
    monkeypatch.setattr(settings, "DATA_KEY", "")
    yield


def test_sin_data_key_pasa_tal_cual(sin_data_key):
    tipo = EncryptedString()
    valor = "clave-secreta-de-ldap"
    cifrado = tipo.process_bind_param(valor, None)
    assert cifrado == valor  # nada se cifra sin DATA_KEY
    assert tipo.process_result_value(cifrado, None) == valor


def test_con_data_key_cifra_y_descifra(con_data_key):
    tipo = EncryptedString()
    valor = "clave-secreta-de-ldap"
    cifrado = tipo.process_bind_param(valor, None)
    assert cifrado != valor  # de verdad se cifro
    assert cifrado is not None and len(cifrado) > len(valor)  # overhead de Fernet
    assert tipo.process_result_value(cifrado, None) == valor


def test_valor_preexistente_sin_cifrar_se_lee_como_texto_plano(con_data_key):
    """Migracion de doble lectura: un valor que quedo en texto plano de

    antes de configurar DATA_KEY no debe romper la lectura -se trata como
    texto plano hasta que se vuelva a guardar."""
    tipo = EncryptedString()
    valor_viejo_sin_cifrar = "clave-secreta-de-antes-de-DATA_KEY"
    assert tipo.process_result_value(valor_viejo_sin_cifrar, None) == valor_viejo_sin_cifrar


def test_none_y_vacio_no_se_tocan(con_data_key):
    tipo = EncryptedString()
    assert tipo.process_bind_param(None, None) is None
    assert tipo.process_bind_param("", None) == ""
    assert tipo.process_result_value(None, None) is None
    assert tipo.process_result_value("", None) == ""


def test_encrypted_binary_cifra_y_descifra(con_data_key):
    tipo = EncryptedBinary()
    valor = b"\x00\x01contenido-binario-del-keytab\xff"
    cifrado = tipo.process_bind_param(valor, None)
    assert cifrado != valor
    assert tipo.process_result_value(cifrado, None) == valor


def test_encrypted_binary_sin_data_key_pasa_tal_cual(sin_data_key):
    tipo = EncryptedBinary()
    valor = b"contenido-del-keytab"
    assert tipo.process_bind_param(valor, None) == valor
    assert tipo.process_result_value(valor, None) == valor


def test_claves_distintas_no_descifran_entre_si(monkeypatch):
    """DATA_KEY es DELIBERADAMENTE independiente de SECRET_KEY: cifrar con

    una clave y tratar de leer con otra debe caer al camino de "texto
    plano", no reventar -es exactamente lo que pasa si alguien rota
    DATA_KEY sin re-cifrar los datos existentes primero."""
    tipo = EncryptedString()
    monkeypatch.setattr(settings, "DATA_KEY", "clave-uno-" + "a" * 40)
    cifrado_con_clave_uno = tipo.process_bind_param("secreto", None)

    monkeypatch.setattr(settings, "DATA_KEY", "clave-dos-" + "b" * 40)
    # No decodifica con la clave nueva: se devuelve el valor cifrado tal
    # cual (no es un dato legible, pero tampoco un crash).
    assert tipo.process_result_value(cifrado_con_clave_uno, None) == cifrado_con_clave_uno
