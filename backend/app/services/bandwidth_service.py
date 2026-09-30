"""Reglas de ancho de banda (delay pools v2): objetivos, tipos de tráfico y
traducción a directivas de Squid.

Una regla nueva tiene VARIOS objetivos (ACLs, usuarios, grupos, tipos de
tráfico, o «todo») y un límite de velocidad de descarga. Cada objetivo se
resuelve a una ACL de Squid; varias `delay_access ... allow <acl>` en la misma
pool se combinan con O (las ACLs dentro de UNA línea se combinan con Y), que
es justo lo que significa «esta regla aplica a A, B o C».

Qué puede y qué no puede hacer Squid (documentación oficial, squid-cache.org,
y verificado en vivo en Squid 6.14):
- delay_pools/delay_parameters limitan la velocidad a la que Squid entrega al
  cliente lo que descarga de los servidores (bajada). Funcionan también con
  objetivos por usuario (proxy_auth): medido 305 KB/s con un límite de 300.
- NO existe en Squid un límite de SUBIDA. `client_delay_pools` parece serlo por
  su documentación, pero se probó: con un POST de 3 MB el límite no cambia la
  subida (2,9 MB/s con o sin regla) y lo que sí frena es la respuesta hacia el
  cliente, por IP. Además `client_delay_access` se evalúa al aceptar la
  conexión, antes de autenticar, así que no puede distinguir usuarios. Por eso
  esta plataforma no ofrece límite de subida.
- Squid NO reserva ni garantiza ancho de banda a nadie: solo pone techos. La
  reserva/priorización real y el límite de subida se hacen con `tc` en el
  sistema operativo, fuera de Squid.
- Las clases 2, 3 y 4 de delay pools solo funcionan con IPv4.
"""

import hashlib
import json
import re

from fastapi import HTTPException

# Cubo agregado «sin límite práctico» para la clase 2 (agregado + individual):
# lo que importa al admin es el tope individual; el agregado solo existe
# porque el formato de Squid lo pide.
AGREGADO_SIN_LIMITE = 1073741824  # 1 GB/s

KINDS = ("acl", "user", "group", "tipo", "all")

# Tipos de tráfico que se pueden limitar sin escribir una expresión regular.
# Squid decide por la URL (extensión al final del path, con o sin query
# string): no ve el contenido real, así que un vídeo servido sin extensión
# (streaming adaptativo) no se detecta -se dice en la ayuda del panel.
TIPOS_TRAFICO = {
    "video": {
        "etiqueta": "Vídeo",
        "descripcion": "Archivos de vídeo por extensión (mp4, mkv, avi, mov, webm, flv, wmv, m4v, mpg)",
        "extensiones": ["mp4", "mkv", "avi", "mov", "webm", "flv", "wmv", "m4v", "mpg", "mpeg"],
    },
    "audio": {
        "etiqueta": "Audio y música",
        "descripcion": "Archivos de audio por extensión (mp3, flac, wav, aac, ogg, m4a)",
        "extensiones": ["mp3", "flac", "wav", "aac", "ogg", "m4a", "wma", "opus"],
    },
    "descargas": {
        "etiqueta": "Descargas grandes",
        "descripcion": "Comprimidos, imágenes de disco e instaladores (zip, rar, 7z, iso, exe, msi, dmg, apk, deb, rpm)",
        "extensiones": ["zip", "rar", "7z", "gz", "tar", "iso", "exe", "msi", "dmg", "apk", "deb", "rpm", "img"],
    },
    "documentos": {
        "etiqueta": "Documentos",
        "descripcion": "Documentos de oficina y PDF (pdf, doc, docx, xls, xlsx, ppt, pptx)",
        "extensiones": ["pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "odt", "ods"],
    },
}


def nombre_acl_tipo(clave: str) -> str:
    return f"bw_tipo_{clave}"


def nombre_acl_usuario(username: str) -> str:
    """Nombre de ACL estable para un usuario: los usernames admiten '.', las
    ACLs de Squid no, así que se usa un resumen del nombre."""
    return "bw_usr_" + hashlib.sha1(username.encode("utf-8")).hexdigest()[:10]


def _regex_extensiones(exts: list[str]) -> str:
    lista = "|".join(re.escape(e) for e in exts)
    return f"-i \\.({lista})($|\\?)"


def asegurar_acl_tipo(db, clave: str) -> str:
    from app.models.acl import Acl

    tipo = TIPOS_TRAFICO[clave]
    nombre = nombre_acl_tipo(clave)
    acl = db.query(Acl).filter(Acl.name == nombre).first()
    valor = _regex_extensiones(tipo["extensiones"])
    if not acl:
        db.add(Acl(name=nombre, type="url_regex", value=valor, enabled=True,
                   description=f"Tipo de tráfico: {tipo['etiqueta']}"))
        db.flush()
    elif acl.value != valor:
        acl.value = valor
    return nombre


def asegurar_acl_usuario(db, username: str) -> str:
    from app.models.acl import Acl

    nombre = nombre_acl_usuario(username)
    acl = db.query(Acl).filter(Acl.name == nombre).first()
    if not acl:
        db.add(Acl(name=nombre, type="proxy_auth", value=username, enabled=True,
                   description=f"Ancho de banda: usuario {username}"))
        db.flush()
    elif acl.value != username:
        acl.value = username
    return nombre


def resolver_objetivos(db, objetivos: list[dict]) -> list[dict]:
    """Valida cada objetivo y le agrega la ACL de Squid a la que corresponde.
    Devuelve la lista normalizada [{kind, value, acl}]."""
    from app.models.acl import Acl
    from app.models.user_group import UserGroup
    from app.models.proxy_user import ProxyUser
    from app.models.ldap_user import LdapUser

    if not objetivos:
        raise HTTPException(400, detail="Elige al menos un objetivo para la regla (ACL, usuario, grupo, tipo de tráfico o todo el tráfico).")
    if len(objetivos) > 200:
        raise HTTPException(400, detail="Demasiados objetivos en una misma regla (máximo 200).")

    resueltos, vistos = [], set()
    for o in objetivos:
        kind = (o.get("kind") or "").strip()
        value = (o.get("value") or "").strip()
        if kind not in KINDS:
            raise HTTPException(400, detail=f"Tipo de objetivo desconocido: {kind!r}.")
        if (kind, value) in vistos:
            continue
        vistos.add((kind, value))

        if kind == "all":
            acl = "all"
        elif kind == "tipo":
            if value not in TIPOS_TRAFICO:
                raise HTTPException(400, detail=f"Tipo de tráfico desconocido: {value!r}.")
            acl = asegurar_acl_tipo(db, value)
        elif kind == "user":
            if not (db.query(ProxyUser).filter(ProxyUser.username == value).first()
                    or db.query(LdapUser).filter(LdapUser.username == value).first()):
                raise HTTPException(400, detail=f"El usuario {value!r} no existe.")
            acl = asegurar_acl_usuario(db, value)
        elif kind == "group":
            if not db.query(UserGroup).filter(UserGroup.name == value).first():
                raise HTTPException(400, detail=f"El grupo {value!r} no existe.")
            acl = value
        else:  # acl
            if not db.query(Acl).filter(Acl.name == value).first():
                raise HTTPException(400, detail=f"La ACL {value!r} no existe.")
            acl = value
        resueltos.append({"kind": kind, "value": value, "acl": acl})
    return resueltos


def validar_limite(download_bps) -> None:
    if not download_bps:
        raise HTTPException(400, detail="Indica el límite de velocidad de descarga.")
    if not (1 <= download_bps <= 10 * 1024 * 1024 * 1024):
        raise HTTPException(400, detail="El límite debe estar entre 1 byte/s y 10 GB/s.")


def parametros_descarga(download_bps: int, shared: bool) -> tuple[int, str]:
    """(clase, parámetros) para delay_class / delay_parameters."""
    if shared:
        return 1, f"{download_bps}/{download_bps}"
    return 2, f"{AGREGADO_SIN_LIMITE}/{AGREGADO_SIN_LIMITE} {download_bps}/{download_bps}"


def serializar_objetivos(resueltos: list[dict]) -> tuple[str, str]:
    """(JSON de targets, acl_names separados por espacio, sin repetir)."""
    acls = list(dict.fromkeys(r["acl"] for r in resueltos))
    return json.dumps(resueltos, ensure_ascii=False), " ".join(acls)


def cargar_objetivos(pool) -> list[dict]:
    if not getattr(pool, "targets", None):
        return []
    try:
        return json.loads(pool.targets)
    except (TypeError, ValueError):
        return []


def acls_de_pool(pool) -> list[str]:
    """ACLs a las que aplica un pool, sea nuevo (targets) o antiguo (acl_name)."""
    if getattr(pool, "acl_names", None):
        return pool.acl_names.split()
    return [pool.acl_name.strip()] if pool.acl_name else ["all"]


def directivas(pools) -> list[dict]:
    """Traduce los pools habilitados a la lista para la plantilla de
    delay_pools: [{clase, parametros, acls}]."""
    salida = []
    for p in pools:
        acls = acls_de_pool(p)
        if p.targets is None:
            salida.append({"clase": p.pool_class, "parametros": p.parameters, "acls": acls})
        elif p.download_bps:
            clase, params = parametros_descarga(p.download_bps, bool(p.shared))
            salida.append({"clase": clase, "parametros": params, "acls": acls})
    return salida
