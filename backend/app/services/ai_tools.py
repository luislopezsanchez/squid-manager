"""Herramientas del asistente de IA en modo agéntico (fase 1).

Dos clases de herramienta, y la distinción es la que hace esto seguro:

- **Lectura** (`listar_*`, `ver_*`, `buscar_documentacion`): se ejecutan al
  toque contra la base, y el resultado se le devuelve al modelo. Nunca
  cambian nada.
- **Propuesta** (`proponer_*`): NUNCA se ejecutan. `ejecutar_herramienta()`
  las intercepta y devuelve la propuesta tal cual, sin tocar la base ni
  Squid -quien de verdad la aplica es el administrador, a mano, con el
  mismo botón "Crear" que ya usaría sin el asistente de por medio (ver
  routes/ai.py y el frontend). El modelo no tiene, en ningún punto de este
  módulo, un camino hacia una llamada que escriba algo de verdad.

Los datos que devuelven las de lectura van al proveedor de IA configurado
(Gemini/Groq/NVIDIA) -por eso son deliberadamente estructurales (nombres,
tipos, cantidades) y nunca incluyen contenido de ACLs de archivo, ni
usuarios, ni líneas de log: quién navegó qué no es del asistente.
"""

from sqlalchemy.orm import Session, defer

from app.models.acl import Acl
from app.models.access_rule import AccessRule
from app.models.squid_settings import SquidSetting
from app.models.user_group import UserGroup, UserGroupMember
from app.services.config_state import is_dirty
from app.services.squid_names import ALLOWED_ACL_TYPES

# Nombres de herramienta que solo arman una propuesta -nunca se ejecutan de
# verdad, ver el docstring del módulo y ejecutar_herramienta() más abajo.
HERRAMIENTAS_PROPUESTA = {"proponer_crear_acl"}


def _listar_acls(db: Session) -> dict:
    acls = (
        db.query(Acl).options(defer(Acl.value))
        .order_by(Acl.name).all()
    )
    return {
        "acls": [
            {
                "nombre": a.name, "tipo": a.type, "origen": a.source,
                "es_categoria": a.is_category, "habilitada": a.enabled,
                "cantidad_lineas": a.line_count if a.source == "file" else None,
            }
            for a in acls
        ],
    }


def _listar_reglas_acceso(db: Session) -> dict:
    reglas = db.query(AccessRule).order_by(AccessRule.order, AccessRule.id).all()
    return {
        "reglas": [
            {
                "orden": r.order, "accion": r.action, "acls": r.acl_names,
                "habilitada": r.enabled, "descripcion": r.description,
            }
            for r in reglas
        ],
    }


def _listar_grupos(db: Session) -> dict:
    # Contado en Python, no con un GROUP BY: la tabla de miembros es chica
    # (mismo criterio que ya usa build_backup_dict en routes/backup.py para
    # lo mismo) y evita depender de un agregado SQL para algo tan simple.
    conteos: dict[int, int] = {}
    for m in db.query(UserGroupMember).all():
        conteos[m.group_id] = conteos.get(m.group_id, 0) + 1
    grupos = db.query(UserGroup).order_by(UserGroup.name).all()
    return {
        "grupos": [
            {
                "nombre": g.name, "origen": getattr(g, "source", "local"),
                # Cantidad, no la lista -no hace falta exponer nombres de
                # usuario para diagnosticar un grupo local, y uno de LDAP no
                # tiene miembros propios en la base (se consulta en vivo).
                "cantidad_miembros": conteos.get(g.id, 0),
                "excluido_de_ssl_bump": g.no_bump,
            }
            for g in grupos
        ],
    }


def _ver_ajustes_squid(db: Session) -> dict:
    ajustes = db.query(SquidSetting).order_by(SquidSetting.key).all()
    return {"ajustes": [{"clave": s.key, "valor": s.value, "categoria": s.category} for s in ajustes]}


def _ver_estado_aplicacion(db: Session) -> dict:
    return {
        "hay_cambios_sin_aplicar": is_dirty(),
        "nota": (
            "Si hay cambios sin aplicar, lo que ves en las otras herramientas "
            "es la configuración guardada, no necesariamente la que Squid está "
            "usando en este momento -hace falta 'Aplicar cambios' en el panel."
        ),
    }


def _buscar_documentacion(db: Session, config, pregunta: str) -> dict:
    from app.services.ai_service import _buscar_fragmentos

    fragmentos = _buscar_fragmentos(db, config, pregunta)
    return {
        "fragmentos": [
            {"archivo": c.source_file, "seccion": c.heading, "contenido": c.content}
            for c in fragmentos
        ],
    }


# --- Definición de herramientas (formato JSON Schema, compatible con el
# tool-calling de OpenAI y, con una conversión trivial de nombres de campo,
# con el de Gemini -ver ai_service.py) ---------------------------------

TOOL_DEFS = [
    {
        "name": "listar_acls",
        "description": (
            "Lista las ACLs configuradas: nombre, tipo, origen y si está "
            "habilitada. Para una ACL de archivo no incluye su contenido "
            "(puede tener millones de líneas), solo cuántas tiene."
        ),
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "listar_reglas_acceso",
        "description": "Lista las reglas de acceso (http_access) en su orden real, con las ACLs que referencia cada una.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "listar_grupos",
        "description": "Lista los grupos de usuarios configurados (nombre, origen local/LDAP, cantidad de miembros). No incluye nombres de usuario.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "ver_ajustes_squid",
        "description": "Lista los ajustes generales de Squid configurados en el panel (puerto, esquema de autenticación, SSL Bump, etc.).",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "ver_estado_aplicacion",
        "description": "Indica si hay cambios de configuración guardados que todavía no se aplicaron a Squid.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "buscar_documentacion",
        "description": "Busca en la documentación oficial de SquidManager (cómo se usa una función del panel, conceptos, pasos a seguir).",
        "parameters": {
            "type": "object",
            "properties": {"pregunta": {"type": "string", "description": "Qué buscar en la documentación"}},
            "required": ["pregunta"],
        },
    },
    {
        "name": "proponer_crear_acl",
        "description": (
            "Propone crear una ACL nueva. NO la crea de verdad: arma una "
            "propuesta que se le muestra al administrador para que la revise "
            "y la confirme a mano en el panel, con el mismo botón que usaría "
            "sin este asistente. Usar solo cuando el administrador pidió "
            "explícitamente crear algo, nunca por iniciativa propia."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Nombre técnico: minúsculas, sin espacios ni acentos"},
                "type": {"type": "string", "enum": sorted(ALLOWED_ACL_TYPES)},
                "value": {"type": "string", "description": "El valor de la ACL (ej. dominios para dstdomain)"},
                "description": {"type": "string", "description": "Descripción legible, opcional"},
            },
            "required": ["name", "type", "value"],
        },
    },
]


def ejecutar_herramienta(db: Session, config, nombre: str, argumentos: dict) -> dict:
    """Ejecuta una herramienta de lectura, o intercepta una de propuesta sin
    tocar nada -ver el docstring del módulo."""
    if nombre in HERRAMIENTAS_PROPUESTA:
        return {"__propuesta__": True, "accion": nombre, "argumentos": argumentos}

    if nombre == "listar_acls":
        return _listar_acls(db)
    if nombre == "listar_reglas_acceso":
        return _listar_reglas_acceso(db)
    if nombre == "listar_grupos":
        return _listar_grupos(db)
    if nombre == "ver_ajustes_squid":
        return _ver_ajustes_squid(db)
    if nombre == "ver_estado_aplicacion":
        return _ver_estado_aplicacion(db)
    if nombre == "buscar_documentacion":
        return _buscar_documentacion(db, config, argumentos.get("pregunta", ""))

    raise ValueError(f"Herramienta desconocida: {nombre!r}")
