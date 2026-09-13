"""Validación de los identificadores y valores que acaban en squid.conf.

Todo lo que el usuario escribe en el panel (nombres de ACL, de grupo, valores,
listas de ACLs de una regla) se interpola tal cual en el fichero de
configuración de Squid. Sin validar, un salto de línea dentro de un valor
inserta directivas arbitrarias — por ejemplo un `http_access allow all` que
anula toda la política. Y un nombre que coincida con una ACL interna de la
plantilla la pisa en silencio.
"""

import re

from fastapi import HTTPException

# Squid acepta nombres bastante libres; aquí se restringe a algo predecible.
NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")

# Nombres que la plantilla ya define. Reutilizarlos cambia el comportamiento
# de las reglas base sin que el usuario se dé cuenta.
RESERVED_NAMES = {
    "all", "localhost", "to_localhost", "localnet", "manager",
    "SSL_ports", "Safe_ports", "CONNECT", "authenticated",
    "step1", "step2", "step3", "ssl_exclude", "exentos_auth_dominio",
}

# Tipos de ACL admitidos. Cualquier otro se rechaza en lugar de escribirse.
ALLOWED_ACL_TYPES = {
    "src", "dst", "srcdomain", "dstdomain", "srcdom_regex", "dstdom_regex",
    "url_regex", "urlpath_regex", "port", "myport", "proto", "method",
    "browser", "referer_regex", "time", "maxconn", "max_user_ip",
    "proxy_auth", "proxy_auth_regex", "ident", "arp", "req_mime_type",
    "rep_mime_type", "http_status", "snmp_community", "localport",
    "ssl::server_name", "ssl::server_name_regex", "at_step",
}

# Caracteres que romperían la línea o inyectarían otra directiva.
_FORBIDDEN_IN_VALUE = re.compile(r"[\r\n\x00]")


def validate_name(name: str, kind: str = "ACL") -> str:
    """Valida un nombre de ACL o de grupo. Devuelve el nombre ya limpio."""
    name = (name or "").strip()
    if not NAME_PATTERN.match(name):
        raise HTTPException(
            400,
            detail=(
                f"Nombre de {kind} inválido: usa entre 1 y 64 caracteres, "
                "empieza por una letra y combina solo letras, números, guion "
                "y guion bajo."
            ),
        )
    if name in RESERVED_NAMES:
        raise HTTPException(
            400,
            detail=f"'{name}' es un nombre reservado por Squid. Elige otro.",
        )
    if name.startswith("sni_"):
        raise HTTPException(
            400,
            detail="El prefijo 'sni_' lo usa SquidManager para las reglas HTTPS. Elige otro nombre.",
        )
    return name


def validate_acl_type(acl_type: str) -> str:
    """Valida el tipo de ACL contra la lista de tipos admitidos."""
    acl_type = (acl_type or "").strip()
    if acl_type not in ALLOWED_ACL_TYPES:
        raise HTTPException(
            400,
            detail=f"Tipo de ACL no admitido: '{acl_type}'.",
        )
    return acl_type


def validate_value(value: str, field: str = "valor") -> str:
    """Valida el valor de una ACL: una sola línea, sin caracteres de control."""
    value = (value or "").strip()
    if not value:
        raise HTTPException(400, detail=f"El {field} no puede estar vacío.")
    if _FORBIDDEN_IN_VALUE.search(value):
        raise HTTPException(
            400,
            detail=f"El {field} no puede contener saltos de línea.",
        )
    if value.startswith("#"):
        raise HTTPException(400, detail=f"El {field} no puede empezar por '#'.")
    return value


def validate_acl_names(acl_names: str, known: set[str]) -> str:
    """Valida la lista de ACLs de una regla contra las que existen de verdad.

    `known` son los nombres de ACL y de grupo definidos, más los internos de
    la plantilla. Se admite el prefijo '!' para negar.
    """
    acl_names = validate_value(acl_names, "listado de ACLs")
    names = acl_names.split()
    unknown = []
    for raw in names:
        bare = raw[1:] if raw.startswith("!") else raw
        if not bare:
            raise HTTPException(400, detail="Hay un '!' sin ACL detrás.")
        if not NAME_PATTERN.match(bare):
            raise HTTPException(400, detail=f"Nombre de ACL inválido en la regla: '{raw}'.")
        if bare not in known:
            unknown.append(bare)
    if unknown:
        raise HTTPException(
            400,
            detail=(
                "La regla usa ACLs o grupos que no existen: "
                + ", ".join(sorted(set(unknown)))
            ),
        )
    return " ".join(names)


def find_references(db, name: str) -> list[str]:
    """Busca dónde se usa una ACL o un grupo antes de borrarlo o renombrarlo.

    Sin esta comprobación, borrar una ACL dejaba reglas apuntando a un nombre
    inexistente y Squid rechazaba el fichero entero con «ACL not found».

    Devuelve descripciones legibles de cada uso.
    """
    from app.models.access_rule import AccessRule
    from app.models.delay_pool import DelayPool

    used_in = []

    for rule in db.query(AccessRule).all():
        names = {n.lstrip("!") for n in (rule.acl_names or "").split()}
        if name in names:
            used_in.append(f"regla de acceso «{rule.action} {rule.acl_names}»")

    for pool in db.query(DelayPool).all():
        if (pool.acl_name or "").strip() == name:
            used_in.append(f"delay pool #{pool.id} (clase {pool.pool_class})")

    return used_in


def ensure_not_referenced(db, name: str, action: str = "eliminar") -> None:
    """Aborta la operación si el nombre está en uso, diciendo dónde."""
    used_in = find_references(db, name)
    if used_in:
        raise HTTPException(
            409,
            detail=(
                f"No se puede {action} «{name}» porque está en uso: "
                + "; ".join(used_in[:5])
                + (f" y {len(used_in) - 5} más" if len(used_in) > 5 else "")
                + ". Quita primero esas referencias."
            ),
        )


# Un dominio válido para dstdomain: letras, dígitos, guion y punto, con un
# '.' inicial opcional (Squid lo usa para "este dominio y sus subdominios").
# Deliberadamente más estricto que un hostname RFC completo: es mejor
# rechazar una línea rara de un archivo subido y que el admin la revise, que
# aceptarla y que termine siendo, sin querer, una directiva distinta dentro
# del archivo que arma build_acl_list_file().
_DOMINIO_PATTERN = re.compile(r"^\.?[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$")

MAX_DOMINIOS_POR_CARGA = 10_000_000  # cortafuegos ante un archivo descomunal por error
# Subido de 200_000 en la fase de externalización de ACLs (migración 0023):
# antes, guardar el valor en la BD y reescribirlo en cada apply hacía que
# cualquier límite más alto fuera contraproducente. Con el archivo en disco
# como fuente de verdad, el límite real ya no es este número sino cuánta
# memoria tolera validar la lista en Python (ver validar_lista_dominios) -
# eso sigue siendo O(n) y todavía no está pensado para streaming.


def validar_lista_dominios(lineas: list[str]) -> tuple[list[str], list[str]]:
    """Filtra una lista de líneas candidatas a dominio.

    Pensado para archivos subidos por un admin (una blocklist descargada de
    algún lado, exportada de otra herramienta...), no para el valor de una
    ACL ya validada por otro camino. Devuelve (válidos sin duplicar,
    rechazados) en vez de abortar ante la primera línea rara: un archivo de
    miles de dominios con dos o tres líneas basura no debería descartarse
    entero, pero el admin sí tiene que enterarse de cuáles se ignoraron.
    """
    vistos: set[str] = set()
    validos: list[str] = []
    rechazados: list[str] = []

    for cruda in lineas:
        linea = cruda.strip()
        if not linea or linea.startswith("#"):
            continue
        if len(linea) > 253 or not _DOMINIO_PATTERN.match(linea):
            rechazados.append(cruda.rstrip("\n"))
            continue
        clave = linea.lower()
        if clave in vistos:
            continue
        vistos.add(clave)
        validos.append(linea)

    return validos, rechazados


def known_acl_names(db) -> set[str]:
    """Conjunto de nombres utilizables en una regla de acceso."""
    from app.models.acl import Acl
    from app.models.user_group import UserGroup

    names = set(RESERVED_NAMES)
    names.update(a[0] for a in db.query(Acl.name).all())
    names.update(g[0] for g in db.query(UserGroup.name).all())
    # Las ACLs de SNI se generan a partir de las de dominio.
    names.update(
        f"sni_{a[0]}"
        for a in db.query(Acl.name).filter(Acl.type.in_(("dstdomain", "dstdom_regex"))).all()
    )
    return names
