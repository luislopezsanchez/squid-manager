"""proxy_auth_scheme='none': Squid deja pasar clientes sin pedirles usuario
ni contraseña propios -pensado para un hijo cuyo control de acceso real lo
hace el proxy padre-.

Riesgo real que motiva las validaciones de este módulo: sin un padre
configurado, 'none' convierte el proxy en un relay abierto hacia Internet;
y con grupos de usuarios existentes (ACLs `proxy_auth` referenciadas por
reglas), Squid aborta el arranque porque no queda ningún auth_param
declarado del que esas ACLs puedan depender.
"""

from app.services.parent_proxy_service import validar_proxy_auth_scheme_none


class FakeParentProxy:
    def __init__(self, enabled=True):
        self.enabled = enabled


class _FakeQuery:
    def __init__(self, items):
        self._items = items

    def filter(self, *args):
        return self

    def all(self):
        return self._items

    def count(self):
        return len(self._items)

    def first(self):
        return self._items[0] if self._items else None


class FakeDBValidacion:
    def __init__(self, padre=None, grupos=None):
        self._padre = padre
        self._grupos = grupos or []

    def query(self, model):
        name = model.__name__ if hasattr(model, "__name__") else str(model)
        if name == "ParentProxy":
            return _FakeQuery([self._padre] if self._padre else [])
        if name == "UserGroup":
            return _FakeQuery(self._grupos)
        return _FakeQuery([])


# --- Validación: hace falta un padre habilitado -----------------------------

def test_rechaza_sin_padre_configurado():
    ok, mensaje = validar_proxy_auth_scheme_none(FakeDBValidacion(padre=None))
    assert not ok
    assert "proxy padre" in mensaje


def test_rechaza_con_padre_deshabilitado():
    ok, mensaje = validar_proxy_auth_scheme_none(
        FakeDBValidacion(padre=FakeParentProxy(enabled=False))
    )
    assert not ok


def test_acepta_con_padre_habilitado_y_sin_grupos():
    ok, _ = validar_proxy_auth_scheme_none(
        FakeDBValidacion(padre=FakeParentProxy(enabled=True))
    )
    assert ok


# --- Validación: no puede haber grupos de usuarios --------------------------

def test_rechaza_con_grupos_de_usuarios_existentes():
    ok, mensaje = validar_proxy_auth_scheme_none(
        FakeDBValidacion(padre=FakeParentProxy(enabled=True), grupos=["marketing"])
    )
    assert not ok
    assert "grupos" in mensaje.lower()


# --- Generación de squid.conf ------------------------------------------------

def test_none_no_emite_ningun_auth_param():
    from test_config_generator import FakeDB, FakeSetting
    from app.services.config_generator import generate_squid_config

    config = generate_squid_config(FakeDB(settings=[
        FakeSetting("http_port", "3128", "network"),
        FakeSetting("proxy_auth_scheme", "none", "general"),
    ]))
    assert "auth_param basic program" not in config
    assert "auth_param digest program" not in config
    assert "acl authenticated proxy_auth" not in config


def test_none_permite_todo_sin_pedir_credenciales():
    from test_config_generator import FakeDB, FakeSetting
    from app.services.config_generator import generate_squid_config

    config = generate_squid_config(FakeDB(settings=[
        FakeSetting("http_port", "3128", "network"),
        FakeSetting("proxy_auth_scheme", "none", "general"),
    ]))
    assert "http_access allow all" in config
    assert "http_access deny !authenticated" not in config
    assert "http_access allow authenticated" not in config


def test_none_no_declara_acls_de_grupo():
    """Aunque hubiera grupos en BD -algo que la validación ya bloquea antes
    de llegar aquí-, el generador no debe declarar sus ACLs proxy_auth con
    'none': son las que abortarían el arranque de Squid."""
    from test_config_generator import FakeDB, FakeSetting
    from app.services.config_generator import generate_squid_config

    db = FakeDB(settings=[
        FakeSetting("http_port", "3128", "network"),
        FakeSetting("proxy_auth_scheme", "none", "general"),
    ])
    original_query = db.query

    def query(model):
        name = model.__name__ if hasattr(model, "__name__") else str(model)
        if name == "UserGroup":
            class _G:
                id = 1
                name = "marketing"
                no_bump = False
            return db._FakeQuery([_G()])
        if name == "UserGroupMember":
            return db._FakeQuery([])
        return original_query(model)

    db.query = query
    config = generate_squid_config(db)
    assert "acl marketing proxy_auth" not in config


def test_basic_sigue_emitiendo_authenticated_y_grupos():
    """Control: el caso normal (no 'none') no se rompió con estos cambios."""
    from test_config_generator import FakeDB, FakeSetting
    from app.services.config_generator import generate_squid_config

    config = generate_squid_config(FakeDB(settings=[
        FakeSetting("http_port", "3128", "network"),
    ]))
    assert "acl authenticated proxy_auth REQUIRED" in config
    assert "http_access allow authenticated" in config
