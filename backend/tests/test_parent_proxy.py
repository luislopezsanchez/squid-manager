"""Pruebas de la salida a través de un proxy padre.

Lo que más se cuida aquí es distinguir las formas de fallar, porque cada una se
arregla de manera distinta y un mensaje genérico no ayuda a nadie: no se llega
al padre, pide credenciales, exige un método que Squid no sabe presentar, o
responde y deja pasar.
"""

import socket
import struct

import pytest

from app.services.parent_proxy_service import (
    parsear_lista,
    validar_destino,
    probar_padre,
    probar_configuracion,
    _metodos_ofrecidos,
)


# --- Lectura de la lista de destinos directos -------------------------------

@pytest.mark.parametrize("entrada,esperado", [
    (".intranet.local", [".intranet.local"]),
    (".intranet.local .empresa.com", [".intranet.local", ".empresa.com"]),
    (".a.com,.b.com", [".a.com", ".b.com"]),
    (".a.com\n.b.com", [".a.com", ".b.com"]),
    ("", []),
    (None, []),
])
def test_parsear_destinos_directos(entrada, esperado):
    assert parsear_lista(entrada) == esperado


# --- Validación del destino -------------------------------------------------

def test_destino_valido():
    ok, _ = validar_destino("proxy.empresa.local", 8080)
    assert ok


def test_falta_el_host():
    ok, mensaje = validar_destino("", 8080)
    assert not ok
    assert "dirección" in mensaje


def test_puerto_fuera_de_rango():
    ok, mensaje = validar_destino("proxy.local", 70000)
    assert not ok
    assert "70000" in mensaje


def test_puerto_no_numerico():
    ok, mensaje = validar_destino("proxy.local", "ocho mil")
    assert not ok
    assert "número" in mensaje


# --- Lectura de los métodos que ofrece el padre -----------------------------

def test_detecta_los_metodos_ofrecidos():
    cabeceras = (
        "HTTP/1.1 407 Proxy Authentication Required\r\n"
        "Proxy-Authenticate: Negotiate\r\n"
        "Proxy-Authenticate: NTLM\r\n"
    )
    assert _metodos_ofrecidos(cabeceras) == ["negotiate", "ntlm"]


# --- Comprobación contra el padre -------------------------------------------

def _falso_proxy(monkeypatch, respuesta: str):
    """Sustituye el socket por uno que devuelve la respuesta indicada."""
    class FalsoSocket:
        def __init__(self):
            self.enviado = b""

        def sendall(self, datos):
            self.enviado += datos

        def recv(self, n):
            datos, self._resto = self._resto[:n], self._resto[n:]
            return datos

        def close(self):
            pass

    def crear(direccion, timeout=None):
        s = FalsoSocket()
        s._resto = respuesta.encode()
        crear.ultimo = s
        return s

    monkeypatch.setattr(socket, "create_connection", crear)
    return crear


def test_padre_que_deja_pasar(monkeypatch):
    _falso_proxy(monkeypatch, "HTTP/1.1 200 OK\r\nServer: squid\r\n\r\n<html>")
    ok, mensaje = probar_padre("proxy.local", 8080)
    assert ok
    assert "deja salir" in mensaje


def test_padre_que_pide_credenciales_y_no_se_dieron(monkeypatch):
    _falso_proxy(monkeypatch,
        "HTTP/1.1 407 Proxy Authentication Required\r\n"
        "Proxy-Authenticate: Basic realm=\"corp\"\r\n\r\n")
    ok, mensaje = probar_padre("proxy.local", 8080)
    assert not ok
    assert "credenciales" in mensaje


def test_padre_que_rechaza_las_credenciales(monkeypatch):
    _falso_proxy(monkeypatch,
        "HTTP/1.1 407 Proxy Authentication Required\r\n"
        "Proxy-Authenticate: Basic realm=\"corp\"\r\n\r\n")
    ok, mensaje = probar_padre("proxy.local", 8080, "juan", "malaclave")
    assert not ok
    assert "rechazó las credenciales" in mensaje


def test_padre_con_ntlm_avisa_de_que_squid_no_puede(monkeypatch):
    """El caso que ahorra una tarde de probar usuarios y contraseñas."""
    _falso_proxy(monkeypatch,
        "HTTP/1.1 407 Proxy Authentication Required\r\n"
        "Proxy-Authenticate: NTLM\r\n\r\n")
    ok, mensaje = probar_padre("proxy.local", 8080, "juan", "clave")
    assert not ok
    assert "NTLM" in mensaje
    assert "no sabe presentar" in mensaje
    assert "Basic" in mensaje


def test_padre_que_prohibe_la_salida(monkeypatch):
    _falso_proxy(monkeypatch, "HTTP/1.1 403 Forbidden\r\n\r\n")
    ok, mensaje = probar_padre("proxy.local", 8080)
    assert not ok
    assert "no permite" in mensaje


def test_las_credenciales_viajan_en_la_peticion(monkeypatch):
    """Comprueba que se envía la cabecera, no solo que no falle."""
    crear = _falso_proxy(monkeypatch, "HTTP/1.1 200 OK\r\n\r\n")
    probar_padre("proxy.local", 8080, "juan", "secreto")
    enviado = crear.ultimo.enviado.decode()
    assert "Proxy-Authorization: Basic anVhbjpzZWNyZXRv" in enviado  # juan:secreto


def test_padre_inalcanzable(monkeypatch):
    def rechazar(direccion, timeout=None):
        raise ConnectionRefusedError()
    monkeypatch.setattr(socket, "create_connection", rechazar)

    ok, mensaje = probar_padre("proxy.local", 8080)
    assert not ok
    assert "rechazó la conexión" in mensaje


def test_padre_que_no_responde(monkeypatch):
    def colgar(direccion, timeout=None):
        raise socket.timeout()
    monkeypatch.setattr(socket, "create_connection", colgar)

    ok, mensaje = probar_padre("proxy.local", 8080, timeout=1)
    assert not ok
    assert "no respondió" in mensaje


# --- Configuración completa -------------------------------------------------

class FalsaConfig:
    def __init__(self, **kwargs):
        self.enabled = kwargs.get("enabled", False)
        self.host = kwargs.get("host")
        self.port = kwargs.get("port", 3128)
        self.username = kwargs.get("username")
        self.password = kwargs.get("password")


def test_apagado_significa_salida_directa():
    ok, mensaje = probar_configuracion(FalsaConfig(enabled=False))
    assert ok
    assert "directa" in mensaje


def test_sin_configuracion_tampoco_estorba():
    ok, _ = probar_configuracion(None)
    assert ok


# --- Generación del squid.conf ---------------------------------------------

def test_sin_padre_no_se_emite_cache_peer():
    from test_config_generator import FakeDB, FakeSetting
    from app.services.config_generator import generate_squid_config

    config = generate_squid_config(
        FakeDB(settings=[FakeSetting("http_port", "3128", "network")])
    )
    assert "cache_peer" not in config
    assert "never_direct" not in config
