"""Migrar desde un Squid administrado a mano: listas de ACL en archivos aparte,
usuarios htpasswd/htdigest, puertos propios, alias de proxy_auth...
(app/services/squid_import_service.py + squid_import_extras.py).

Los datos son sintéticos pero con la forma de una instalación real: un
squid.conf con rutas absolutas del servidor de origen y archivos que lo
acompañan."""
from app.services import squid_import_extras as ex
from app.services import squid_import_service as svc

HA1 = "0123456789abcdef0123456789abcdef"
BCRYPT = "$2y$05$" + "a" * 53
APR1 = "$apr1$8sFt66rZ$" + "b" * 22
DES = "abcdefghijklm"

SQUID_CONF = """
auth_param digest program /usr/lib/squid/digest_file_auth -c /etc/squid/d-usuarios
auth_param digest realm MIEMPRESA
auth_param digest children 10
acl SSL_ports port 443
acl SSL_ports port 873 10000
acl Safe_ports port 80 443 1025-65535 2000 1500-1600 20
acl usersproxy proxy_auth REQUIRED
acl lan src 192.168.1.0/24
acl moviles src "/etc/squid/ip_moviles"
acl bloqueados url_regex -i "/etc/squid/denegados"
acl intranet dstdomain .empresa.local .empresa.com
acl faltante src "/etc/squid/no_subido"
http_access deny bloqueados
http_access allow lan usersproxy !bloqueados
http_access allow moviles
http_access allow faltante
http_access deny all
cache_peer 10.0.0.1 parent 3128 0 no-query
never_direct allow all
always_direct allow intranet
http_reply_access allow all
cache_swap_low 98
directiva_inventada algo
"""

ARCHIVOS = {
    "squid.conf": SQUID_CONF,
    "ip_moviles": "10.1.0.5\n10.1.0.6 # portatil de Ana\n\n# comentario\n10.1.0.7\n",
    "denegados": "adult\ncasino\n",
    "d-usuarios": f"ana:MIEMPRESA:{HA1}\nbob:MIEMPRESA:{HA1}\ncarla:OTRO:{HA1}\n",
    "usuarios": f"ana:{BCRYPT}\ndiego:{APR1}\nelena:{DES}\n",
    "script.sh": "#!/bin/sh\necho hola\n",
}


def _analizar(**kw):
    conocidos = {"all", "localhost", "manager", "to_localhost", "SSL_ports", "Safe_ports", "CONNECT", "localnet", "authenticated"}
    return svc.analizar(dict(ARCHIVOS), "squid.conf", set(), conocidos, **kw)


# --- listas de ACL en archivo ------------------------------------------------

def test_lista_en_archivo_se_inserta_sin_comentarios_ni_lineas_vacias():
    r = ex.resolver_valor_acl("src", '"/etc/squid/ip_moviles"', {"ip_moviles": ARCHIVOS["ip_moviles"]})
    assert r.problema == "" and r.valor == "10.1.0.5 10.1.0.6 10.1.0.7" and r.archivos == ["ip_moviles"]


def test_opciones_de_squid_se_conservan_delante_de_los_valores():
    r = ex.resolver_valor_acl("url_regex", '-i "/x/denegados"', {"denegados": "adult\ncasino\n"})
    assert r.valor == "-i adult casino"


def test_archivo_no_subido_explica_que_falta():
    r = ex.resolver_valor_acl("src", '"/etc/squid/falta"', {})
    assert "no se subió" in r.problema and r.archivos == ["falta"]


def test_regex_con_espacios_no_se_puede_inlinear():
    r = ex.resolver_valor_acl("url_regex", '"/x/p"', {"p": "foo bar\nbaz\n"})
    assert "espacios" in r.problema


def test_lista_grande_de_dominios_va_como_lista_de_archivo():
    texto = "\n".join(f"sitio{i}.com" for i in range(ex.MAX_ENTRADAS_INLINE + 5))
    r = ex.resolver_valor_acl("dstdomain", '"/x/d"', {"d": texto})
    assert r.lista is not None and len(r.lista) == ex.MAX_ENTRADAS_INLINE + 5 and r.valor == ""


# --- puertos -----------------------------------------------------------------

def test_puertos_extra_ignora_los_que_la_base_ya_cubre():
    assert ex.puertos_extra("80 443 1025-65535 2000 873 20 1500-1600 900-950", ex.BASE_SAFE_PORTS) == ["873", "20", "900-950"]
    assert ex.puertos_extra("443 563 10000", ex.BASE_SSL_PORTS) == ["563", "10000"]


# --- usuarios ------------------------------------------------------------------

def test_formatos_de_linea_de_usuario():
    assert ex.clasificar_linea_usuario(f"a:{BCRYPT}")[0] == "htpasswd"
    assert ex.clasificar_linea_usuario(f"a:{APR1}")[0] == "htpasswd"
    assert ex.clasificar_linea_usuario(f"a:{DES}")[0] == "htpasswd"
    assert ex.clasificar_linea_usuario(f"a:REALM:{HA1}") == ("digest", ("a", "REALM", HA1))
    assert ex.clasificar_linea_usuario("10.0.0.1") is None
    assert ex.clasificar_linea_usuario("sitio.com") is None


def test_una_lista_de_ips_o_dominios_no_es_un_archivo_de_usuarios():
    assert not ex.es_archivo_de_usuarios("10.0.0.1\n10.0.0.2\n")
    assert not ex.es_archivo_de_usuarios(".gmail.com\n.yahoo.com\n")
    assert ex.es_archivo_de_usuarios(f"a:{BCRYPT}\nb:{APR1}\n")


# --- análisis completo -------------------------------------------------------

def test_acl_con_lista_en_archivo_se_importa_con_su_contenido():
    r = _analizar()
    moviles = next(a for a in r.acls if a.name == "moviles")
    assert moviles.estado == "importar" and moviles.value == "10.1.0.5 10.1.0.6 10.1.0.7"
    assert next(a for a in r.acls if a.name == "bloqueados").value == "-i adult casino"


def test_acl_con_lista_que_no_se_subio_no_se_importa_y_su_regla_tampoco():
    r = _analizar()
    assert next(a for a in r.acls if a.name == "faltante").estado == "no_soportado"
    assert any("faltante" in x.acl_names and x.estado == "no_importada" for x in r.reglas)


def test_proxy_auth_required_es_alias_de_authenticated_y_las_reglas_se_reescriben():
    r = _analizar()
    assert next(a for a in r.acls if a.name == "usersproxy").estado == "alias"
    regla = next(x for x in r.reglas if "lan" in x.acl_names.split())
    assert regla.acl_names == "lan authenticated !bloqueados" and regla.estado == "importar"


def test_puertos_propios_pasan_a_ajustes():
    r = _analizar()
    assert r.extra_ssl_ports == ["873", "10000"]
    assert r.extra_safe_ports == ["20"]        # 2000 y 1500-1600 ya están dentro de 1025-65535
    claves = {s.key: s.value for s in r.settings}
    assert claves["extra_ssl_ports"] == "873 10000"


def test_esquema_digest_y_realm_salen_del_squid_conf_y_los_usuarios_conservan_su_clave():
    r = _analizar()
    assert r.esquema_auth == "digest" and r.realm_auth == "MIEMPRESA"
    por_nombre = {u.username: u for u in r.usuarios}
    assert por_nombre["ana"].estado == "importar" and por_nombre["ana"].digest_ha1 == HA1
    assert por_nombre["ana"].htpasswd_hash == BCRYPT           # también su hash de Basic
    assert por_nombre["bob"].estado == "importar"
    # sin clave de Digest para ese realm: se importa deshabilitado
    assert por_nombre["diego"].estado == "sin_credencial" and por_nombre["diego"].habilitado is False
    assert por_nombre["elena"].estado == "sin_credencial"
    # carla solo tenía una clave de OTRO realm: no sirve con MIEMPRESA
    assert por_nombre["carla"].estado == "sin_credencial"
    assert any("otro realm" in n for n in r.notas)
    claves = {s.key: s.value for s in r.settings}
    assert claves["proxy_auth_scheme"] == "digest" and claves["auth_realm"] == "MIEMPRESA"


def test_con_ldap_activo_no_se_cambia_a_digest():
    r = _analizar(ldap_habilitado=True)
    assert r.esquema_auth == "basic"
    assert next(u for u in r.usuarios if u.username == "diego").estado == "importar"
    assert any("LDAP" in n for n in r.notas)


def test_usuarios_que_ya_existen_no_se_reimportan():
    r = _analizar(usuarios_existentes={"ana"})
    assert next(u for u in r.usuarios if u.username == "ana").estado == "ya_existe"


def test_los_archivos_de_listas_no_se_confunden_con_usuarios():
    r = _analizar()
    assert sorted(r.archivos_usuarios) == ["d-usuarios", "usuarios"]
    assert "ip_moviles" in r.archivos_lista and "script.sh" not in r.archivos_usuarios


def test_never_direct_y_dominios_directos_pasan_al_proxy_padre():
    r = _analizar()
    assert r.never_direct is True
    assert r.direct_domains == [".empresa.local", ".empresa.com"]


def test_directivas_conocidas_sin_equivalente_no_se_llaman_desconocidas():
    r = _analizar()
    no_sop = {h.directiva for h in r.no_soportadas}
    assert {"http_reply_access", "cache_swap_low"} <= no_sop
    assert [h.directiva for h in r.desconocidas] == ["directiva_inventada"]
