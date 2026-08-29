"""Generador de configuración de Squid usando Jinja2.

Este servicio toma los datos de la BD y genera el archivo squid.conf completo.
La validación de sintaxis vive en `squid_service.validate_squid_config`, que la
ejecuta dentro del contenedor de Squid (en el del backend no hay binario).
"""

from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from sqlalchemy.orm import Session

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


def generate_squid_config(db: Session) -> str:
    """Genera el contenido del squid.conf desde la base de datos."""

    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), trim_blocks=True)
    template = env.get_template("squid.conf.j2")

    acls = db.query(Acl).filter(Acl.enabled == True).order_by(Acl.name).all()  # noqa: E712
    rules = (
        db.query(AccessRule)
        .filter(AccessRule.enabled == True)  # noqa: E712
        .order_by(AccessRule.order, AccessRule.id)
        .all()
    )
    settings = {s.key: s.value for s in db.query(SquidSetting).all()}
    delay_pools = db.query(DelayPool).filter(DelayPool.enabled == True).all()  # noqa: E712
    ldap = db.query(LdapConfig).first()

    groups = []
    groups_sin_bump = []
    for g in db.query(UserGroup).order_by(UserGroup.name).all():
        members = [
            m.username
            for m in db.query(UserGroupMember).filter(UserGroupMember.group_id == g.id).all()
        ]
        grupo = {"name": g.name, "members": members}
        groups.append(grupo)
        # Solo interesa si tiene a alguien: una ACL de un grupo vacío no puede
        # eximir a nadie, y ensucia la configuración.
        if getattr(g, "no_bump", False) and members:
            groups_sin_bump.append(grupo)

    domain_acls = {a.name for a in acls if a.type in DOMAIN_ACL_TYPES}

    # Reglas http_access en su orden real. Para cada regla que menciona una ACL
    # de dominio se emite además una regla equivalente por SNI: el ACL
    # dstdomain no casa con las peticiones HTTPS ya descifradas, solo con el
    # CONNECT, así que sin la paralela la política no se aplicaría a HTTPS.
    rendered_rules = []
    # ACLs de dominio que aparecen en alguna regla deny: su tráfico HTTPS se
    # corta en el paso 2 del bump, antes de descifrar nada.
    terminate_acls = []

    for rule in rules:
        names = rule.acl_names.split() if rule.acl_names else []
        if not names:
            continue

        rendered_rules.append({"action": rule.action, "acl_names": " ".join(names)})

        mentioned_domains = [n for n in names if n.lstrip("!") in domain_acls]
        if not mentioned_domains:
            continue

        sni_names = " ".join(
            (f"!sni_{n[1:]}" if n.startswith("!") else f"sni_{n}")
            if n.lstrip("!") in domain_acls
            else n
            for n in names
        )
        rendered_rules.append({"action": rule.action, "acl_names": sni_names})

        if rule.action == "deny":
            for n in mentioned_domains:
                bare = n.lstrip("!")
                if not n.startswith("!") and bare not in terminate_acls:
                    terminate_acls.append(bare)

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

    # En que puerto escribe la directiva `http_port` depende del despliegue: en
    # contenedor es un puerto interno fijo contra el que Docker mapea el que
    # elige el panel; en instalacion nativa no hay mapeo y Squid escucha
    # directamente donde diga el panel.
    from app.services.runtime import get_runtime

    runtime = get_runtime()
    puerto_deseado = str(settings.get("http_port") or INTERNAL_SQUID_PORT).strip()
    puerto_escucha = runtime.listen_port(puerto_deseado)

    config = template.render(
        acls=acls,
        rules=rendered_rules,
        terminate_acls=terminate_acls,
        domain_acl_types=DOMAIN_ACL_TYPES,
        settings=settings,
        delay_pools=delay_pools,
        ldap=ldap,
        groups=groups,
        ssl_exclude=ssl_exclude,
        internal_port=puerto_escucha,
        modo_despliegue=runtime.name,
        dns_nameservers=dns_nameservers,
        trusted_sources=trusted_sources,
        ssl_bump_enabled=ssl_bump_enabled,
        groups_sin_bump=groups_sin_bump,
        parent_proxy=parent_proxy,
        direct_domains=direct_domains,
        parent_ca=parent_ca,
    )
    return config
