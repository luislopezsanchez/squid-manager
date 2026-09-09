"""Import de un squid.conf real (no escrito por SquidManager).

El caso de prueba principal (fixtures_import/) es un squid.conf de un
cliente real, con `include` de ACLs/reglas en archivos aparte, NTLM contra
Active Directory vía winbind, grupos externos y un proxy padre -exactamente
el tipo de configuración "hecha a mano" para la que existe este importador.
"""

from pathlib import Path

import pytest

from app.services import squid_import_service as svc

FIXTURES = Path(__file__).parent / "fixtures_import"


def _leer_fixtures() -> dict[str, str]:
    return {
        "squid.conf": (FIXTURES / "squid.conf").read_text(encoding="utf-8"),
        "acl-pcs.conf": (FIXTURES / "acl-pcs.conf").read_text(encoding="utf-8"),
        "access-pcs.conf": (FIXTURES / "access-pcs.conf").read_text(encoding="utf-8"),
    }


# --- Caso real: un squid.conf de un cliente real, con datos anonimizados ---

def test_resuelve_los_include_por_nombre_de_archivo():
    """Sin resolver 'include', este archivo importaría 0 ACLs y 0 reglas
    -son las líneas que trae, el resto vive en los archivos incluidos-.
    Es justo el bug que tenía la versión anterior del importador."""
    archivos = _leer_fixtures()
    resultado = svc.analizar(archivos, "squid.conf", set(), {"all", "manager"})
    assert not resultado.includes_faltantes
    acls_de_pcs = [a for a in resultado.acls if a.name.lower().startswith("ip")]
    assert len(acls_de_pcs) == 42  # una por PC en acl-pcs.conf


def test_todas_las_acls_de_pcs_son_importables():
    archivos = _leer_fixtures()
    resultado = svc.analizar(archivos, "squid.conf", set(), {"all", "manager"})
    acls_de_pcs = [a for a in resultado.acls if a.name.lower().startswith("ip")]
    assert all(a.estado == "importar" for a in acls_de_pcs)
    assert all(a.type == "src" for a in acls_de_pcs)
    nombres = {a.name for a in acls_de_pcs}
    assert "ippc-recepcion" in nombres
    assert "ipPC-JRECEPCION" in nombres


def test_la_acl_proxy_local_del_admin_tambien_se_importa():
    """`acl proxy src ...` vive en el squid.conf principal, no en un
    include: confirma que el propio archivo principal también se analiza,
    no solo lo incluido."""
    archivos = _leer_fixtures()
    resultado = svc.analizar(archivos, "squid.conf", set(), {"all", "manager"})
    proxy = next(a for a in resultado.acls if a.name == "proxy")
    assert proxy.estado == "importar"
    assert proxy.value == "10.10.10.6/32"


def test_reglas_con_grupos_externos_no_se_importan_pero_se_explica_por_que():
    """gnacional/ginternet son ACLs 'external' (AD vía winbind): no están
    en los archivos subidos como ACL propia (son 'acl gnacional external
    ad_group nacional' en squid.conf), así que toda regla que las use debe
    marcarse como no importable, con el motivo."""
    archivos = _leer_fixtures()
    resultado = svc.analizar(archivos, "squid.conf", set(), {"all", "manager"})
    no_importadas = [r for r in resultado.reglas if r.estado == "no_importada"]
    assert len(no_importadas) > 0
    assert any("gnacional" in r.motivo or "ginternet" in r.motivo for r in no_importadas)


def test_ntlm_se_reporta_como_no_soportado_con_motivo():
    archivos = _leer_fixtures()
    resultado = svc.analizar(archivos, "squid.conf", set(), {"all", "manager"})
    directivas = {h.directiva for h in resultado.no_soportadas}
    assert "auth_param" in directivas
    assert "external_acl_type" in directivas


def test_squidguard_se_reporta_como_no_soportado():
    archivos = _leer_fixtures()
    resultado = svc.analizar(archivos, "squid.conf", set(), {"all", "manager"})
    directivas = {h.directiva for h in resultado.no_soportadas}
    assert "url_rewrite_program" in directivas


def test_cachemgr_passwd_no_se_importa_ni_aparece_en_ninguna_parte():
    """Es una contraseña en texto plano: no debe terminar en ningún campo
    del informe, ni siquiera citada como 'no soportada' con su valor."""
    archivos = _leer_fixtures()
    resultado = svc.analizar(archivos, "squid.conf", set(), {"all", "manager"})
    todo_el_texto = str(resultado.settings) + str(resultado.no_soportadas) + str(resultado.desconocidas)
    assert "REDACTED_PASSWORD" not in todo_el_texto


def test_cache_peer_padre_se_detecta():
    archivos = _leer_fixtures()
    resultado = svc.analizar(archivos, "squid.conf", set(), {"all", "manager"})
    assert resultado.parent_proxy is not None
    assert resultado.parent_proxy.host == "parent.example.com"
    assert resultado.parent_proxy.port == 81
    assert resultado.parent_proxy.estado == "importar"  # sin login=, nada que traducir mal


def test_visible_hostname_y_dns_se_mapean_a_settings():
    archivos = _leer_fixtures()
    resultado = svc.analizar(archivos, "squid.conf", set(), {"all", "manager"})
    claves = {s.key: s.value for s in resultado.settings}
    assert claves.get("visible_hostname") == "proxy.example.com"
    assert claves.get("dns_nameservers") == "10.10.10.2"


def test_access_log_no_se_importa_verbatim():
    """Bug real encontrado en vivo: la plantilla de SquidManager ya antepone
    'stdio:' a access_log; copiar 'daemon:/var/log/squid/access.log squid'
    tal cual produce 'stdio:daemon:/...' y Squid no arranca. access_log NO
    se auto-importa; se informa para revisar a mano."""
    archivos = _leer_fixtures()
    resultado = svc.analizar(archivos, "squid.conf", set(), {"all", "manager"})
    claves = {s.key for s in resultado.settings}
    assert "access_log" not in claves
    directivas_no_soportadas = {h.directiva for h in resultado.no_soportadas}
    assert "access_log" in directivas_no_soportadas


def test_http_port_no_se_importa_para_no_pisar_el_puerto_en_uso():
    archivos = _leer_fixtures()
    resultado = svc.analizar(archivos, "squid.conf", set(), {"all", "manager"})
    claves = {s.key for s in resultado.settings}
    assert "http_port" not in claves
    directivas_no_soportadas = {h.directiva for h in resultado.no_soportadas}
    assert "http_port" in directivas_no_soportadas


# --- Casos sintéticos, más puntuales -------------------------------------

def test_acl_repetida_acumula_valores():
    archivos = {"squid.conf": (
        "acl redsocial dstdomain .facebook.com\n"
        "acl redsocial dstdomain .instagram.com\n"
    )}
    resultado = svc.analizar(archivos, "squid.conf", set(), set())
    assert len(resultado.acls) == 1
    assert resultado.acls[0].value == ".facebook.com .instagram.com"


def test_acl_ya_existente_se_marca_y_no_se_reimporta():
    archivos = {"squid.conf": "acl redes dstdomain .facebook.com\n"}
    resultado = svc.analizar(archivos, "squid.conf", {"redes"}, {"redes"})
    assert resultado.acls[0].estado == "ya_existe"


def test_acl_proxy_auth_no_se_importa_recomienda_grupos():
    archivos = {"squid.conf": "acl vip proxy_auth juan maria\n"}
    resultado = svc.analizar(archivos, "squid.conf", set(), set())
    assert resultado.acls[0].estado == "no_soportado"
    assert "Grupos de usuarios" in resultado.acls[0].motivo


def test_include_faltante_se_reporta_sin_romper_el_analisis():
    archivos = {"squid.conf": "include /etc/squid/no-subido.conf\nacl x src 1.2.3.4/32\n"}
    resultado = svc.analizar(archivos, "squid.conf", set(), set())
    assert resultado.includes_faltantes == ["/etc/squid/no-subido.conf"]
    assert len(resultado.acls) == 1  # el resto del archivo se sigue analizando


def test_include_circular_no_cuelga():
    archivos = {
        "a.conf": "include b.conf\nacl x src 1.1.1.1/32\n",
        "b.conf": "include a.conf\nacl y src 2.2.2.2/32\n",
    }
    resultado = svc.analizar(archivos, "a.conf", set(), set())
    nombres = {a.name for a in resultado.acls}
    assert nombres == {"x", "y"}


def test_continuacion_de_linea_con_backslash():
    archivos = {"squid.conf": "acl grande src 1.1.1.1/32 \\\n  2.2.2.2/32\n"}
    resultado = svc.analizar(archivos, "squid.conf", set(), set())
    assert resultado.acls[0].value == "1.1.1.1/32 2.2.2.2/32"


def test_directiva_totalmente_desconocida_se_reporta_como_tal():
    archivos = {"squid.conf": "una_directiva_inventada foo bar\n"}
    resultado = svc.analizar(archivos, "squid.conf", set(), set())
    assert len(resultado.desconocidas) == 1
    assert resultado.desconocidas[0].directiva == "una_directiva_inventada"


def test_cache_peer_con_login_passthru_no_se_importa():
    archivos = {"squid.conf": "cache_peer padre.com parent 3128 0 login=PASSTHRU\n"}
    resultado = svc.analizar(archivos, "squid.conf", set(), set())
    assert resultado.parent_proxy.estado == "no_soportado"


def test_cache_peer_con_login_user_pass_se_separa_correctamente():
    archivos = {"squid.conf": "cache_peer padre.com parent 3128 0 login=ana:secreta\n"}
    resultado = svc.analizar(archivos, "squid.conf", set(), set())
    assert resultado.parent_proxy.username == "ana"
    assert resultado.parent_proxy.password == "secreta"
    assert resultado.parent_proxy.estado == "importar"


# --- Aplicación (con FakeDB, sin tocar una base real) -----------------------

class _FakeAddedList(list):
    pass


class _FakeQuery:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items

    def filter(self, *a, **k):
        return self

    def first(self):
        return self._items[0] if self._items else None

    def count(self):
        return len(self._items)


class FakeDBImport:
    def __init__(self):
        self.added = []

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        pass

    def query(self, model):
        name = model.__name__ if hasattr(model, "__name__") else str(model)
        ya_agregados = [o for o in self.added if type(o).__name__ == name]
        if name == "Acl":
            return _FakeQuery([o for o in ya_agregados])
        return _FakeQuery(ya_agregados)


def test_aplicar_escribe_solo_lo_marcado_importar(monkeypatch):
    resultado = svc.ResultadoAnalisis(
        acls=[
            svc.ItemAcl("bloqueados", "dstdomain", ".ads.com", "importar"),
            svc.ItemAcl("vip", "proxy_auth", "juan", "no_soportado", "usa grupos"),
        ],
        reglas=[svc.ItemRegla("deny", "bloqueados", "importar")],
    )
    db = FakeDBImport()
    # known_acl_names hace queries de columnas (db.query(Acl.name)) que este
    # FakeDB no reproduce fielmente; se prueba aparte en squid_names, acá
    # alcanza con que devuelva la ACL recién creada como conocida.
    monkeypatch.setattr(svc, "known_acl_names", lambda _db: {"bloqueados"})
    detalle = svc.aplicar(db, resultado)
    assert detalle["acls"] == 1
    assert detalle["reglas"] == 1
    nombres_creados = {o.name for o in db.added if type(o).__name__ == "Acl"}
    assert nombres_creados == {"bloqueados"}


def test_aplicar_importa_proxy_padre_desactivado():
    resultado = svc.ResultadoAnalisis(
        parent_proxy=svc.ItemParentProxy("padre.com", 3128, "ana", "secreta", "importar"),
    )
    db = FakeDBImport()
    detalle = svc.aplicar(db, resultado)
    assert detalle["parent_proxy"] is True
    creado = next(o for o in db.added if type(o).__name__ == "ParentProxy")
    assert creado.enabled is False
    assert creado.host == "padre.com"
    assert any("DESACTIVADO" in a for a in detalle["avisos"])
