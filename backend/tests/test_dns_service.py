"""Pruebas de los servidores DNS propios.

Un servidor mal configurado aquí deja al proxy sin resolver ningún nombre, así
que lo que más se cuida es que los valores inválidos se rechacen antes de
llegar al squid.conf.
"""

import socket
import struct

import pytest

from app.services.dns_service import (
    parsear_lista,
    validar_servidores,
    probar_servidor,
    probar_servidores,
    _construir_consulta,
)


# --- Lectura del valor que escribe el administrador -------------------------

@pytest.mark.parametrize("entrada,esperado", [
    ("1.1.1.1", ["1.1.1.1"]),
    ("1.1.1.1 8.8.8.8", ["1.1.1.1", "8.8.8.8"]),
    ("1.1.1.1,8.8.8.8", ["1.1.1.1", "8.8.8.8"]),
    ("1.1.1.1\n8.8.8.8", ["1.1.1.1", "8.8.8.8"]),
    ("  1.1.1.1   8.8.8.8  ", ["1.1.1.1", "8.8.8.8"]),
    ("", []),
    (None, []),
])
def test_parsear_lista(entrada, esperado):
    """Da igual si se separan con espacios, comas o saltos de línea."""
    assert parsear_lista(entrada) == esperado


# --- Validación -------------------------------------------------------------

def test_acepta_ipv4_e_ipv6():
    ok, _ = validar_servidores(["172.27.0.1", "1.1.1.1", "2606:4700:4700::1111"])
    assert ok


def test_rechaza_nombres_de_host():
    """Squid no admite nombres aquí: tendría que resolverlos para resolver."""
    ok, mensaje = validar_servidores(["pihole.local"])
    assert not ok
    assert "pihole.local" in mensaje


def test_rechaza_ip_mal_formada():
    ok, mensaje = validar_servidores(["999.1.1.1"])
    assert not ok
    assert "999.1.1.1" in mensaje


def test_una_ip_mala_invalida_toda_la_lista():
    ok, _ = validar_servidores(["1.1.1.1", "no-es-una-ip"])
    assert not ok


# --- Construcción de la consulta -------------------------------------------

def test_la_consulta_es_un_paquete_dns_valido():
    consulta = _construir_consulta("example.com", 0x1234)
    ident, indicadores, preguntas, respuestas = struct.unpack(">HHHH", consulta[:8])
    assert ident == 0x1234
    assert indicadores == 0x0100      # recursión deseada
    assert preguntas == 1
    assert respuestas == 0
    assert b"\x07example\x03com\x00" in consulta
    assert consulta[-4:] == struct.pack(">HH", 1, 1)   # tipo A, clase Internet


# --- Comprobación contra un servidor ---------------------------------------

def test_rechaza_algo_que_no_es_ip_sin_tocar_la_red():
    ok, mensaje = probar_servidor("no-es-una-ip")
    assert not ok
    assert "no es una dirección IP" in mensaje


def test_avisa_cuando_el_servidor_no_contesta():
    """192.0.2.x está reservada para documentación: nadie responde ahí."""
    ok, mensaje = probar_servidor("192.0.2.1", timeout=0.5)
    assert not ok
    assert "no respondió" in mensaje


def test_lista_vacia_significa_resolucion_del_sistema():
    ok, mensaje = probar_servidores([])
    assert ok
    assert "sistema" in mensaje.lower()


def test_detecta_un_servidor_que_rechaza_la_consulta(monkeypatch):
    """Un DNS que solo atiende a su red responde REFUSED, no silencio."""
    def falso_socket(*args, **kwargs):
        class S:
            def settimeout(self, t): pass
            def sendto(self, datos, destino):
                self.ident = struct.unpack(">H", datos[:2])[0]
            def recvfrom(self, n):
                # RCODE 5 = REFUSED
                cabecera = struct.pack(">HHHHHH", self.ident, 0x8005, 1, 0, 0, 0)
                return cabecera + b"\x00" * 4, None
            def close(self): pass
        return S()

    monkeypatch.setattr(socket, "socket", falso_socket)
    ok, mensaje = probar_servidor("10.0.0.1")
    assert not ok
    assert "rechazó la consulta" in mensaje


def test_detecta_un_servidor_que_responde_sin_resultados(monkeypatch):
    """Responde, pero no resuelve: sirve de poco para navegar."""
    def falso_socket(*args, **kwargs):
        class S:
            def settimeout(self, t): pass
            def sendto(self, datos, destino):
                self.ident = struct.unpack(">H", datos[:2])[0]
            def recvfrom(self, n):
                cabecera = struct.pack(">HHHHHH", self.ident, 0x8180, 1, 0, 0, 0)
                return cabecera + b"\x00" * 4, None
            def close(self): pass
        return S()

    monkeypatch.setattr(socket, "socket", falso_socket)
    ok, mensaje = probar_servidor("10.0.0.1")
    assert not ok
    assert "sin resultados" in mensaje


def test_acepta_una_respuesta_correcta(monkeypatch):
    def falso_socket(*args, **kwargs):
        class S:
            def settimeout(self, t): pass
            def sendto(self, datos, destino):
                self.ident = struct.unpack(">H", datos[:2])[0]
            def recvfrom(self, n):
                cabecera = struct.pack(">HHHHHH", self.ident, 0x8180, 1, 2, 0, 0)
                return cabecera + b"\x00" * 4, None
            def close(self): pass
        return S()

    monkeypatch.setattr(socket, "socket", falso_socket)
    ok, mensaje = probar_servidor("10.0.0.1")
    assert ok
    assert "responde correctamente" in mensaje


# --- Generación del squid.conf ---------------------------------------------

def test_sin_dns_configurado_no_se_emite_la_directiva():
    """Comportamiento de siempre: la resolución del sistema."""
    from test_config_generator import FakeDB, FakeSetting
    from app.services.config_generator import generate_squid_config

    config = generate_squid_config(FakeDB(settings=[FakeSetting("http_port", "3128", "network")]))
    assert "dns_nameservers" not in config


def test_los_servidores_configurados_llegan_al_squid_conf():
    from test_config_generator import FakeDB, FakeSetting
    from app.services.config_generator import generate_squid_config

    db = FakeDB(settings=[
        FakeSetting("http_port", "3128", "network"),
        FakeSetting("dns_nameservers", "172.27.0.1 1.1.1.1", "network"),
    ])
    config = generate_squid_config(db)
    assert "dns_nameservers 172.27.0.1 1.1.1.1" in config


def test_dns_v4_first_solo_si_se_activa():
    from test_config_generator import FakeDB, FakeSetting
    from app.services.config_generator import generate_squid_config

    base = [FakeSetting("http_port", "3128", "network")]
    assert "dns_v4_first" not in generate_squid_config(FakeDB(settings=base))

    con_v4 = base + [FakeSetting("dns_v4_first", "true", "network")]
    assert "dns_v4_first on" in generate_squid_config(FakeDB(settings=con_v4))
