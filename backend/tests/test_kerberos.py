"""Pruebas de la autenticación Negotiate (Kerberos/SPNEGO) contra AD."""

import struct

from app.services import kerberos_service
from app.services.kerberos_service import (
    _krb5_conf,
    escribir_krb5_conf,
    quitar_entradas_des,
    validar_keytab,
)


# --- Validación del archivo subido ------------------------------------------

def test_rechaza_archivo_vacio():
    ok, mensaje = validar_keytab(b"")
    assert not ok
    assert "vacío" in mensaje


def test_rechaza_archivo_sin_cabecera_de_keytab():
    ok, mensaje = validar_keytab(b"esto no es un keytab, es texto plano")
    assert not ok
    assert "keytab" in mensaje.lower()


def test_acepta_cabecera_de_keytab_valida():
    # Cabecera real de un keytab v5: 0x05 0x02 + resto de entradas.
    ok, _ = validar_keytab(b"\x05\x02" + b"\x00" * 20)
    assert ok


# --- Filtrado de entradas DES del keytab -------------------------------------
# MIT Kerberos >= 1.18 (Ubuntu 24.04 trae 1.20) eliminó el soporte de DES del
# todo. Confirmado en vivo contra un AD real: un keytab generado con
# `ktpass -crypto All` (que sigue incluyendo des-cbc-crc/des-cbc-md5) rompía
# gss_accept_sec_context() con "Bad encryption type" hasta quitarle esas dos
# entradas -las de AES/RC4 ya estaban bien, el problema eran justo esas dos-.

def _entrada_keytab(enctype: int, principal: str = "svc", realm: str = "X") -> bytes:
    """Construye una entrada de keytab v5.2 mínima pero válida, con el
    enctype indicado. Suficiente para que quitar_entradas_des la parsee: no
    hace falta que la clave sea real, solo que el formato binario sea correcto.
    """
    cuerpo = struct.pack(">H", 1)  # 1 componente en el principal
    cuerpo += struct.pack(">H", len(realm)) + realm.encode()
    cuerpo += struct.pack(">H", len(principal)) + principal.encode()
    cuerpo += struct.pack(">I", 1)  # name_type
    cuerpo += struct.pack(">I", 0)  # timestamp
    cuerpo += bytes([1])  # vno de 8 bits
    cuerpo += struct.pack(">H", enctype)
    clave = b"\x00" * 8
    cuerpo += struct.pack(">H", len(clave)) + clave
    return cuerpo


def _keytab(entradas: list[bytes]) -> bytes:
    salida = bytearray(b"\x05\x02")
    for entrada in entradas:
        salida += struct.pack(">i", len(entrada))
        salida += entrada
    return bytes(salida)


def test_quita_entradas_des_y_conserva_el_resto():
    des_crc = _entrada_keytab(1)
    des_md5 = _entrada_keytab(3)
    aes256 = _entrada_keytab(18)
    aes128 = _entrada_keytab(17)
    original = _keytab([des_crc, des_md5, aes256, aes128])

    filtrado = quitar_entradas_des(original)

    assert des_crc not in filtrado
    assert des_md5 not in filtrado
    assert aes256 in filtrado
    assert aes128 in filtrado
    assert filtrado[:2] == b"\x05\x02"


def test_sin_entradas_des_devuelve_el_mismo_contenido():
    aes256 = _entrada_keytab(18)
    original = _keytab([aes256])
    assert quitar_entradas_des(original) == original


def test_hueco_de_entrada_borrada_se_salta_sin_romper_el_parseo():
    # Una longitud negativa marca un hueco (entrada borrada con ktutil, por
    # ejemplo): hay que saltarlo sin intentar interpretarlo como entrada.
    aes256 = _entrada_keytab(18)
    hueco = struct.pack(">i", -10) + b"\x00" * 10
    original = b"\x05\x02" + hueco + struct.pack(">i", len(aes256)) + aes256

    filtrado = quitar_entradas_des(original)

    assert aes256 in filtrado


def test_formato_desconocido_se_deja_intacto():
    # No es un keytab 0x0502: no hay que asumir el formato y arriesgarse a
    # corromperlo, mejor devolverlo tal cual llegó.
    datos = b"\x05\x01" + b"\x00" * 30
    assert quitar_entradas_des(datos) == datos


# --- Generación del bloque negotiate en squid.conf --------------------------

class FakeKerberos:
    def __init__(self, enabled=True, realm="EMPRESA.LOCAL", proxy_fqdn="proxy.empresa.local",
                 keytab_data=b"\x05\x02algo"):
        self.enabled = enabled
        self.realm = realm
        self.proxy_fqdn = proxy_fqdn
        self.keytab_data = keytab_data


# --- krb5.conf: permitted_enctypes para que Squid acepte tickets de un AD ---
# real -----------------------------------------------------------------------
# Sin este archivo, libkrb5 usa sus valores por defecto, que en MIT Kerberos
# moderno rechazan RC4-HMAC (el tipo más común en un AD que no está forzado a
# solo-AES) con "Bad encryption type". Confirmado en vivo: mismo keytab válido,
# la autenticación fallaba siempre hasta escribir este archivo.

def test_krb5_conf_incluye_rc4_y_el_realm_indicado():
    contenido = _krb5_conf("EMPRESA.LOCAL")
    assert "default_realm = EMPRESA.LOCAL" in contenido
    assert "rc4-hmac" in contenido
    assert "allow_weak_crypto = true" in contenido
    # AD nombra el realm como el dominio DNS en mayúsculas, siempre: el mapeo
    # se puede derivar sin pedirle el dominio DNS aparte al administrador.
    assert ".empresa.local = EMPRESA.LOCAL" in contenido


def test_escribir_krb5_conf_lo_crea_si_kerberos_esta_activo(tmp_path, monkeypatch):
    ruta = tmp_path / "krb5.conf"
    monkeypatch.setattr(kerberos_service, "KRB5_CONF_PATH", ruta)

    escribir_krb5_conf(FakeKerberos(enabled=True, realm="TEST.COM"))

    assert ruta.exists()
    assert "default_realm = TEST.COM" in ruta.read_text()


def test_escribir_krb5_conf_lo_retira_si_kerberos_no_esta_activo(tmp_path, monkeypatch):
    ruta = tmp_path / "krb5.conf"
    ruta.write_text("resto de una configuracion anterior")
    monkeypatch.setattr(kerberos_service, "KRB5_CONF_PATH", ruta)

    escribir_krb5_conf(FakeKerberos(enabled=False))

    assert not ruta.exists()


def test_escribir_krb5_conf_sin_kerberos_no_crea_nada(tmp_path, monkeypatch):
    ruta = tmp_path / "krb5.conf"
    monkeypatch.setattr(kerberos_service, "KRB5_CONF_PATH", ruta)

    escribir_krb5_conf(None)

    assert not ruta.exists()


def _fake_db_con_kerberos(kerberos):
    from test_config_generator import FakeDB, FakeSetting

    db = FakeDB(settings=[FakeSetting("http_port", "3128", "network")])
    original_query = db.query

    def query(model):
        name = model.__name__ if hasattr(model, "__name__") else str(model)
        if name == "KerberosConfig":
            return db._FakeQuery([kerberos] if kerberos else [])
        return original_query(model)

    db.query = query
    return db


def test_sin_kerberos_configurado_no_se_emite_negotiate():
    from app.services.config_generator import generate_squid_config

    config = generate_squid_config(_fake_db_con_kerberos(None))
    assert "auth_param negotiate" not in config


def test_kerberos_activado_sin_keytab_no_se_emite_negotiate():
    """Sin keytab, apuntar al helper tumbaría la autenticación entera al primer intento."""
    from app.services.config_generator import generate_squid_config

    kerberos = FakeKerberos(enabled=True, keytab_data=None)
    config = generate_squid_config(_fake_db_con_kerberos(kerberos))
    assert "auth_param negotiate" not in config


def test_kerberos_deshabilitado_con_keytab_no_se_emite_negotiate():
    from app.services.config_generator import generate_squid_config

    kerberos = FakeKerberos(enabled=False)
    config = generate_squid_config(_fake_db_con_kerberos(kerberos))
    assert "auth_param negotiate" not in config


def test_kerberos_activado_con_keytab_emite_negotiate_antes_que_basic():
    from app.services.config_generator import generate_squid_config

    kerberos = FakeKerberos(enabled=True, realm="EMPRESA.LOCAL", proxy_fqdn="proxy.empresa.local")
    config = generate_squid_config(_fake_db_con_kerberos(kerberos))
    assert "auth_param negotiate program /usr/lib/squid/negotiate_kerberos_auth" in config
    assert "-s HTTP/proxy.empresa.local@EMPRESA.LOCAL" in config
    assert "-k /etc/squid/HTTP.keytab" in config
    # Basic tiene que seguir presente: Kerberos convive, no reemplaza.
    assert "auth_param basic program" in config
    assert config.index("auth_param negotiate") < config.index("auth_param basic")
