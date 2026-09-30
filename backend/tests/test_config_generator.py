"""Tests del generador de squid.conf (Jinja2)."""

import pytest
from app.services.config_generator import generate_squid_config


class FakeSetting:
    def __init__(self, key, value, category="general", description=""):
        self.key = key
        self.value = value
        self.category = category
        self.description = description


class FakeAcl:
    def __init__(self, name, type_, value, enabled=True, description="", source="inline"):
        self.name = name
        self.type = type_
        self.value = value
        self.enabled = enabled
        self.description = description
        self.source = source


class FakeRule:
    def __init__(self, action, acl_names, order, enabled=True, description="", id=None):
        self.action = action
        self.acl_names = acl_names
        self.order = order
        self.enabled = enabled
        self.description = description
        # motivo_regla_<id> (ver config_generator._motivo_de_regla): el id
        # solo necesita ser único dentro de una misma llamada, así que
        # reusar `order` alcanza para las pruebas sin pedir un id aparte
        # en cada FakeRule(...) existente.
        self.id = id if id is not None else order


class FakeUser:
    def __init__(self, username, enabled=True):
        self.username = username
        self.enabled = enabled


class _FakeAdmin:
    def __init__(self, email):
        self.username = "admin"
        self.email = email


class FakeDelayPool:
    def __init__(self, pool_class, parameters, acl_name="", enabled=True):
        self.pool_class = pool_class
        self.parameters = parameters
        self.acl_name = acl_name
        self.enabled = enabled
        # Campos de las reglas nuevas de ancho de banda (None = regla antigua).
        self.targets = None
        self.acl_names = None
        self.download_bps = None
        self.shared = True


class FakeLdap:
    def __init__(self, enabled=False, server_url="", bind_dn="", search_base="", user_filter="(uid=%s)"):
        self.enabled = enabled
        self.server_url = server_url
        self.bind_dn = bind_dn
        self.search_base = search_base
        self.user_filter = user_filter


class FakeDB:
    """Simula una sesión SQLAlchemy con queries básicas."""

    def __init__(self, settings=None, acls=None, rules=None, users=None, delay_pools=None, ldap=None,
                 groups=None, group_members=None, admin_email=None):
        self._settings = settings or []
        self._acls = acls or []
        self._rules = rules or []
        self._users = users or []
        self._delay_pools = delay_pools or []
        self._ldap = ldap
        self._groups = groups or []
        self._group_members = group_members or []
        # Solo se usa si algún test pasa admin_email: el filtro por
        # username="admin" es un no-op en este doble (ver filter() más
        # abajo), así que basta con un único FakeAdmin.
        self._admin = _FakeAdmin(admin_email) if admin_email is not None else None

    def query(self, model):
        name = model.__name__ if hasattr(model, "__name__") else str(model)
        if name == "SquidSetting":
            return self._FakeQuery(self._settings)
        elif name == "Acl":
            return self._FakeQuery(self._acls)
        elif name == "AccessRule":
            return self._FakeQuery(self._rules)
        elif name == "ProxyUser":
            return self._FakeQuery(self._users)
        elif name == "DelayPool":
            return self._FakeQuery(self._delay_pools)
        elif name == "LdapConfig":
            return self._FakeQuery([self._ldap] if self._ldap else [])
        elif name == "UserGroup":
            return self._FakeQuery(self._groups)
        elif name == "UserGroupMember":
            # El .filter(group_id == ...) de config_generator es un no-op acá
            # (como el resto de filtros de este doble): para un test con más
            # de un grupo, pasar solo los miembros del grupo que interesa.
            return self._FakeQuery(self._group_members)
        elif name == "Admin":
            return self._FakeQuery([self._admin] if self._admin else [])
        return self._FakeQuery([])

    class _FakeQuery:
        def __init__(self, items):
            self._items = items

        def all(self):
            return self._items

        def filter(self, *args):
            # Ignoramos filtros en los tests (simulan datos ya filtrados)
            return self

        def order_by(self, *args):
            return self

        def options(self, *args, **kwargs):
            # No-op: config_generator usa defer(Acl.value) para no traer el
            # contenido de una ACL de archivo; este doble ya guarda los
            # objetos completos en memoria, así que no hay nada que diferir.
            return self

        def first(self):
            return self._items[0] if self._items else None


def test_generate_basic_config():
    db = FakeDB(
        settings=[FakeSetting("http_port", "3128", "network")],
        acls=[FakeAcl("redes_sociales", "dstdomain", ".facebook.com")],
        rules=[FakeRule("deny", "redes_sociales", 0)],
    )
    config = generate_squid_config(db)
    assert "http_port 3128" in config
    assert "acl redes_sociales dstdomain .facebook.com" in config
    assert "http_access deny redes_sociales" in config


def test_generate_ssl_bump_config():
    db = FakeDB(
        settings=[FakeSetting("http_port", "3128", "network")],
        acls=[FakeAcl("redes_sociales", "dstdomain", ".facebook.com")],
        rules=[FakeRule("deny", "redes_sociales", 0)],
    )
    config = generate_squid_config(db)
    # SSL Bump debe generar terminate por SNI para ACLs dstdomain deny
    assert "ssl_bump" in config.lower()
    assert "sni_redes_sociales" in config
    assert "ssl_bump terminate" in config


def test_generate_delay_pools():
    db = FakeDB(
        settings=[FakeSetting("http_port", "3128", "network")],
        delay_pools=[FakeDelayPool(2, "64000/64000 64000/32000")],
    )
    config = generate_squid_config(db)
    assert "delay_pools 1" in config
    assert "delay_class 1 2" in config
    assert "delay_parameters 1 64000/64000 64000/32000" in config


def test_generate_empty_config():
    db = FakeDB()
    config = generate_squid_config(db)
    assert "http_port" in config  # al menos el puerto por defecto


def test_acl_no_referenciada_por_ninguna_regla_no_se_declara():
    """Una ACL creada pero que ninguna regla ni delay pool usa todavía no le
    cuesta nada a Squid: no se declara en absoluto (ni su línea básica), a
    diferencia de la SNI -que ya se omitía solo para ACLs de dominio-."""
    db = FakeDB(
        acls=[
            FakeAcl("usada", "dstdomain", ".ejemplo.com"),
            FakeAcl("sin_usar", "dstdomain", ".otro-ejemplo.com"),
        ],
        rules=[FakeRule("deny", "usada", 0)],
    )
    config = generate_squid_config(db)
    assert "acl usada dstdomain .ejemplo.com" in config
    assert "sin_usar" not in config


def test_acl_referenciada_solo_por_un_delay_pool_si_se_declara():
    db = FakeDB(
        acls=[FakeAcl("streaming", "dstdomain", ".youtube.com")],
        delay_pools=[FakeDelayPool(2, "64000/64000 64000/32000", acl_name="streaming")],
    )
    config = generate_squid_config(db)
    assert "acl streaming dstdomain .youtube.com" in config


def test_acl_referenciada_con_negacion_si_se_declara():
    db = FakeDB(
        acls=[
            FakeAcl("bloqueados", "dstdomain", ".bloqueado.com"),
            FakeAcl("excepcion", "src", "10.0.0.5/32"),
        ],
        rules=[FakeRule("allow", "excepcion !bloqueados", 0)],
    )
    config = generate_squid_config(db)
    assert "acl bloqueados dstdomain .bloqueado.com" in config
    assert "acl excepcion src 10.0.0.5/32" in config


class FakeGroup:
    def __init__(self, name, description="", no_bump=False, source="local",
                 ldap_group_name=None, ldap_group_nested=False):
        self.id = abs(hash(name)) % 1000
        self.name = name
        self.description = description
        self.no_bump = no_bump
        self.source = source
        self.ldap_group_name = ldap_group_name
        self.ldap_group_nested = ldap_group_nested


class FakeGroupMember:
    def __init__(self, group_id, username):
        self.group_id = group_id
        self.username = username


def test_el_orden_de_las_reglas_se_respeta():
    """Las reglas salen en el orden del panel.

    La versión anterior extraía las reglas «deny <grupo>» del flujo y las
    refundía al final, con lo que el orden mostrado dejaba de significar nada.
    """
    db = FakeDB(
        settings=[FakeSetting("http_port", "3128", "network")],
        acls=[FakeAcl("uy_domains", "dstdomain", ".uy")],
        rules=[
            FakeRule("allow", "Nacional uy_domains", 0),
            FakeRule("deny", "Nacional", 1),
        ],
    )
    config = generate_squid_config(db)
    pos_allow = config.index("http_access allow Nacional uy_domains")
    pos_deny = config.index("http_access deny Nacional")
    assert pos_allow < pos_deny


def test_se_fuerza_la_autenticacion_antes_de_las_reglas():
    """`deny !authenticated` va antes: así un deny de grupo da 403 y no 407."""
    db = FakeDB(
        settings=[FakeSetting("http_port", "3128", "network")],
        rules=[FakeRule("deny", "Nacional", 0)],
    )
    config = generate_squid_config(db)
    assert "http_access deny !authenticated" in config
    assert config.index("deny !authenticated") < config.index("http_access deny Nacional")


def test_regla_sni_paralela_para_reglas_con_varias_acls():
    """Con varias ACLs en la misma regla también se genera la paralela por SNI.

    Antes se comparaba el campo entero con el nombre de una ACL, así que en
    cuanto la regla combinaba dos condiciones no se generaba nada para HTTPS.
    """
    db = FakeDB(
        settings=[FakeSetting("http_port", "3128", "network")],
        acls=[
            FakeAcl("redes_sociales", "dstdomain", ".facebook.com"),
            FakeAcl("horario", "time", "M-F 09:00-17:00"),
        ],
        rules=[FakeRule("deny", "redes_sociales horario", 0)],
    )
    config = generate_squid_config(db)
    assert "http_access deny sni_redes_sociales horario" in config
    assert "ssl_bump terminate step2 sni_redes_sociales" in config


def test_dominios_excluidos_del_descifrado():
    """Los dominios excluidos se hacen splice antes del bump."""
    db = FakeDB(
        settings=[
            FakeSetting("http_port", "3128", "network"),
            FakeSetting("ssl_bump_exclude", ".banco.com .salud.gob", "security"),
        ],
    )
    config = generate_squid_config(db)
    assert "acl ssl_exclude ssl::server_name .banco.com .salud.gob" in config
    assert config.index("ssl_bump splice step2 ssl_exclude") < config.index("ssl_bump bump step3 all")


def test_store_log_desactivado_por_defecto():
    """store.log escribe mucho y no lo consume nadie."""
    db = FakeDB(settings=[FakeSetting("http_port", "3128", "network")])
    config = generate_squid_config(db)
    assert "cache_store_log none" in config


def test_rutas_de_log_con_prefijo_stdio():
    db = FakeDB(settings=[FakeSetting("http_port", "3128", "network")])
    config = generate_squid_config(db)
    assert "access_log stdio:/var/log/squid/access.log" in config


def test_idioma_de_las_paginas_de_error():
    db = FakeDB(settings=[FakeSetting("http_port", "3128", "network")])
    config = generate_squid_config(db)
    assert "error_default_language es" in config


def test_base_de_certificados_en_el_volumen_persistente():
    """La base vivía en /tmp y se perdía en cada reinicio del contenedor."""
    db = FakeDB(settings=[FakeSetting("http_port", "3128", "network")])
    config = generate_squid_config(db)
    assert "-s /var/lib/ssl_crtd/db" in config
    assert "/tmp/ssl_crtd" not in config


def test_shutdown_lifetime_corto_por_defecto():
    """purge_credentials() hace un restart de verdad para vaciar la caché de
    credenciales validadas -con el shutdown_lifetime de 30s por defecto de
    Squid, cada borrado/deshabilitación de usuario desde el panel quedaba
    bloqueado ese tiempo de más. Medido en vivo, 2026-09-27: un DELETE de
    usuario tardaba 46s; con este default baja a unos pocos segundos."""
    db = FakeDB(settings=[FakeSetting("http_port", "3128", "network")])
    config = generate_squid_config(db)
    assert "shutdown_lifetime 1 second" in config


def test_shutdown_lifetime_configurable():
    db = FakeDB(settings=[
        FakeSetting("http_port", "3128", "network"),
        FakeSetting("shutdown_lifetime", "5 seconds", "general"),
    ])
    config = generate_squid_config(db)
    assert "shutdown_lifetime 5 seconds" in config


# --- Grupos locales vs. grupos de LDAP/Active Directory --------------------

def test_grupo_local_se_traduce_a_proxy_auth():
    db = FakeDB(
        settings=[FakeSetting("http_port", "3128", "network")],
        groups=[FakeGroup("ventas", source="local")],
        group_members=[FakeGroupMember(0, "jperez"), FakeGroupMember(0, "mgomez")],
    )
    config = generate_squid_config(db)
    assert "acl ventas proxy_auth jperez mgomez" in config
    assert "external_acl_type ldap_group_helper" not in config


def test_grupo_local_vacio_usa_el_placeholder():
    db = FakeDB(
        settings=[FakeSetting("http_port", "3128", "network")],
        groups=[FakeGroup("vacio", source="local")],
    )
    config = generate_squid_config(db)
    assert "acl vacio proxy_auth __EMPTY_GROUP__" in config


def test_grupo_ldap_declara_el_helper_externo_una_sola_vez():
    db = FakeDB(
        settings=[FakeSetting("http_port", "3128", "network")],
        groups=[
            FakeGroup("ad_ventas", source="ldap", ldap_group_name="Ventas"),
            FakeGroup("ad_soporte", source="ldap", ldap_group_name="Soporte Tecnico"),
        ],
    )
    config = generate_squid_config(db)
    assert config.count("external_acl_type ldap_group_helper") == 1
    # Codificado %XX y sin comillas a proposito: squid.conf interpreta un
    # parametro de ACL entre comillas como "leer desde este archivo", no
    # como un string con espacios escapado -confirmado en vivo, ver el
    # comentario en config_generator.py junto a ldap_group_name_encoded.
    assert "acl ad_ventas external ldap_group_helper Ventas direct" in config
    assert "acl ad_soporte external ldap_group_helper Soporte%20Tecnico direct" in config
    assert '"Soporte Tecnico"' not in config


def test_grupo_ldap_anidado_usa_el_parametro_nested():
    db = FakeDB(
        settings=[FakeSetting("http_port", "3128", "network")],
        groups=[FakeGroup("ad_admins", source="ldap", ldap_group_name="Domain Admins", ldap_group_nested=True)],
    )
    config = generate_squid_config(db)
    assert "acl ad_admins external ldap_group_helper Domain%20Admins nested" in config


def test_sin_grupos_ldap_no_se_declara_el_helper():
    db = FakeDB(
        settings=[FakeSetting("http_port", "3128", "network")],
        groups=[FakeGroup("solo_local", source="local")],
        group_members=[FakeGroupMember(0, "jperez")],
    )
    config = generate_squid_config(db)
    assert "external_acl_type ldap_group_helper" not in config


def test_grupos_locales_y_ldap_conviven():
    db = FakeDB(
        settings=[FakeSetting("http_port", "3128", "network")],
        groups=[
            FakeGroup("local1", source="local"),
            FakeGroup("ad1", source="ldap", ldap_group_name="Grupo1"),
        ],
    )
    config = generate_squid_config(db)
    assert "acl local1 proxy_auth __EMPTY_GROUP__" in config
    assert "acl ad1 external ldap_group_helper Grupo1 direct" in config
    assert config.count("external_acl_type ldap_group_helper") == 1


# --- Página de bloqueo personalizada (deny_info) ----------------------------

def test_deny_info_se_declara_para_la_ultima_acl_de_una_regla_deny():
    """Squid asocia deny_info con la ÚLTIMA ACL de la línea que denegó, no
    con la regla como un todo -acá ninguna de las dos ACLs es una lista de
    dominios indexada (dinámica de por sí), así que se agrega una ACL
    sintética de motivo al final (ver static_message_helper.py), sin
    descripción propia cae al texto genérico armado con las ACLs."""
    db = FakeDB(
        settings=[FakeSetting("http_port", "3128", "network")],
        acls=[FakeAcl("red_local", "src", "192.168.1.0/24"), FakeAcl("bloqueados", "dstdomain", ".ejemplo.com")],
        rules=[FakeRule("deny", "red_local bloqueados", 0)],
    )
    config = generate_squid_config(db)
    assert "http_access deny red_local bloqueados motivo_regla_0" in config
    assert "deny_info ERR_SQUIDMANAGER_DENIED motivo_regla_0" in config
    assert 'acl motivo_regla_0 external squidmanager_static_message_helper No cumple la regla de acceso: red_local bloqueados' in config


def test_deny_info_siempre_incluye_all_como_respaldo():
    """"motivo_general" es de la que depende el "deny all" final -la
    denegación por descarte, el caso más común- así que siempre se
    declara, haya o no reglas deny personalizadas."""
    db = FakeDB(settings=[FakeSetting("http_port", "3128", "network")])
    config = generate_squid_config(db)
    assert "http_access deny all motivo_general" in config
    assert "deny_info ERR_SQUIDMANAGER_DENIED motivo_general" in config


def test_deny_info_no_se_declara_para_una_regla_allow():
    db = FakeDB(
        settings=[FakeSetting("http_port", "3128", "network")],
        acls=[FakeAcl("red_local", "src", "192.168.1.0/24")],
        rules=[FakeRule("allow", "red_local", 0)],
    )
    config = generate_squid_config(db)
    assert "deny_info ERR_SQUIDMANAGER_DENIED red_local" not in config


def test_deny_info_no_se_repite_para_una_acl_de_dominio_indexada():
    """Una lista de dominios indexada (source='file', ver
    acls_dominio_indexadas) es dinámica de por sí -%o ya muestra la
    categoría real, vía domain_block_helper.py-, así que dos reglas que la
    usan como última ACL comparten la misma línea de deny_info, sin
    duplicar ni agregarle ninguna ACL sintética."""
    db = FakeDB(
        settings=[FakeSetting("http_port", "3128", "network")],
        acls=[FakeAcl("bloqueados", "dstdomain", None, source="file")],
        rules=[
            FakeRule("deny", "bloqueados", 0),
            FakeRule("deny", "bloqueados", 1, description="otra regla, misma ACL"),
        ],
    )
    config = generate_squid_config(db)
    assert config.count("deny_info ERR_SQUIDMANAGER_DENIED bloqueados") == 1
    assert "motivo_regla_0" not in config
    assert "motivo_regla_1" not in config


def test_deny_info_cada_regla_sin_acl_dinamica_tiene_su_propio_motivo():
    """Sin una ACL dinámica al final, cada regla obtiene su PROPIA ACL
    sintética de motivo (por rule.id) -aunque dos reglas usen el mismo
    nombre de ACL, cada una puede tener su propia descripción."""
    db = FakeDB(
        settings=[FakeSetting("http_port", "3128", "network")],
        acls=[FakeAcl("bloqueados", "src", "10.0.0.0/8")],
        rules=[
            FakeRule("deny", "bloqueados", 0, description="primera regla"),
            FakeRule("deny", "bloqueados", 1, description="otra regla, misma ACL"),
        ],
    )
    config = generate_squid_config(db)
    assert 'acl motivo_regla_0 external squidmanager_static_message_helper primera regla' in config
    assert 'acl motivo_regla_1 external squidmanager_static_message_helper otra regla, misma ACL' in config
    assert "deny_info ERR_SQUIDMANAGER_DENIED motivo_regla_0" in config
    assert "deny_info ERR_SQUIDMANAGER_DENIED motivo_regla_1" in config


def test_una_descripcion_con_comillas_dobles_no_rompe_la_linea_de_acl():
    """Una descripción escrita a mano puede traer comillas dobles -se
    reemplazan por simples, no se intenta escapar (no está probado que
    Squid soporte un escape ahí adentro, y total no cambia el sentido)."""
    db = FakeDB(
        settings=[FakeSetting("http_port", "3128", "network")],
        acls=[FakeAcl("bloqueados", "src", "10.0.0.0/8")],
        rules=[FakeRule("deny", "bloqueados", 0, description='Bloqueado "temporalmente" por soporte')],
    )
    config = generate_squid_config(db)
    assert 'acl motivo_regla_0 external squidmanager_static_message_helper Bloqueado \'temporalmente\' por soporte' in config


# --- cache_mgr (correo de contacto de la página de bloqueo) -----------------

def test_cache_mgr_usa_el_correo_de_la_cuenta_admin_por_defecto():
    db = FakeDB(settings=[FakeSetting("http_port", "3128", "network")], admin_email="soporte@empresa.com")
    config = generate_squid_config(db)
    assert "cache_mgr soporte@empresa.com" in config


def test_sin_correo_de_admin_no_se_declara_cache_mgr():
    db = FakeDB(settings=[FakeSetting("http_port", "3128", "network")], admin_email="")
    config = generate_squid_config(db)
    assert "cache_mgr" not in config


def test_motivo_de_regla_pierde_los_acentos():
    """Verificado en vivo: un motivo con tildes/eñe llega mojibake a la
    página de bloqueo (Squid reescapa los bytes UTF-8 del mensaje de un
    ACL externo como si cada uno fuera un carácter Latin-1 suelto) -la
    única forma confiable de evitarlo es no mandar bytes no-ASCII."""
    db = FakeDB(
        settings=[FakeSetting("http_port", "3128", "network")],
        acls=[FakeAcl("bloqueados", "src", "10.0.0.0/8")],
        rules=[FakeRule("deny", "bloqueados", 0, description="Política de horario: mañana no, tarde sí")],
    )
    config = generate_squid_config(db)
    assert "acl motivo_regla_0 external squidmanager_static_message_helper Politica de horario: manana no, tarde si" in config


# --- Reglas de ancho de banda nuevas: varios objetivos, bajada y subida -----

def _pool_v2(acl_names, download=None, shared=True):
    p = FakeDelayPool(1, "", acl_name=acl_names.split()[0])
    p.targets = "[]"
    p.acl_names = acl_names
    p.download_bps = download
    p.shared = shared
    return p


def test_regla_con_varios_objetivos_genera_un_allow_por_objetivo():
    db = FakeDB(
        settings=[FakeSetting("http_port", "3128", "network")],
        acls=[FakeAcl("redes", "dstdomain", ".facebook.com"), FakeAcl("video", "dstdomain", ".youtube.com")],
        delay_pools=[_pool_v2("redes video", download=65536)],
    )
    config = generate_squid_config(db)
    assert "delay_class 1 1" in config
    assert "delay_parameters 1 65536/65536" in config
    # Un allow por objetivo (se combinan con O), no una sola línea con las dos (Y).
    assert "delay_access 1 allow redes\n" in config
    assert "delay_access 1 allow video\n" in config
    assert "delay_access 1 deny all" in config


def test_limite_por_equipo_usa_clase_2_con_agregado_sin_limite():
    db = FakeDB(
        settings=[FakeSetting("http_port", "3128", "network")],
        acls=[FakeAcl("redes", "dstdomain", ".facebook.com")],
        delay_pools=[_pool_v2("redes", download=32768, shared=False)],
    )
    config = generate_squid_config(db)
    assert "delay_class 1 2" in config
    assert "delay_parameters 1 1073741824/1073741824 32768/32768" in config


def test_acl_de_una_regla_nueva_se_declara():
    db = FakeDB(
        settings=[FakeSetting("http_port", "3128", "network")],
        acls=[FakeAcl("redes", "dstdomain", ".facebook.com"), FakeAcl("otra", "dstdomain", ".x.com")],
        delay_pools=[_pool_v2("redes", download=1000)],
    )
    config = generate_squid_config(db)
    assert "acl redes dstdomain" in config
    assert "acl otra " not in config
