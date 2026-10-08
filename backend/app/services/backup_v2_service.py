"""Backup y restauración de SquidManager, formato 2 (`.smbackup`).

Objetivo: que lo exportado desde un SquidManager, importado en OTRO, lo deje
configurado idéntico -no «casi»-. El formato anterior (JSON) perdía cosas sin
avisar: los hashes de contraseña de los usuarios, el contenido de las listas
de dominios, el proxy padre, Kerberos, syslog, SMTP, notificaciones, las
cuotas de grupo, los límites de ancho de banda nuevos...

Diseño:

- **Dirigido por tabla.** Cada entidad declara qué columnas son secretas y cuáles
  son estado de ejecución (no se respaldan). El resto de columnas se exporta
  sola: si mañana una tabla gana una columna, entra en el backup sin tocar
  este módulo.
- **Un paquete ZIP** con `manifest.json` (versión, conteos y sha256 de cada parte),
  `config.json` (toda la configuración sin secretos), `acl_lists/*.txt.gz`
  (contenido de las listas grandes de dominios) y, solo si se eligió una
  contraseña, `secrets.enc`: los secretos (hashes de contraseñas de usuarios,
  claves de LDAP/SMTP/Telegram/XMPP/IA, keytab...) cifrados con Fernet y una clave
  derivada de esa contraseña con scrypt. Sin contraseña, el backup no lleva
  ningún secreto.
- **Restaurar es transaccional**: se valida y aplica todo dentro de una
  transacción; si algo falla no queda nada a medias. `simular=True` ejecuta el
  mismo camino y deshace al final, así el informe previo es exactamente lo que
  pasaría. Dos modos: `combinar` (agrega y actualiza) y `reemplazar` (deja el
  servidor igual al backup: lo que no está en el backup se elimina).
- Lo que NO viaja a propósito: administradores del panel, auditoría, mensajes de
  contacto, índice de documentación, consumo de cuotas y el `instance_id` del
  Panel central (identifica a ESTE servidor).
"""

from __future__ import annotations

import base64
import gzip
import hashlib
import io
import json
import logging
import re
import zipfile
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import inspect as sa_inspect

logger = logging.getLogger(__name__)

FORMATO = "squidmanager-backup"
VERSION_FORMATO = 2
MAX_PAQUETE_BYTES = 512 * 1024 * 1024
MAX_PARTE_BYTES = 256 * 1024 * 1024  # una parte descomprimida (una lista enorme de dominios)


def _gunzip_acotado(blob: bytes) -> bytes:
    """Descomprime un gzip sin superar MAX_PARTE_BYTES (una «bomba» de compresión no agota la memoria)."""
    import zlib
    d = zlib.decompressobj(wbits=31)
    salida = d.decompress(blob, MAX_PARTE_BYTES + 1)
    if len(salida) > MAX_PARTE_BYTES:
        raise ValueError("Una parte del paquete descomprimida es demasiado grande.")
    return salida

_COMUNES = {"id", "created_at", "updated_at"}


@dataclass
class Entidad:
    nombre: str
    modelo_path: str                       # "app.models.acl:Acl"
    clave: tuple[str, ...] = ()            # vacío = singleton (una sola fila)
    excluir: frozenset = frozenset()
    secretas: frozenset = frozenset()
    filtro: str | None = None              # expresión sobre `Modelo` para limitar filas
    ordenar: str | None = None


ENTIDADES: list[Entidad] = [
    Entidad("squid_settings", "app.models.squid_settings:SquidSetting", ("key",)),
    Entidad("acls", "app.models.acl:Acl", ("name",),
            excluir=frozenset({"content_hash", "line_count", "last_synced_at", "last_sync_status"})),
    Entidad("user_groups", "app.models.user_group:UserGroup", ("name",)),
    Entidad("access_rules", "app.models.access_rule:AccessRule", ordenar="order"),
    Entidad("proxy_users", "app.models.proxy_user:ProxyUser", ("username",),
            secretas=frozenset({"password_hash", "htpasswd_hash", "digest_ha1"})),
    Entidad("ldap_config", "app.models.ldap_config:LdapConfig", secretas=frozenset({"bind_password"})),
    Entidad("ldap_users", "app.models.ldap_user:LdapUser", ("username",)),
    Entidad("navigation_quotas", "app.models.navigation_quota:NavigationQuota", ("username",),
            excluir=frozenset({"quota_bytes_used", "quota_period_started_at", "quota_action_applied"})),
    Entidad("group_quotas", "app.models.group_quota:GroupQuota", ("group_name",),
            excluir=frozenset({"quota_bytes_used", "quota_period_started_at", "quota_action_applied"})),
    Entidad("delay_pools", "app.models.delay_pool:DelayPool",
            excluir=frozenset({"quota_id", "group_quota_id"}),
            filtro="(Modelo.quota_id.is_(None)) & (Modelo.group_quota_id.is_(None))"),
    Entidad("parent_proxy", "app.models.parent_proxy:ParentProxy", secretas=frozenset({"password"})),
    Entidad("kerberos_config", "app.models.kerberos_config:KerberosConfig",
            excluir=frozenset({"keytab_uploaded_at"}), secretas=frozenset({"keytab_data"})),
    Entidad("syslog_config", "app.models.syslog_config:SyslogConfig"),
    Entidad("smtp_config", "app.models.smtp_config:SmtpConfig", secretas=frozenset({"smtp_password"})),
    Entidad("notification_config", "app.models.notification_config:NotificationConfig",
            secretas=frozenset({"telegram_bot_token", "xmpp_password"})),
    Entidad("central_monitor_config", "app.models.central_config:CentralMonitorConfig",
            excluir=frozenset({"instance_id"})),
    Entidad("monitored_nodes", "app.models.monitored_node:MonitoredNode", ("name",),
            secretas=frozenset({"password"})),
    Entidad("ai_config", "app.models.ai_config:AiConfig", secretas=frozenset({"api_key", "embedding_api_key"})),
    Entidad("update_config", "app.models.update_config:UpdateConfig"),
]

NOMBRES_AMIGABLES = {
    "squid_settings": "Ajustes de Squid", "acls": "ACLs", "user_groups": "Grupos", "access_rules": "Reglas de acceso",
    "proxy_users": "Usuarios locales", "ldap_config": "Configuración LDAP", "ldap_users": "Usuarios LDAP",
    "navigation_quotas": "Cuotas de usuario", "group_quotas": "Cuotas de grupo", "delay_pools": "Reglas de ancho de banda",
    "parent_proxy": "Proxy padre", "kerberos_config": "Kerberos", "syslog_config": "Syslog externo", "smtp_config": "SMTP",
    "notification_config": "Notificaciones", "central_monitor_config": "Panel central (ajustes)",
    "monitored_nodes": "Panel central (nodos)", "ai_config": "Asistente de IA", "update_config": "Actualizaciones",
    "modulos": "Módulos",
}


class BackupError(Exception):
    """Error que se le explica al admin tal cual (archivo corrupto, contraseña incorrecta...)."""


# ---------------------------------------------------------------------------
# Serialización genérica de filas
# ---------------------------------------------------------------------------

def _modelo(ent: Entidad):
    import importlib

    modulo, _, clase = ent.modelo_path.partition(":")
    return getattr(importlib.import_module(modulo), clase)


def _columnas(modelo, ent: Entidad) -> list[str]:
    return [c.key for c in sa_inspect(modelo).columns if c.key not in _COMUNES and c.key not in ent.excluir]


def _a_json(valor):
    if isinstance(valor, datetime):
        return valor.isoformat()
    if isinstance(valor, (bytes, bytearray, memoryview)):
        return {"$b64": base64.b64encode(bytes(valor)).decode()}
    return valor


def _desde_json(columna, valor):
    if valor is None:
        return None
    if isinstance(valor, dict) and "$b64" in valor:
        return base64.b64decode(valor["$b64"])
    tipo = str(columna.type).upper()
    if "DATETIME" in tipo or "TIMESTAMP" in tipo:
        return datetime.fromisoformat(valor)
    return valor


def _clave_str(ent: Entidad, fila: dict) -> str:
    return "\x1f".join(str(fila.get(k)) for k in ent.clave) if ent.clave else "_"


def _consulta(db, ent: Entidad, modelo):
    q = db.query(modelo)
    if ent.filtro:
        q = q.filter(eval(ent.filtro, {"Modelo": modelo}))  # noqa: S307 - expresión fija de este módulo, no input
    if ent.ordenar:
        q = q.order_by(getattr(modelo, ent.ordenar), modelo.id)
    elif ent.clave:
        q = q.order_by(*[getattr(modelo, k) for k in ent.clave])
    else:
        q = q.order_by(modelo.id)
    return q


# ---------------------------------------------------------------------------
# Cifrado de secretos
# ---------------------------------------------------------------------------

_SCRYPT = {"n": 2 ** 15, "r": 8, "p": 1}


def _fernet(passphrase: str, sal: bytes, n: int, r: int, p: int):
    from cryptography.fernet import Fernet

    clave = hashlib.scrypt(passphrase.encode("utf-8"), salt=sal, n=n, r=r, p=p, maxmem=128 * 1024 * 1024, dklen=32)
    return Fernet(base64.urlsafe_b64encode(clave))


def cifrar_secretos(secretos: dict, passphrase: str) -> bytes:
    import os

    sal = os.urandom(16)
    token = _fernet(passphrase, sal, **_SCRYPT).encrypt(json.dumps(secretos, ensure_ascii=False).encode("utf-8"))
    return json.dumps({"kdf": "scrypt", **_SCRYPT, "salt": base64.b64encode(sal).decode(), "token": token.decode()}).encode("utf-8")


def descifrar_secretos(datos: bytes, passphrase: str) -> dict:
    from cryptography.fernet import InvalidToken

    try:
        env = json.loads(datos.decode("utf-8"))
        f = _fernet(passphrase, base64.b64decode(env["salt"]), int(env["n"]), int(env["r"]), int(env["p"]))
        return json.loads(f.decrypt(env["token"].encode()).decode("utf-8"))
    except InvalidToken:
        raise BackupError("La contraseña del backup no es correcta.")
    except (KeyError, ValueError) as e:
        raise BackupError(f"La parte cifrada del backup está dañada: {e}")


# ---------------------------------------------------------------------------
# Exportar
# ---------------------------------------------------------------------------

def _sha256(datos: bytes) -> str:
    return hashlib.sha256(datos).hexdigest()


def exportar(db, exportado_por: str, app_version: str, passphrase: str | None = None, incluir_listas: bool = True) -> bytes:
    """Arma el paquete `.smbackup` completo en memoria."""
    from app.services import modules_service

    config: dict = {}
    secretos: dict = {}
    conteos: dict[str, int] = {}

    for ent in ENTIDADES:
        modelo = _modelo(ent)
        cols = _columnas(modelo, ent)
        filas = []
        for obj in _consulta(db, ent, modelo).all():
            fila = {c: _a_json(getattr(obj, c)) for c in cols if c not in ent.secretas}
            sec = {c: _a_json(getattr(obj, c)) for c in cols if c in ent.secretas and getattr(obj, c) is not None}
            if ent.nombre == "user_groups":
                from app.models.user_group import UserGroupMember
                fila["members"] = [m.username for m in db.query(UserGroupMember)
                                   .filter(UserGroupMember.group_id == obj.id).order_by(UserGroupMember.username).all()]
            if ent.nombre == "acls" and obj.source == "file":
                fila["value"] = None
            filas.append(fila)
            if sec and passphrase:
                secretos.setdefault(ent.nombre, {})[_clave_str(ent, fila)] = sec
        if ent.clave or ent.nombre == "access_rules" or ent.nombre == "delay_pools":
            config[ent.nombre] = filas
        else:
            config[ent.nombre] = filas[0] if filas else None
        conteos[ent.nombre] = len(filas)

    config["modulos"] = modules_service.get_all(db)
    conteos["modulos"] = len(config["modulos"])

    partes: dict[str, bytes] = {"config.json": json.dumps(config, ensure_ascii=False, indent=1, sort_keys=True).encode("utf-8")}

    # Listas de dominios grandes (ACL de archivo) que no se vuelven a descargar solas.
    listas = []
    if incluir_listas:
        from app.models.acl import Acl
        from app.services.squid_service import ACL_LISTS_DIR

        for acl in db.query(Acl).filter(Acl.source == "file").all():
            if acl.sync_url:  # categorías con fuente propia: se vuelven a sincronizar
                continue
            ruta = ACL_LISTS_DIR / f"{acl.name}.txt"
            if ruta.exists():
                partes[f"acl_lists/{acl.name}.txt.gz"] = gzip.compress(ruta.read_bytes(), compresslevel=6)
                listas.append(acl.name)

    if passphrase and secretos:
        partes["secrets.enc"] = cifrar_secretos(secretos, passphrase)

    manifest = {
        "formato": FORMATO, "version_formato": VERSION_FORMATO, "app_version": app_version,
        "creado": datetime.utcnow().isoformat() + "Z", "creado_por": exportado_por,
        "contiene_secretos": bool(passphrase and secretos), "listas_incluidas": listas,
        "conteos": conteos, "sha256": {n: _sha256(d) for n, d in partes.items()},
    }

    salida = io.BytesIO()
    with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=1))
        for nombre, datos in partes.items():
            z.writestr(nombre, datos)
    return salida.getvalue()


# ---------------------------------------------------------------------------
# Leer y validar un paquete
# ---------------------------------------------------------------------------

@dataclass
class Paquete:
    manifest: dict
    config: dict
    secretos: dict | None
    listas: dict[str, bytes] = field(default_factory=dict)
    requiere_passphrase: bool = False


def leer_paquete(datos: bytes, passphrase: str | None = None) -> Paquete:
    if len(datos) > MAX_PAQUETE_BYTES:
        raise BackupError("El archivo es demasiado grande.")
    try:
        z = zipfile.ZipFile(io.BytesIO(datos))
    except zipfile.BadZipFile:
        raise BackupError("No es un backup de SquidManager válido (el archivo está dañado o no es un .smbackup).")

    def _leer(nombre: str) -> bytes:
        try:
            info = z.getinfo(nombre)
        except KeyError:
            raise BackupError(f"Al backup le falta «{nombre}».")
        if info.file_size > MAX_PARTE_BYTES:
            raise BackupError(f"«{nombre}» es demasiado grande.")
        return z.read(nombre)

    manifest = json.loads(_leer("manifest.json").decode("utf-8"))
    if manifest.get("formato") != FORMATO:
        raise BackupError("No es un backup de SquidManager.")
    if int(manifest.get("version_formato", 0)) > VERSION_FORMATO:
        raise BackupError(
            f"Este backup es de un formato más nuevo (v{manifest.get('version_formato')}) que el que entiende esta versión "
            f"({VERSION_FORMATO}). Actualiza este SquidManager antes de restaurarlo.")

    partes = {n: _leer(n) for n in manifest.get("sha256", {})}
    for nombre, esperado in manifest.get("sha256", {}).items():
        if _sha256(partes[nombre]) != esperado:
            raise BackupError(f"El backup está dañado: «{nombre}» no coincide con su firma.")

    config = json.loads(partes["config.json"].decode("utf-8"))
    secretos = None
    requiere = False
    if "secrets.enc" in partes:
        if not passphrase:
            requiere = True
        else:
            secretos = descifrar_secretos(partes["secrets.enc"], passphrase)
    listas = {n[len("acl_lists/"):-len(".txt.gz")]: partes[n] for n in partes if n.startswith("acl_lists/")}
    return Paquete(manifest, config, secretos, listas, requiere)


def inspeccionar(paquete: Paquete) -> dict:
    """Resumen de un paquete para mostrarlo antes de restaurar."""
    m = paquete.manifest
    return {
        "app_version": m.get("app_version"), "creado": m.get("creado"), "creado_por": m.get("creado_por"),
        "contiene_secretos": m.get("contiene_secretos"), "requiere_contrasena": paquete.requiere_passphrase,
        "conteos": {NOMBRES_AMIGABLES.get(k, k): v for k, v in (m.get("conteos") or {}).items() if v},
        "listas_incluidas": m.get("listas_incluidas", []),
    }


# ---------------------------------------------------------------------------
# Restaurar
# ---------------------------------------------------------------------------

_USERNAME = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def _validar_setting(clave: str, valor: str) -> str:
    """Mismas reglas que PUT /settings: un backup manipulado no puede colar una
    directiva arbitraria en squid.conf ni eximir de autenticarse a cualquiera."""
    from fastapi import HTTPException
    from app.services.auth_exempt_service import parsear_lista as p_exentos, validar_dominios
    from app.services.dns_service import parsear_lista as p_dns, validar_servidores
    from app.services.origenes_service import parsear_lista as p_orig, validar_origenes
    from app.services.squid_names import validate_value

    valor = valor or ""
    try:
        if clave == "dns_nameservers":
            ok, msg = validar_servidores(p_dns(valor))
            if not ok:
                raise BackupError(f"Ajuste «{clave}»: {msg}")
        elif clave == "trusted_sources":
            ok, msg = validar_origenes(p_orig(valor))
            if not ok:
                raise BackupError(f"Ajuste «{clave}»: {msg}")
        elif clave == "auth_exempt_domains":
            ok, msg = validar_dominios(p_exentos(valor))
            if not ok:
                raise BackupError(f"Ajuste «{clave}»: {msg}")
        elif clave in ("extra_safe_ports", "extra_ssl_ports"):
            for t in valor.split():
                if not re.fullmatch(r"\d{1,5}(-\d{1,5})?", t):
                    raise BackupError(f"Ajuste «{clave}»: «{t}» no es un puerto válido.")
        elif clave != "ssl_bump_exclude" and valor:
            valor = validate_value(valor, field=f"valor de «{clave}»")
    except HTTPException as e:
        raise BackupError(f"Ajuste «{clave}»: {e.detail}")
    return valor


def _validar_fila_unica(nombre: str, fila: dict, secretos: dict | None) -> None:
    """Mismas barreras que las rutas de cada configuración: lo que se restaura acaba en
    squid.conf, en ldap_helper.conf o en el script de Kerberos, así que un backup manipulado
    no puede colar saltos de línea ni caracteres que cambien el sentido de la directiva."""
    from fastapi import HTTPException
    from app.services.squid_names import validate_value

    valores = dict(fila)
    valores.update(secretos or {})
    try:
        # Solo las que acaban en una línea de un fichero de configuración; las de texto libre
        # (mensajes, prompts) y los certificados PEM llevan saltos de línea legítimos.
        if nombre in ("ldap_config", "parent_proxy", "kerberos_config", "syslog_config"):
            for clave, v in valores.items():
                if isinstance(v, str) and v and "cert" not in clave:
                    validate_value(v, field=f"«{clave}» de «{nombre}»")
        if nombre == "kerberos_config":
            from app.routes.kerberos import _validar_realm_fqdn
            _validar_realm_fqdn(valores.get("realm"), valores.get("proxy_fqdn"))
        elif nombre == "parent_proxy":
            for clave in ("host", "username", "password"):
                v = valores.get(clave)
                if isinstance(v, str) and re.search(r"\s", v.strip() if clave == "host" else v):
                    raise HTTPException(400, detail=f"«{clave}» del proxy padre no puede llevar espacios.")
    except HTTPException as e:
        raise BackupError(f"Configuración «{nombre}»: {e.detail}")


@dataclass
class Informe:
    simulacion: bool
    modo: str
    entidades: dict = field(default_factory=dict)   # nombre -> {crear, actualizar, eliminar}
    avisos: list = field(default_factory=list)
    usuarios_sin_contrasena: list = field(default_factory=list)

    def cuenta(self, ent: str, campo: str, n: int = 1):
        e = self.entidades.setdefault(ent, {"crear": 0, "actualizar": 0, "eliminar": 0})
        e[campo] += n

    def como_dict(self) -> dict:
        return {
            "simulacion": self.simulacion, "modo": self.modo,
            "entidades": [{"clave": k, "nombre": NOMBRES_AMIGABLES.get(k, k), **v}
                          for k, v in self.entidades.items() if any(v.values())],
            "avisos": self.avisos, "usuarios_sin_contrasena": self.usuarios_sin_contrasena,
        }


def _sincronizar_lista(db, ent: Entidad, filas_backup: list[dict], informe: Informe, modo: str, aplicar_fila):
    """Upsert por clave natural; en `reemplazar` elimina lo que el backup no trae."""
    modelo = _modelo(ent)
    existentes = {_clave_str(ent, {k: getattr(o, k) for k in ent.clave}): o for o in db.query(modelo).all()}
    vistas = set()
    for fila in filas_backup:
        k = _clave_str(ent, fila)
        vistas.add(k)
        obj = existentes.get(k)
        if obj is None:
            obj = modelo()
            db.add(obj)
            informe.cuenta(ent.nombre, "crear")
        else:
            informe.cuenta(ent.nombre, "actualizar")
        aplicar_fila(obj, fila, nuevo=k not in existentes)
    if modo == "reemplazar":
        for k, obj in existentes.items():
            if k not in vistas:
                db.delete(obj)
                informe.cuenta(ent.nombre, "eliminar")
    db.flush()


def _asignar(obj, modelo, ent: Entidad, fila: dict, secretos_fila: dict | None):
    cols = {c.key: c for c in sa_inspect(modelo).columns}
    for k, v in fila.items():
        if k in cols and k not in _COMUNES and k not in ent.excluir and k not in ent.secretas:
            setattr(obj, k, _desde_json(cols[k], v))
    if secretos_fila:
        for k, v in secretos_fila.items():
            if k in cols and k in ent.secretas:
                setattr(obj, k, _desde_json(cols[k], v))


def restaurar(db, paquete: Paquete, modo: str = "combinar", simular: bool = True) -> Informe:
    """Aplica el paquete dentro de una transacción. Con `simular` se ejecuta todo
    y se deshace al final (no se escribe ningún archivo)."""
    from app.models.access_rule import AccessRule
    from app.models.delay_pool import DelayPool
    from app.models.user_group import UserGroup, UserGroupMember
    from app.services import modules_service
    from app.services.squid_names import (
        known_acl_names, validate_acl_names, validate_acl_type, validate_name, validate_value,
    )

    if modo not in ("combinar", "reemplazar"):
        raise BackupError("Modo de restauración desconocido.")
    cfg, sec = paquete.config, (paquete.secretos or {})
    informe = Informe(simulacion=simular, modo=modo)
    por_nombre = {e.nombre: e for e in ENTIDADES}
    archivos_a_escribir: list[tuple] = []  # (nombre_acl, tipo, lista, descripcion, categoria)

    def secretos_de(ent: Entidad, fila: dict) -> dict | None:
        return (sec.get(ent.nombre) or {}).get(_clave_str(ent, fila))

    try:
        # 1) Ajustes
        ent = por_nombre["squid_settings"]
        filas = [dict(f, value=_validar_setting(f["key"], f.get("value"))) for f in cfg.get("squid_settings", [])]
        _sincronizar_lista(db, ent, filas, informe, modo,
                           lambda o, f, nuevo: _asignar(o, _modelo(ent), ent, f, None))

        # 2) ACLs (con el contenido de las listas de archivo)
        ent = por_nombre["acls"]
        filas = []
        for f in cfg.get("acls", []):
            f = dict(f)
            f["name"] = validate_name(f["name"], "ACL")
            f["type"] = validate_acl_type(f["type"])
            if f.get("source") == "file":
                f["value"] = None
            elif f.get("value"):
                f["value"] = validate_value(f["value"])
            filas.append(f)

        def aplicar_acl(obj, f, nuevo):
            _asignar(obj, _modelo(ent), ent, f, None)
            if f.get("source") == "file":
                obj.value = None
                blob = paquete.listas.get(f["name"])
                if blob is not None:
                    texto = _gunzip_acotado(blob).decode("utf-8", errors="replace")
                    lista = [l.strip() for l in texto.splitlines() if l.strip()]
                    from app.services.squid_service import hash_domain_list
                    obj.line_count = len(lista)
                    obj.content_hash = hash_domain_list(lista)
                    archivos_a_escribir.append((f["name"], f["type"], lista))
                elif not f.get("sync_url"):
                    informe.avisos.append(
                        f"La ACL «{f['name']}» es una lista de archivo y este backup no trae su contenido: "
                        "vuelve a cargarla con «Cargar dominios».")
        _sincronizar_lista(db, ent, filas, informe, modo, aplicar_acl)
        if any(f.get("sync_url") for f in filas):
            informe.avisos.append("Las categorías con fuente en línea (HaGeZi) se vuelven a descargar solas en unos minutos.")

        # 3) Grupos y miembros
        ent = por_nombre["user_groups"]
        filas = []
        for f in cfg.get("user_groups", []):
            f = dict(f)
            f["name"] = validate_name(f["name"], "grupo")
            filas.append(f)

        def aplicar_grupo(obj, f, nuevo):
            _asignar(obj, _modelo(ent), ent, f, None)
            db.flush()
            db.query(UserGroupMember).filter(UserGroupMember.group_id == obj.id).delete()
            for u in f.get("members", []):
                db.add(UserGroupMember(group_id=obj.id, username=u))
        _sincronizar_lista(db, ent, filas, informe, modo, aplicar_grupo)
        if modo == "reemplazar":
            db.flush()
            db.query(UserGroupMember).filter(~UserGroupMember.group_id.in_(db.query(UserGroup.id))).delete(synchronize_session=False)

        # 4) Reglas de acceso (orden importa: se reescriben enteras)
        db.flush()
        conocidos = known_acl_names(db)
        reglas = []
        for f in cfg.get("access_rules", []):
            reglas.append((f, validate_acl_names(f["acl_names"], conocidos)))
        from collections import Counter
        actuales = Counter((r.action, r.acl_names) for r in db.query(AccessRule).all())
        nuevas = Counter((f["action"], nombres) for f, nombres in reglas)
        if modo == "reemplazar":
            comunes = sum((actuales & nuevas).values())
            informe.cuenta("access_rules", "actualizar", comunes)
            informe.cuenta("access_rules", "crear", sum(nuevas.values()) - comunes)
            informe.cuenta("access_rules", "eliminar", sum(actuales.values()) - comunes)
            db.query(AccessRule).delete()
            base, ya = 0, set()
        else:
            base, ya = db.query(AccessRule).count(), set(actuales)
        orden = base
        for f, nombres in reglas:
            if (f["action"], nombres) in ya:
                if modo != "reemplazar":
                    informe.cuenta("access_rules", "actualizar")
                continue
            db.add(AccessRule(action=f["action"], acl_names=nombres, order=orden, description=f.get("description"),
                              enabled=f.get("enabled", True)))
            orden += 1
            if modo != "reemplazar":
                informe.cuenta("access_rules", "crear")
        if modo == "reemplazar":
            # ya = set() arriba: todas se reinsertan en el orden del backup
            pass

        # 5) Usuarios locales (con sus credenciales si el backup las trae)
        ent = por_nombre["proxy_users"]
        filas = cfg.get("proxy_users", [])
        for f in filas:
            if not _USERNAME.match(f["username"]):
                raise BackupError(f"Usuario no válido en el backup: «{f['username']}».")

        def aplicar_usuario(obj, f, nuevo):
            s = secretos_de(ent, f)
            _asignar(obj, _modelo(ent), ent, f, s)
            if nuevo and not s:
                from app.services.auth_service import get_password_hash
                import secrets as _s
                # Sin credenciales en el backup: un hash interno aleatorio (no sirve para entrar).
                obj.password_hash = get_password_hash(_s.token_urlsafe(24))
                informe.usuarios_sin_contrasena.append(f["username"])
        _sincronizar_lista(db, ent, filas, informe, modo, aplicar_usuario)
        if informe.usuarios_sin_contrasena:
            informe.avisos.append(
                f"{len(informe.usuarios_sin_contrasena)} usuario(s) se crearon SIN contraseña porque el backup no incluye credenciales: "
                "restablécelas en Usuarios. (Para conservarlas, crea el backup con una contraseña de protección.)")

        # 6) Resto de listas por clave natural
        for nombre in ("ldap_users", "navigation_quotas", "group_quotas", "monitored_nodes"):
            ent = por_nombre[nombre]
            _sincronizar_lista(db, ent, cfg.get(nombre, []), informe, modo,
                               lambda o, f, nuevo, ent=ent: _asignar(o, _modelo(ent), ent, f, secretos_de(ent, f)))

        # 7) Reglas de ancho de banda (lista sin clave natural)
        ent = por_nombre["delay_pools"]
        firma = lambda d: (d.get("description"), d.get("acl_names") or d.get("acl_name"), d.get("parameters"))  # noqa: E731
        q_dp = db.query(DelayPool).filter(DelayPool.quota_id.is_(None), DelayPool.group_quota_id.is_(None))
        actuales = Counter(firma({"description": p.description, "acl_names": p.acl_names, "acl_name": p.acl_name, "parameters": p.parameters}) for p in q_dp.all())
        nuevos = []
        for f in cfg.get("delay_pools", []):
            f = dict(f)
            f["parameters"] = validate_value(f["parameters"], field="parámetros del delay pool")
            nuevos.append(f)
        cuenta_nuevos = Counter(firma(f) for f in nuevos)
        if modo == "reemplazar":
            comunes = sum((actuales & cuenta_nuevos).values())
            informe.cuenta("delay_pools", "actualizar", comunes)
            informe.cuenta("delay_pools", "crear", len(nuevos) - comunes)
            informe.cuenta("delay_pools", "eliminar", sum(actuales.values()) - comunes)
            q_dp.delete()
            existentes = set()
        else:
            existentes = set(actuales)
        for f in nuevos:
            if firma(f) in existentes:
                if modo != "reemplazar":
                    informe.cuenta("delay_pools", "actualizar")
                continue
            obj = DelayPool()
            _asignar(obj, _modelo(ent), ent, f, None)
            db.add(obj)
            if modo != "reemplazar":
                informe.cuenta("delay_pools", "crear")

        # 8) Configuraciones de una sola fila
        for nombre in ("ldap_config", "parent_proxy", "kerberos_config", "syslog_config", "smtp_config",
                       "notification_config", "central_monitor_config", "ai_config", "update_config"):
            ent = por_nombre[nombre]
            fila = cfg.get(nombre)
            if not fila:
                continue
            _validar_fila_unica(nombre, fila, (sec.get(nombre) or {}).get("_"))
            modelo = _modelo(ent)
            obj = db.query(modelo).first()
            if obj is None:
                obj = modelo()
                db.add(obj)
                informe.cuenta(nombre, "crear")
            else:
                informe.cuenta(nombre, "actualizar")
            _asignar(obj, modelo, ent, fila, (sec.get(nombre) or {}).get("_"))
            if ent.secretas and not (sec.get(nombre) or {}).get("_") and paquete.manifest.get("contiene_secretos") is False:
                informe.avisos.append(f"«{NOMBRES_AMIGABLES[nombre]}»: el backup no trae sus credenciales; revísalas en su pantalla.")

        # 9) Módulos
        for clave, activo in (cfg.get("modulos") or {}).items():
            if clave in modules_service.MODULOS:
                modules_service.set_enabled(db, clave, bool(activo))
                informe.cuenta("modulos", "actualizar")

        db.flush()

        if simular:
            db.rollback()
            return informe

        # Solo con todo validado y aplicado en la transacción se escriben los archivos.
        for nombre, tipo, lista in archivos_a_escribir:
            _escribir_lista_acl(nombre, tipo, lista)
        db.commit()
        return informe
    except Exception:
        db.rollback()
        raise


def _escribir_lista_acl(nombre: str, tipo: str, lista: list[str]) -> None:
    """Escribe el archivo de una ACL de lista (mismo camino que la carga masiva)
    y, si es de dominios, la indexa para el helper de Squid."""
    from app.services.squid_service import write_acl_list_file

    content_hash, _ = write_acl_list_file(nombre, lista)
    if tipo == "dstdomain":
        from app.services import domain_index_service
        domain_index_service.index_category(nombre, lista, content_hash)
