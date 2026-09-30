import re
"""Generador de configuración de Squid usando Jinja2.

Este servicio toma los datos de la BD y genera el archivo squid.conf completo.
La validación de sintaxis vive en `squid_service.validate_squid_config`, que la
ejecuta dentro del contenedor de Squid (en el del backend no hay binario).
"""
# build-lineage: 6b800719-eeeb-43f8-8e6e-92ffbbbb4455

from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from urllib.parse import quote
from sqlalchemy.orm import Session, defer

from app.models.acl import Acl
from app.models.access_rule import AccessRule
from app.models.squid_settings import SquidSetting
from app.models.delay_pool import DelayPool
from app.models.ldap_config import LdapConfig
from app.models.user_group import UserGroup, UserGroupMember
from app.services.dns_service import parsear_lista

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"

# Se reexporta desde el runtime, que es donde vive ahora: en que puerto escucha
# Squid es una cuestion del despliegue, no del generador de configuracion.
from app.services.runtime.base import INTERNAL_SQUID_PORT  # noqa: E402,F401

# Tipos de ACL de dominio: son los que necesitan una regla paralela por SNI
# para que la política también se aplique al tráfico HTTPS.
DOMAIN_ACL_TYPES = ("dstdomain", "dstdom_regex")


def _ascii_seguro(texto: str) -> str:
    """Tilde/eñe -> su base sin acento, cualquier otro no-ASCII se descarta.

    Verificado en vivo, 2026-09-27: el mensaje de un ACL externo (%o,
    deny_info) llega a mostrarse mojibake si tiene bytes UTF-8 de un
    carácter acentuado -Squid los vuelve a escapar como si cada BYTE fuera
    un carácter Latin-1 suelto ("ñ" -> "&#195;&#177;", que un navegador
    renderiza como "Ã±", no como "ñ"). No se encontró ningún ajuste de
    squid.conf para esto -es una limitación real del protocolo de
    external_acl_type, no algo que dependa de esta app-, así que la única
    forma confiable de que el motivo se lea bien es no mandarle bytes no
    ASCII en absoluto. Perder la tilde es un costo menor comparado con
    mostrar texto ilegible en la página que ve el usuario bloqueado.
    """
    import unicodedata

    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")


def _motivo_de_regla(rule, names: list[str]) -> str:
    """Texto de "Motivo" en la página de bloqueo para esta regla deny (ver
    deny_info_acls más abajo y static_message_helper.py).

    Se usa la descripción que el propio admin le puso a la regla si la
    puso -es exactamente el "por qué" que ya escribió, sin inventar nada
    nuevo-; sin ella, un texto genérico armado con las ACLs que componen
    la regla es mejor que un motivo vacío.

    Se sanea para viajar bien por %DATA en la línea `acl ... external ...`
    de squid.conf: sin salto de línea (una descripción es de una sola
    línea, pero por las dudas), sin comillas dobles propias (ahí Squid las
    interpreta como "leer de un archivo", para cualquier tipo de ACL -ver
    el comentario en squid.conf.j2-, así que se reemplazan, no se
    escapan), y sin acentos (ver _ascii_seguro). Cortado a un largo
    razonable: una descripción larga no aporta más leyéndose en una
    tarjeta chica, y evita una línea de configuración kilométrica.
    """
    texto = (rule.description or "").strip()
    if not texto:
        limpios = [n.lstrip("!") for n in names]
        texto = f"No cumple la regla de acceso: {' '.join(limpios)}"
    texto = texto.replace("\n", " ").replace("\r", " ").replace('"', "'")
    texto = _ascii_seguro(texto)
    return texto[:200]


_PUERTO = re.compile(r"^\d{1,5}(-\d{1,5})?$")


def _puertos(valor) -> list[str]:
    """Puertos/rangos extra de Safe_ports o SSL_ports, ya filtrados: lo que no
    es un puerto válido se descarta en vez de llegar al squid.conf."""
    return [t for t in (valor or "").split() if _PUERTO.match(t) and all(1 <= int(x) <= 65535 for x in t.split("-"))]


def generate_squid_config(db: Session, kerberos=None) -> str:
    """Genera el contenido del squid.conf desde la base de datos.

    `kerberos`: fila de KerberosConfig ya cargada, para que quien esté
    aplicando toda la configuración (que también necesita esta fila para
    escribir el keytab) no pague dos consultas por el mismo registro único.
    Si no se pasa, se consulta aquí (compatible con los tests existentes).
    """

    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), trim_blocks=True)
    template = env.get_template("squid.conf.j2")

    # defer(Acl.value): la plantilla solo lee `value` para una ACL 'inline'
    # (una 'file' referencia el archivo por nombre, nunca su contenido -ver
    # squid.conf.j2). Sin esto, cada apply traía de la BD el valor completo
    # de TODAS las ACLs, incluidas las de archivo -donde puede haber
    # millones de líneas que ni siquiera se usan aquí. Con defer(), acceder
    # a `.value` de una ACL 'inline' sí dispara su propia consulta (son
    # pocas y livianas); una 'file' nunca llega a pedirlo.
    acls = (
        db.query(Acl).options(defer(Acl.value))
        .filter(Acl.enabled == True).order_by(Acl.name).all()  # noqa: E712
    )
    rules = (
        db.query(AccessRule)
        .filter(AccessRule.enabled == True)  # noqa: E712
        .order_by(AccessRule.order, AccessRule.id)
        .all()
    )
    settings = {s.key: s.value for s in db.query(SquidSetting).all()}
    delay_pools = db.query(DelayPool).filter(DelayPool.enabled == True).all()  # noqa: E712
    ldap = db.query(LdapConfig).first()

    # cache_mgr: correo que Squid ofrece en %w en sus páginas de error (acá,
    # el link "Contactá a tu administrador" de la página de bloqueo
    # personalizada -ver ERR_SQUIDMANAGER_DENIED). Sin esto, Squid usa su
    # propio default ("webmaster", no una casilla real de nadie). Se toma
    # siempre de la cuenta "admin" (la que crea seed_data() en main.py,
    # ver Admins → esa fila), no de quien esté aplicando los cambios en
    # este momento -es EL contacto administrativo del panel, no algo que
    # dependa de qué admin tocó "Aplicar cambios" por última vez.
    from app.models.admin import Admin

    admin_por_defecto = db.query(Admin).filter(Admin.username == "admin").first()
    cache_mgr_email = (admin_por_defecto.email or "").strip() if admin_por_defecto else ""

    groups = []
    groups_sin_bump = []
    for g in db.query(UserGroup).order_by(UserGroup.name).all():
        source = getattr(g, "source", "local")
        members = (
            []
            if source == "ldap"
            else [
                m.username
                for m in db.query(UserGroupMember).filter(UserGroupMember.group_id == g.id).all()
            ]
        )
        ldap_group_name = getattr(g, "ldap_group_name", None)
        grupo = {
            "name": g.name, "members": members, "source": source,
            # Codificado %XX (mismo criterio que ya usa el protocolo de
            # helpers de Squid para valores con espacios, ver auth_helper.py):
            # squid.conf NO admite un parámetro de ACL con espacios entre
            # comillas como si fuera un string cualquiera -las comillas ahí
            # significan "leer la lista desde este archivo", no "escapar
            # este texto"- confirmado en vivo: "Admins. del dominio" entre
            # comillas rompía el parseo con "Can not open file Admins. for
            # reading". Un único token sin espacios evita el problema del
            # todo, y ldap_group_helper.py ya decodifica cada campo con
            # unquote() por el mismo motivo.
            "ldap_group_name_encoded": quote(ldap_group_name, safe="") if ldap_group_name else None,
            "ldap_group_name": ldap_group_name,
            "ldap_group_nested": getattr(g, "ldap_group_nested", False),
        }
        groups.append(grupo)
        # Solo interesa si tiene a alguien: una ACL de un grupo vacío no puede
        # eximir a nadie, y ensucia la configuración. La excepción de SSL
        # Bump por grupo todavía no soporta grupos de LDAP (el bloque
        # ssl_bump de la plantilla usa proxy_auth con la lista de miembros
        # directo, no el helper externo) -se valida al crear/editar el
        # grupo, así que en la práctica nunca debería llegar acá un grupo
        # LDAP con no_bump=True, pero el filtro por `members` es la
        # salvaguarda real.
        if getattr(g, "no_bump", False) and members:
            groups_sin_bump.append(grupo)

    # Al menos un grupo LDAP -> hace falta declarar el external_acl_type una
    # sola vez (un único pool de helpers, compartido por todos los grupos de
    # AD que existan; cada uno pasa su propio nombre de grupo como parámetro
    # fijo de su ACL, ver plantilla).
    hay_grupos_ldap = any(g["source"] == "ldap" for g in groups)

    domain_acls = {a.name for a in acls if a.type in DOMAIN_ACL_TYPES}

    # Igual criterio que acls_dominio_indexadas más abajo, pero calculado
    # ACÁ (antes del loop de reglas, que lo necesita) sobre `acls` entero
    # en vez de sobre acls_declaradas -que todavía no existe a esta altura,
    # porque depende de referenced_acl_names, que el propio loop construye.
    nombres_dominio_indexados = {
        a.name for a in acls if a.source == "file" and a.type == "dstdomain"
    }

    # Reglas http_access en su orden real. Para cada regla que menciona una ACL
    # de dominio se emite además una regla equivalente por SNI: el ACL
    # dstdomain no casa con las peticiones HTTPS ya descifradas, solo con el
    # CONNECT, así que sin la paralela la política no se aplicaría a HTTPS.
    rendered_rules = []
    # ACLs de dominio que aparecen en alguna regla deny: su tráfico HTTPS se
    # corta en el paso 2 del bump, antes de descifrar nada.
    terminate_acls = []
    # ACLs de dominio que de verdad hace falta declarar por SNI -las que
    # aparecen en alguna regla http_access-, para no declarar (y que Squid
    # tenga que parsear) la variante SNI de una ACL que existe pero a la
    # que ninguna regla hace referencia todavía. Con una lista de millones
    # de dominios esto no es un detalle menor: declarar sni_<nombre> sin
    # que la use ninguna regla le hace parsear ese mismo archivo grande una
    # segunda vez para nada -confirmado en pruebas: quitar esa declaración
    # sobrante bajó el tiempo de `squid -k parse` a menos de la mitad con
    # una ACL de ~5.9M dominios sin usar en ninguna regla.
    domain_acls_used: set[str] = set()
    # Nombres de ACL (de cualquier tipo) que de verdad referencia alguna regla
    # o un delay pool -no solo las de dominio-, para no declarar en absoluto
    # (ni siquiera su línea básica `acl nombre tipo ...`) una ACL 'file' que
    # nadie usa todavía: Squid la carga igual con solo declararla, ANTES de
    # que ninguna regla la mencione. Confirmado en vivo, 2026-09-27: con 9
    # categorías HaGeZi + una lista de ~5.9M dominios habilitadas pero sin
    # ninguna regla que las usara, `squid -k parse` tardaba 67s solo por
    # cargarlas -tiempo que no compraba ningún filtrado real, porque no
    # afectaban a ninguna decisión de tráfico. Es la misma idea que ya
    # aplicaba domain_acls_used más abajo para la variante SNI, extendida a
    # la declaración base.
    from app.services.bandwidth_service import acls_de_pool, directivas
    referenced_acl_names: set[str] = {a for p in delay_pools for a in acls_de_pool(p)}
    delay_descargas = directivas(delay_pools)

    # Nombres de ACL que hace falta declarar en deny_info para que un deny
    # de esa regla muestre la página de bloqueo personalizada -Squid la
    # asocia con la ÚLTIMA ACL de la línea http_access que denegó, no con
    # la regla como un todo (ver deny_info en squid.conf.documented).
    #
    # Cuando esa última ACL ya es dinámica de por sí (una lista de dominios
    # indexada: domain_block_helper.py devuelve la categoría real vía %o)
    # se usa tal cual. Para cualquier OTRA regla deny (por horario, por
    # grupo, por tipo de archivo, por usuario...) Squid no expone ningún
    # tag que diga "qué regla fue" dentro de una página de error -por eso
    # se agrega una ACL sintética al final de la línea, siempre-verdadera
    # (no cambia si la regla matchea, ver static_message_helper.py), solo
    # para que Squid la recuerde como "la última" y deny_info pueda
    # mostrar un motivo específico: la descripción que el admin le puso a
    # la regla, o un texto genérico si no puso ninguna (ver
    # _motivo_de_regla). motivos_reglas guarda ese texto para que la
    # plantilla declare su ACL.
    deny_info_acls: set[str] = set()
    motivos_reglas: dict[str, str] = {}

    for rule in rules:
        names = rule.acl_names.split() if rule.acl_names else []
        if not names:
            continue

        motivo_acl = None
        if rule.action == "deny":
            ultimo = names[-1].lstrip("!")
            if ultimo in nombres_dominio_indexados:
                deny_info_acls.add(ultimo)
            else:
                motivo_acl = f"motivo_regla_{rule.id}"
                motivos_reglas[motivo_acl] = _motivo_de_regla(rule, names)
                deny_info_acls.add(motivo_acl)

        acl_names_str = " ".join(names) + (f" {motivo_acl}" if motivo_acl else "")
        rendered_rules.append({"action": rule.action, "acl_names": acl_names_str})
        referenced_acl_names.update(n.lstrip("!") for n in names)

        mentioned_domains = [n for n in names if n.lstrip("!") in domain_acls]
        if not mentioned_domains:
            continue
        domain_acls_used.update(mentioned_domains)

        sni_names = " ".join(
            (f"!sni_{n[1:]}" if n.startswith("!") else f"sni_{n}")
            if n.lstrip("!") in domain_acls
            else n
            for n in names
        ) + (f" {motivo_acl}" if motivo_acl else "")
        rendered_rules.append({"action": rule.action, "acl_names": sni_names})

        if rule.action == "deny":
            for n in mentioned_domains:
                bare = n.lstrip("!")
                if not n.startswith("!") and bare not in terminate_acls:
                    terminate_acls.append(bare)

    # Solo se declaran en squid.conf las ACLs que de verdad usa algo -ver el
    # comentario de referenced_acl_names más arriba-. Una ACL creada pero
    # todavía no enganchada a ninguna regla/delay pool (categorías HaGeZi
    # recién sincronizadas, una lista subida "para más adelante") no le
    # cuesta nada a Squid hasta que se use de verdad.
    acls_declaradas = [a for a in acls if a.name in referenced_acl_names]

    # "motivo_general" siempre incluida: es la ACL sintética de la que
    # depende el "deny all" final de la plantilla (lo que nadie autorizó
    # explícitamente -la denegación por descarte, la más común-), con un
    # texto fijo declarado directo en squid.conf.j2 (no hay ninguna regla
    # de la que sacar una descripción para este caso).
    deny_info_acls.add("motivo_general")
    deny_info_acls_ordenadas = sorted(deny_info_acls)

    # De las ACLs en uso, las que son una lista de dominios respaldada por
    # archivo (fuente típica: HaGeZi, una blocklist subida a mano) no se
    # declaran con la ACL nativa `dstdomain "archivo"` -que obliga a Squid a
    # cargar la lista entera en memoria en cada parseo, la use o no una
    # regla, y sea del tamaño que sea-, sino contra el helper externo
    # (external_acl_type, ver domain_index_service.py y
    # squid/domain_block_helper.py): Squid solo declara el nombre del
    # helper una vez, y este consulta un índice SQLite por request. Mismo
    # patrón que ya usa hay_grupos_ldap/ldap_group_helper para grupos de AD.
    # dstdom_regex se deja fuera a propósito: un patrón regex no encaja en
    # el índice de sufijos por dominio (ver domain_index_service.matches).
    acls_dominio_indexadas = {
        a.name for a in acls_declaradas if a.source == "file" and a.type == "dstdomain"
    }
    hay_acls_dominio_indexadas = bool(acls_dominio_indexadas)

    # Dominios excluidos del descifrado (banca, sanidad, apps con pinning).
    ssl_exclude = [
        d.strip()
        for d in (settings.get("ssl_bump_exclude") or "").replace("\n", " ").split()
        if d.strip()
    ]

    # Servidores DNS propios. Vacío = Squid usa la resolución del sistema, que
    # es el comportamiento de siempre.
    dns_nameservers = parsear_lista(settings.get("dns_nameservers"))

    # Orígenes exentos de autenticación. Vacío = todos deben autenticarse.
    from app.services.origenes_service import parsear_lista as parsear_origenes

    trusted_sources = parsear_origenes(settings.get("trusted_sources"))

    # Dominios de destino exentos de autenticación, sin importar el origen.
    # A diferencia de trusted_sources (por IP), esto sirve para un destino que
    # no sabe presentar credenciales de proxy (Windows Update, telemetría de
    # Office, un SaaS sin proxy-auth) sin tener que eximir a todo un origen.
    from app.services.auth_exempt_service import parsear_lista as parsear_exentos

    auth_exempt_domains = parsear_exentos(settings.get("auth_exempt_domains"))

    # Interceptación de HTTPS. Activada salvo que se diga lo contrario, que es
    # como se ha comportado siempre. Se apaga cuando la salida va por otro
    # proxy que ya intercepta: encadenar dos interceptaciones rompe HTTPS.
    ssl_bump_enabled = str(
        settings.get("ssl_bump_enabled", "true")
    ).strip().lower() not in ("false", "0", "no", "off")

    # Salida a través de otro proxy. Sin fila o apagado = salida directa.
    from app.models.parent_proxy import ParentProxy
    from app.services.parent_proxy_service import parsear_lista as parsear_destinos

    parent_proxy = db.query(ParentProxy).first()
    direct_domains = parsear_destinos(
        parent_proxy.direct_domains if parent_proxy else None
    )
    # Solo se declara el certificado del padre si hay uno guardado: apuntar a
    # un fichero inexistente deja un WARNING en el log de Squid y ninguna
    # confianza añadida, que es peor que no declararlo.
    parent_ca = bool(
        parent_proxy
        and parent_proxy.enabled
        and (getattr(parent_proxy, "ca_cert", None) or "").strip()
    )

    # Negotiate (Kerberos) solo se declara si esta activo (enabled + keytab
    # subido) segun la unica fuente de verdad de kerberos_activo(): sin esto,
    # apuntar al fichero inexistente tumbaria el helper en el primer intento
    # de autenticacion en vez de simplemente no ofrecer el esquema.
    from app.services.kerberos_service import kerberos_activo

    if kerberos is None:
        from app.models.kerberos_config import KerberosConfig

        kerberos = db.query(KerberosConfig).first()
    kerberos_esta_activo = kerberos_activo(kerberos)

    # En que puerto escribe la directiva `http_port` depende del despliegue: en
    # contenedor es un puerto interno fijo contra el que Docker mapea el que
    # elige el panel; en instalacion nativa no hay mapeo y Squid escucha
    # directamente donde diga el panel.
    from app.services.runtime import get_runtime

    runtime = get_runtime()
    puerto_deseado = str(settings.get("http_port") or INTERNAL_SQUID_PORT).strip()
    puerto_escucha = runtime.listen_port(puerto_deseado)

    config = template.render(
        acls=acls_declaradas,
        rules=rendered_rules,
        terminate_acls=terminate_acls,
        domain_acls_used=domain_acls_used,
        domain_acl_types=DOMAIN_ACL_TYPES,
        acls_dominio_indexadas=acls_dominio_indexadas,
        hay_acls_dominio_indexadas=hay_acls_dominio_indexadas,
        deny_info_acls=deny_info_acls_ordenadas,
        motivos_reglas=motivos_reglas,
        cache_mgr_email=cache_mgr_email,
        settings=settings,
        delay_pools=delay_descargas,
        extra_safe_ports=_puertos(settings.get("extra_safe_ports")),
        extra_ssl_ports=_puertos(settings.get("extra_ssl_ports")),
        ldap=ldap,
        groups=groups,
        hay_grupos_ldap=hay_grupos_ldap,
        ssl_exclude=ssl_exclude,
        internal_port=puerto_escucha,
        modo_despliegue=runtime.name,
        dns_nameservers=dns_nameservers,
        trusted_sources=trusted_sources,
        auth_exempt_domains=auth_exempt_domains,
        ssl_bump_enabled=ssl_bump_enabled,
        groups_sin_bump=groups_sin_bump,
        parent_proxy=parent_proxy,
        direct_domains=direct_domains,
        parent_ca=parent_ca,
        kerberos=kerberos,
        kerberos_esta_activo=kerberos_esta_activo,
    )
    return config
