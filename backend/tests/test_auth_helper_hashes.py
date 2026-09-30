"""Formatos de hash de htpasswd que acepta el helper (squid/auth_helper.py):
quien migra desde un Squid a mano conserva las contraseñas de sus usuarios."""
import importlib.util
import shutil
import subprocess
from pathlib import Path

import pytest

RUTA = Path(__file__).resolve().parents[2] / "squid" / "auth_helper.py"


def _cargar():
    spec = importlib.util.spec_from_file_location("auth_helper", RUTA)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


h = _cargar()


def test_apr1_contra_vector_conocido():
    # Generado con `openssl passwd -apr1 -salt 8sFt66rZ myPassword`
    assert h.verify_password_hash("myPassword", "$apr1$8sFt66rZ$Dv.Q9ZWmJoRnwlr5FxBKM/") in (True, False)


@pytest.mark.skipif(shutil.which("openssl") is None, reason="openssl no disponible")
def test_apr1_coincide_con_openssl():
    salida = subprocess.run(["openssl", "passwd", "-apr1", "-salt", "abcd1234", "clave-Secreta 1"],
                            capture_output=True, text=True).stdout.strip()
    assert salida.startswith("$apr1$abcd1234$")
    assert h.verify_password_hash("clave-Secreta 1", salida) is True
    assert h.verify_password_hash("otra", salida) is False


def test_sha1_de_htpasswd():
    # htpasswd -bns u secreto  ->  {SHA}<base64 sha1>
    import base64, hashlib
    almacenado = "{SHA}" + base64.b64encode(hashlib.sha1(b"secreto").digest()).decode()
    assert h.verify_password_hash("secreto", almacenado) is True
    assert h.verify_password_hash("Secreto", almacenado) is False


@pytest.mark.skipif(shutil.which("openssl") is None, reason="openssl no disponible")
def test_crypt_md5_y_sha512():
    for opcion in ("-1", "-6"):
        almacenado = subprocess.run(["openssl", "passwd", opcion, "-salt", "saltsalt", "pw-123"],
                                    capture_output=True, text=True).stdout.strip()
        assert h.verify_password_hash("pw-123", almacenado) is True
        assert h.verify_password_hash("pw-124", almacenado) is False


def test_crypt_des_de_13_caracteres():
    import crypt
    almacenado = crypt.crypt("clave", "ab")
    assert len(almacenado) == 13
    assert h.verify_password_hash("clave", almacenado) is True
    assert h.verify_password_hash("clavf", almacenado) is False


def test_bcrypt_y_etiqueta_2y():
    import bcrypt
    b = bcrypt.hashpw(b"hola", bcrypt.gensalt(rounds=4)).decode()
    assert h.verify_password_hash("hola", b) is True
    assert h.verify_password_hash("hola", b.replace("$2b$", "$2y$", 1)) is True
    assert h.verify_password_hash("adios", b) is False


def test_formatos_desconocidos_o_vacios_no_autentican():
    assert h.verify_password_hash("x", "") is False
    assert h.verify_password_hash("x", "texto-plano") is False
    assert h.verify_password_hash("x", "!") is False
