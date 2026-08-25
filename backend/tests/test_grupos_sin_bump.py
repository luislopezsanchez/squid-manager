"""Pruebas de los grupos exentos de la interceptación de HTTPS.

Hay equipos donde no se puede instalar el certificado (móviles personales) y
herramientas que se rompen al interceptarlas: git, npm, docker y cualquier
aplicación con certificate pinning. Antes, la única salida era desactivar la
interceptación para todo el mundo.

Lo que más se cuida aquí es el **orden** del fichero generado. Squid lo lee de
arriba abajo, y una ACL de usuario no se puede declarar mientras no exista un
esquema de autenticación: puesta antes, Squid aborta el arranque con «Invalid
ACL» y el proxy se queda sin servicio. Eso obligó a reordenar la plantilla.

Se usan dobles propios en lugar de los de test_config_generator porque aquellos
no contemplan grupos con miembros.
"""

from app.services.config_generator import generate_squid_config


class Ajuste:
    def __init__(self, key, value, category="general"):
        self.key, self.value, self.category = key, value, category
        self.description = ""


class Grupo:
    def __init__(self, id, name, miembros, no_bump=False):
        self.id, self.name, self.no_bump = id, name, no_bump
        self.miembros = miembros
        self.description = ""


class Miembro:
    def __init__(self, group_id, username):
        self.group_id, self.username = group_id, username


class BD:
    """Lo justo para que generate_squid_config funcione."""

    def __init__(self, ajustes=None, grupos=None):
        self._ajustes = ajustes or []
        self._grupos = grupos or []
        self._miembros = [
            Miembro(g.id, u) for g in self._grupos for u in g.miembros
        ]

    def query(self, modelo):
        nombre = getattr(modelo, "__name__", str(modelo))
        if nombre == "SquidSetting":
            return _Consulta(self._ajustes)
        if nombre == "UserGroup":
            return _Consulta(self._grupos)
        if nombre == "UserGroupMember":
            return _Consulta(self._miembros)
        return _Consulta([])


class _Consulta:
    def __init__(self, items):
        self._items = items

    def filter(self, *criterios):
        # generate_squid_config filtra los miembros por grupo. El criterio de
        # SQLAlchemy no se puede evaluar aquí, así que se resuelve por el
        # valor que lleva dentro.
        for c in criterios:
            valor = getattr(getattr(c, "right", None), "value", None)
            if valor is not None and self._items and hasattr(self._items[0], "group_id"):
                return _Consulta([m for m in self._items if m.group_id == valor])
        return self

    def order_by(self, *_):
        return self

    def all(self):
        return list(self._items)

    def first(self):
        return self._items[0] if self._items else None


def _config(grupos=None, **ajustes):
    base = [Ajuste("http_port", "3128", "network")]
    base += [Ajuste(k, v, "security") for k, v in ajustes.items()]
    return generate_squid_config(BD(ajustes=base, grupos=grupos or []))


# --- El orden, que es lo que rompía Squid -----------------------------------

def test_la_autenticacion_se_declara_antes_que_la_interceptacion():
    config = _config()
    assert config.index("auth_param basic program") < config.index("ssl_bump peek step1"), (
        "auth_param debe ir antes de ssl_bump: una ACL de usuario declarada "
        "sin esquema de autenticación aborta el arranque de Squid."
    )


def test_la_acl_del_grupo_va_despues_de_la_autenticacion():
    config = _config(grupos=[Grupo(1, "direccion", ["ana"], no_bump=True)])
    assert config.index("auth_param basic program") < config.index("acl nobump_direccion")


# --- Qué se emite y qué no --------------------------------------------------

def test_sin_grupos_exentos_no_se_emite_nada():
    assert "nobump_" not in _config()


def test_un_grupo_exento_genera_su_acl_y_su_splice():
    config = _config(grupos=[Grupo(1, "direccion", ["ana", "luis"], no_bump=True)])
    assert "acl nobump_direccion proxy_auth ana luis" in config
    assert "ssl_bump splice step2 nobump_direccion" in config


def test_un_grupo_normal_no_queda_exento():
    config = _config(grupos=[Grupo(1, "ventas", ["pedro"])])
    assert "nobump_ventas" not in config


def test_un_grupo_exento_pero_vacio_no_emite_acl():
    """Una ACL sin miembros no exime a nadie y solo ensucia el fichero."""
    assert "nobump_vacio" not in _config(grupos=[Grupo(1, "vacio", [], no_bump=True)])


def test_conviven_un_grupo_exento_y_otro_normal():
    config = _config(grupos=[
        Grupo(1, "direccion", ["ana"], no_bump=True),
        Grupo(2, "ventas", ["pedro"]),
    ])
    assert "acl nobump_direccion proxy_auth ana" in config
    assert "nobump_ventas" not in config
    # El grupo normal sigue teniendo su ACL de siempre para las reglas.
    assert "acl ventas proxy_auth pedro" in config


# --- Interacción con lo que ya existía --------------------------------------

def test_la_exencion_no_libra_del_bloqueo_por_dominio():
    """Quedar exento del descifrado no es quedar exento del filtrado.

    El peek del paso 1 sigue por delante: sin él no habría SNI que inspeccionar
    y el bloqueo por dominio dejaría de aplicarse a ese grupo.
    """
    config = _config(grupos=[Grupo(1, "direccion", ["ana"], no_bump=True)])
    assert config.index("ssl_bump peek step1") < config.index("ssl_bump splice step2 nobump_direccion")


def test_sin_interceptacion_global_la_exencion_no_aplica():
    """Si no se descifra a nadie, eximir a un grupo no tiene sentido."""
    config = _config(
        grupos=[Grupo(1, "direccion", ["ana"], no_bump=True)],
        ssl_bump_enabled="false",
    )
    assert "ssl_bump splice all" in config
    assert "nobump_direccion" not in config
