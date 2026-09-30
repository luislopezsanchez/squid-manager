"""Importar un squid.conf de verdad (no escrito por SquidManager) al panel.

Un Squid administrado a mano varía mucho de una instalación a otra: separa
ACLs y reglas en archivos aparte con `include`, usa NTLM/AD, squidGuard,
proxy padres con opciones propias... No existe un parser que entienda
CUALQUIER squid.conf y lo traduzca perfecto -eso requeriría re-implementar
Squid entero-. Lo que sí se puede hacer, y es lo que hace este módulo, es:

  1. Tokenizar el archivo (o los archivos, resolviendo `include`) con la
     gramática real de Squid: comentarios, continuaciones de línea.
  2. Clasificar CADA directiva encontrada en tres cajones, explícitos:
     - importable: se traduce 1:1 al modelo de datos de SquidManager.
     - reconocida pero no soportada: se sabe qué hace, pero no tiene
       equivalente en el panel (NTLM, squidGuard, grupos externos de AD...).
       Se informa con una razón concreta, nunca se ignora en silencio.
     - desconocida: la directiva no está en ninguna tabla. Se informa como
       tal, sin inventar qué hace.
  3. Nada se escribe en la base de datos en el paso de análisis (dry-run).
     Solo `aplicar_importacion` -sobre un resultado ya analizado- escribe,
     y reutiliza los mismos validadores que ya usa el resto del panel
     (`squid_names.validate_*`), así que una ACL o regla mal formada no
     puede colarse por este camino aunque no lo haga por el de siempre.

No se manda nada a ningún servicio externo (ni IA en la nube ni telemetría):
un squid.conf real suele traer contraseñas (`cachemgr_passwd`, `cache_peer
... login=`) y la topología completa de la red interna del cliente. Todo el
análisis es local, determinista y da el mismo resultado en cada corrida con
el mismo archivo -algo que una traducción asistida por IA no puede
garantizar, y que para algo que decide quién entra a Internet importa.
"""

from __future__ import annotations

import re
import secrets
import time
from dataclasses import dataclass, field

from app.services import squid_import_extras as extras

from app.services.squid_names import (
    NAME_PATTERN,
    RESERVED_NAMES,
    validate_name,
    validate_acl_type,
    validate_value,
    validate_acl_names,
    known_acl_names,
    validar_lista_dominios,
)

# --- Tipos de ACL: qué se importa solo, qué necesita el camino ya soportado -

# Tipos cuyo valor es autocontenido (IPs, dominios, horarios, regex...): se
# puede recrear la ACL sin depender de nada más que lo que ya trae la línea.
IMPORTABLE_ACL_TYPES = {
    "src", "dst", "srcdomain", "dstdomain", "srcdom_regex", "dstdom_regex",
    "url_regex", "urlpath_regex", "port", "myport", "proto", "method",
    "browser", "referer_regex", "time", "maxconn", "max_user_ip",
    "req_mime_type", "rep_mime_type", "http_status", "snmp_community",
    "localport", "ssl::server_name", "ssl::server_name_regex", "arp",
    "ident",
}

# Tipos que SÍ reconoce Squid (y que el panel podría llegar a escribir a
# mano) pero que no se auto-importan: dependen de un camino propio del panel
# que hay que usar en su lugar, o de infraestructura externa que el import no
# puede reconstruir sin adivinar.
ACL_TYPES_NO_IMPORTABLES = {
    "proxy_auth": "usa Grupos de usuarios en el panel para esto, no una ACL suelta",
    "proxy_auth_regex": "usa Grupos de usuarios en el panel para esto, no una ACL suelta",
    "at_step": "es de uso interno de SSL Bump (step1/step2/step3); no se importa",
    "external": "depende de un helper externo (external_acl_type) que el import no reconstruye",
}

# Nombres de los DOS external_acl_type que declara este mismo panel para
# listas de dominios grandes (ver config_generator.py y
# domain_index_service.py): una ACL así ("acl nombre external
# squidmanager_domain_helper <categoria>") no es un helper externo genérico
# que el import no pueda entender -es EL PROPIO panel el que la generó-,
# así que se distingue con un mensaje específico (más abajo, en analizar())
# en vez del genérico de ACL_TYPES_NO_IMPORTABLES["external"]. Lo que sigue
# sin poder reconstruirse es el CONTENIDO de la lista (millones de
# dominios): eso vive en /etc/squid/acl_lists/<categoria>.txt, que este
# import -pensado para un squid.conf de texto, no para archivos de datos
# aparte- nunca recibe.
_HELPERS_PROPIOS_DE_DOMINIO = ("squidmanager_domain_helper", "squidmanager_domain_helper_sni")

# ACLs que ya define la propia plantilla de SquidManager. Importarlas
# duplicaría (o pisaría) una definición interna.
INTERNAL_ACLS = {
    "all", "localhost", "to_localhost", "SSL_ports", "Safe_ports", "CONNECT",
    "localnet", "authenticated", "step1", "step2", "step3", "manager",
    "ssl_exclude", "exentos_auth_dominio", "origenes_confianza",
}

# Reglas base que ya genera la plantilla: si el archivo importado las trae
# tal cual, no hace falta duplicarlas (no es que se "pierdan", ya existen).
REGLAS_BASE_REDUNDANTES = {
    "all", "!Safe_ports", "CONNECT !SSL_ports", "manager",
    "!authenticated", "authenticated", "localhost manager",
}

# --- Directivas sueltas que sí tienen un ajuste equivalente en el panel ----

# directiva squid.conf -> clave de SquidSetting. Los valores se copian tal
# cual: el admin los revisa en el informe antes de aplicar nada.
DIRECTIVA_A_SETTING = {
    "cache_mem": "cache_mem",
    "cache_dir": "cache_dir",
    "maximum_object_size": "maximum_object_size",
    # access_log y cache_store_log NO están acá a propósito: la plantilla de
    # SquidManager ya antepone el prefijo del módulo ("access_log
    # stdio:{{ ... }}"), así que copiar el valor original tal cual -que ya
    # suele traer su propio prefijo, "daemon:" o "stdio:", más el nombre del
    # formato de log al final- produce un "stdio:daemon:/ruta ... squid" que
    # Squid no sabe abrir. Verificado en vivo: rompió el arranque de Squid
    # en la primera prueba real de este importador. cache_log sí es seguro
    # (la plantilla no le añade ningún prefijo).
    "cache_log": "cache_log",
    "visible_hostname": "visible_hostname",
    "dns_nameservers": "dns_nameservers",
}

# --- Directivas reconocidas, sin equivalente en el panel -------------------
# Explicar el motivo real, no solo decir "no soportado".
DIRECTIVAS_NO_SOPORTADAS = {
    "auth_param": "el esquema de autenticación del proxy se elige en Configuración (basic/digest/none); NTLM, Negotiate y Kerberos vía winbind no tienen equivalente ahí -Kerberos/Negotiate contra Active Directory sí se soporta, pero se configura aparte, en Kerberos-",
    "external_acl_type": "grupos externos resueltos por un helper (AD/winbind, LDAP a medida) no tienen equivalente; usa Grupos de usuarios o LDAP en el panel",
    "url_rewrite_program": "un reescritor de URL externo (p. ej. squidGuard) no tiene equivalente en el panel",
    "url_rewrite_children": "depende de url_rewrite_program, ver arriba",
    "url_rewrite_bypass": "depende de url_rewrite_program, ver arriba",
    "cachemgr_passwd": "gestionado internamente por SquidManager; además es una contraseña en texto plano, no debería quedar en un archivo de configuración",
    "ftp_user": "no tiene equivalente en el panel",
    "debug_options": "no tiene equivalente en el panel",
    "coredump_dir": "gestionado internamente por SquidManager",
    "error_default_language": "usa el ajuste 'error_language' en Configuración",
    "cache_mgr": "no tiene equivalente en el panel",
    "http_port": "el puerto de escucha se cambia en Configuración; no se importa desde acá para no pisar el que ya está en uso",
    "https_port": "SquidManager no gestiona un https_port propio (usa SSL Bump sobre http_port)",
    "refresh_pattern": "hay un patrón de refresco en Configuración, pero admite solo uno; con varias líneas refresh_pattern no hay un mapeo 1:1 seguro -revísalo a mano",
    "access_log": "revísalo a mano en Configuración: el formato (módulo, ruta y tipo de log) no siempre se traduce 1:1 al que usa SquidManager",
    "cache_store_log": "revísalo a mano en Configuración, por el mismo motivo que access_log",
}


def _es_directiva_auth_param_basic(directiva: str, resto: str) -> tuple[str, str] | None:
    """`auth_param basic realm/children/credentialsttl` sí tienen equivalente
    (auth_realm/auth_children/credentialsttl), a diferencia del resto de
    auth_param. Devuelve (setting_key, valor) o None si no aplica."""
    m = re.match(r"^basic\s+realm\s+(.+)$", resto)
    if m:
        return "auth_realm", m.group(1).strip()
    m = re.match(r"^basic\s+children\s+(\d+)", resto)
    if m:
        return "auth_children", m.group(1).strip()
    m = re.match(r"^basic\s+credentialsttl\s+(.+)$", resto)
    if m:
        return "credentialsttl", m.group(1).strip()
    return None


# --- Tokenizado -------------------------------------------------------------

@dataclass
class Directiva:
    archivo: str
    linea: int
    nombre: str
    resto: str


def _lineas_logicas(nombre_archivo: str, texto: str) -> list[tuple[int, str]]:
    """Une continuaciones de línea (backslash final) y descarta comentarios
    y líneas en blanco. Devuelve (número de línea de inicio, contenido)."""
    lineas_crudas = texto.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    resultado: list[tuple[int, str]] = []
    buffer = ""
    inicio = 0
    for i, cruda in enumerate(lineas_crudas, start=1):
        # Un '#' es comentario salvo que venga escapado (\#), como hace Squid.
        sin_comentario = re.sub(r"(?<!\\)#.*$", "", cruda).replace("\\#", "#")
        sin_comentario = sin_comentario.rstrip()
        if not buffer:
            inicio = i
        if sin_comentario.endswith("\\"):
            buffer += sin_comentario[:-1] + " "
            continue
        buffer += sin_comentario
        contenido = re.sub(r"\s+", " ", buffer.strip())
        buffer = ""
        if contenido:
            resultado.append((inicio, contenido))
    return resultado


MAX_INCLUDES = 50  # cortafuegos ante un include circular o una cadena absurda


def _resolver_directivas(
    archivos: dict[str, str],
    nombre_archivo: str,
    vistos: set[str] | None = None,
) -> tuple[list[Directiva], list[str]]:
    """Aplana un archivo y sus `include` en una lista única de directivas.

    Los `include` del squid.conf original casi siempre usan rutas absolutas
    del servidor de origen (`/etc/squid/acl-pcs.conf`), que no existen acá:
    se resuelven por el NOMBRE DE ARCHIVO (basename) contra lo que el admin
    subió, no por la ruta completa.
    """
    vistos = vistos or set()
    faltantes: list[str] = []
    if nombre_archivo in vistos:
        return [], faltantes
    if len(vistos) >= MAX_INCLUDES:
        return [], faltantes
    vistos = vistos | {nombre_archivo}

    texto = archivos[nombre_archivo]
    directivas: list[Directiva] = []
    for lineno, contenido in _lineas_logicas(nombre_archivo, texto):
        partes = contenido.split(None, 1)
        nombre_directiva = partes[0]
        resto = partes[1].strip() if len(partes) > 1 else ""

        if nombre_directiva == "include":
            objetivo = resto.strip().strip('"')
            basename = objetivo.split("/")[-1].split("\\")[-1]
            candidato = next(
                (f for f in archivos if f.split("/")[-1].split("\\")[-1] == basename),
                None,
            )
            if candidato is None:
                faltantes.append(objetivo)
                continue
            sub_directivas, sub_faltantes = _resolver_directivas(archivos, candidato, vistos)
            directivas.extend(sub_directivas)
            faltantes.extend(sub_faltantes)
            continue

        directivas.append(Directiva(nombre_archivo, lineno, nombre_directiva, resto))

    return directivas, faltantes


# --- Resultado del análisis --------------------------------------------------

@dataclass
class ItemAcl:
    name: str
    type: str
    value: str
    estado: str  # "importar" | "ya_existe" | "no_soportado" | "invalida" | "alias"
    motivo: str = ""
    # Lista grande de dominios leída de un archivo: se carga como ACL de archivo.
    lista: list[str] | None = None
    origen: str = ""  # archivo(s) del que salió el valor


@dataclass
class ItemRegla:
    action: str
    acl_names: str
    estado: str  # "importar" | "no_importada"
    motivo: str = ""


@dataclass
class ItemSetting:
    key: str
    value: str
    estado: str = "importar"


@dataclass
class ItemDelayPool:
    pool_class: int
    parameters: str
    estado: str = "importar"


@dataclass
class ItemParentProxy:
    host: str
    port: int
    username: str | None
    password: str | None
    estado: str  # "importar" | "no_soportado"
    motivo: str = ""


@dataclass
class ItemUsuario:
    username: str
    estado: str  # "importar" | "ya_existe" | "sin_credencial"
    motivo: str = ""
    htpasswd_hash: str | None = None
    hash_formato: str = ""
    digest_ha1: str | None = None
    digest_realm: str | None = None
    habilitado: bool = True
    archivos: list = field(default_factory=list)


@dataclass
class Hallazgo:
    directiva: str
    archivo: str
    linea: int
    motivo: str


@dataclass
class ResultadoAnalisis:
    acls: list[ItemAcl] = field(default_factory=list)
    reglas: list[ItemRegla] = field(default_factory=list)
    settings: list[ItemSetting] = field(default_factory=list)
    delay_pools: list[ItemDelayPool] = field(default_factory=list)
    parent_proxy: ItemParentProxy | None = None
    usuarios: list[ItemUsuario] = field(default_factory=list)
    extra_safe_ports: list[str] = field(default_factory=list)
    extra_ssl_ports: list[str] = field(default_factory=list)
    never_direct: bool = False
    direct_domains: list[str] = field(default_factory=list)
    esquema_auth: str | None = None
    realm_auth: str | None = None
    archivos_usuarios: list[str] = field(default_factory=list)
    archivos_lista: list[str] = field(default_factory=list)
    notas: list[str] = field(default_factory=list)
    no_soportadas: list[Hallazgo] = field(default_factory=list)
    desconocidas: list[Hallazgo] = field(default_factory=list)
    includes_faltantes: list[str] = field(default_factory=list)

    def resumen(self) -> dict:
        return {
            "acls_a_importar": sum(1 for a in self.acls if a.estado == "importar"),
            "acls_ignoradas": sum(1 for a in self.acls if a.estado not in ("importar", "alias")),
            "acls_alias": sum(1 for a in self.acls if a.estado == "alias"),
            "usuarios_a_importar": sum(1 for u in self.usuarios if u.estado == "importar"),
            "usuarios_sin_credencial": sum(1 for u in self.usuarios if u.estado == "sin_credencial"),
            "usuarios_ya_existen": sum(1 for u in self.usuarios if u.estado == "ya_existe"),
            "puertos_extra": len(self.extra_safe_ports) + len(self.extra_ssl_ports),
            "reglas_a_importar": sum(1 for r in self.reglas if r.estado == "importar"),
            "reglas_ignoradas": sum(1 for r in self.reglas if r.estado != "importar"),
            "settings_a_importar": len(self.settings),
            "delay_pools_a_importar": len(self.delay_pools),
            "parent_proxy": self.parent_proxy.estado if self.parent_proxy else None,
            "directivas_no_soportadas": len(self.no_soportadas),
            "directivas_desconocidas": len(self.desconocidas),
            "includes_faltantes": len(self.includes_faltantes),
        }


ACL_RE = re.compile(r"^(\S+)\s+(\S+)\s+(.+)$")
RULE_ACTION_RE = re.compile(r"^(allow|deny)\s+(.+)$", re.IGNORECASE)
CACHE_PEER_RE = re.compile(
    r"^(\S+)\s+(parent|sibling)\s+(\d+)\s+(\d+)\s*(.*)$"
)
DELAY_CLASS_RE = re.compile(r"^(\d+)\s+(\d+)$")
DELAY_PARAMS_RE = re.compile(r"^(\d+)\s+(.+)$")


def analizar(
    archivos: dict[str, str],
    principal: str,
    acl_names_existentes: set[str],
    acl_names_conocidos: set[str],
    usuarios_existentes: set[str] | None = None,
    ldap_habilitado: bool = False,
) -> ResultadoAnalisis:
    """Analiza (sin escribir nada) uno o más archivos subidos.

    `principal`: nombre del archivo que se toma como punto de entrada (el
    squid.conf en sí); los demás se resuelven solo si algún `include` los
    referencia. `acl_names_existentes`: ACLs que YA hay en la BD (para no
    duplicar). `acl_names_conocidos`: superset que además incluye grupos de
    usuarios y los nombres internos -lo que ya devuelve `known_acl_names`-,
    usado para validar qué reglas son importables.
    """
    directivas, faltantes = _resolver_directivas(archivos, principal)
    resultado = ResultadoAnalisis(includes_faltantes=faltantes)

    acls_de_este_import: dict[str, ItemAcl] = {}
    delay_class: dict[int, int] = {}
    delay_params: dict[int, str] = {}
    # Archivos que acompañan al squid.conf (listas de ACL, usuarios...), por nombre.
    companeros = {extras.basename(n): t for n, t in archivos.items() if n != principal}
    aliases: dict[str, str] = {}          # ACL del origen -> ACL integrada equivalente
    usados_como_lista: set[str] = set()
    always_direct: list[tuple[str, str]] = []

    for d in directivas:
        if d.nombre == "acl":
            m = ACL_RE.match(d.resto)
            if not m:
                resultado.desconocidas.append(Hallazgo(
                    "acl", d.archivo, d.linea, "línea de ACL con formato irreconocible",
                ))
                continue
            name, acl_type, value = m.group(1), m.group(2), m.group(3).strip()

            if name in ("SSL_ports", "Safe_ports") and acl_type == "port":
                # La base del panel ya define estos dos nombres, pero quien migra suele
                # haberles sumado puertos propios (rsync, webmin...): sin ellos, el
                # tráfico que antes pasaba empieza a rechazarse.
                base = extras.BASE_SSL_PORTS if name == "SSL_ports" else extras.BASE_SAFE_PORTS
                destino = resultado.extra_ssl_ports if name == "SSL_ports" else resultado.extra_safe_ports
                for pto in extras.puertos_extra(value, base):
                    if pto not in destino:
                        destino.append(pto)
                continue

            if name in INTERNAL_ACLS or name.startswith("sni_"):
                continue  # ya la define la plantilla; no es un hallazgo, es lo esperado

            if acl_type == "proxy_auth" and value.strip().upper() == "REQUIRED":
                # «cualquier usuario autenticado» es la ACL integrada `authenticated`:
                # las reglas que la usaban se reescriben para apuntar a ella.
                aliases[name] = "authenticated"
                item = ItemAcl(name, acl_type, value, "alias",
                               "equivale a «authenticated» (cualquier usuario autenticado), que el panel ya trae: las reglas que la usaban se importan apuntando a esa")
                acls_de_este_import[name] = item
                resultado.acls.append(item)
                continue

            if name in acls_de_este_import:
                # Squid acumula valores de ACLs repetidas con el mismo nombre.
                previa = acls_de_este_import[name]
                if previa.type == acl_type and previa.estado == "importar":
                    previa.value = f"{previa.value} {value}".strip()
                continue

            if acl_type == "external" and value.split(" ", 1)[0] in _HELPERS_PROPIOS_DE_DOMINIO:
                # Es una lista de dominios del propio panel (ver el comentario
                # de _HELPERS_PROPIOS_DE_DOMINIO más arriba), no un helper
                # externo genérico: se sabe exactamente qué es, solo que su
                # contenido (potencialmente millones de dominios) no viaja
                # dentro de este squid.conf de texto.
                categoria = value.split(None, 1)[1] if len(value.split(None, 1)) > 1 else name
                item = ItemAcl(
                    name, acl_type, value, "no_soportado",
                    f"es una lista de dominios de SquidManager (categoría «{categoria}»); "
                    "su contenido no viaja en este archivo. Volvé a cargarla en «ACLs» > "
                    "«Cargar dominios» con el nombre "
                    f"«{name}» para recrearla.",
                )
            elif acl_type in ACL_TYPES_NO_IMPORTABLES:
                item = ItemAcl(name, acl_type, value, "no_soportado", ACL_TYPES_NO_IMPORTABLES[acl_type])
            elif acl_type not in IMPORTABLE_ACL_TYPES:
                item = ItemAcl(name, acl_type, value, "no_soportado", f"tipo de ACL '{acl_type}' no reconocido")
            elif not NAME_PATTERN.match(name) or name in RESERVED_NAMES:
                item = ItemAcl(name, acl_type, value, "invalida", "nombre no válido o reservado por Squid")
            elif name in acl_names_existentes:
                item = ItemAcl(name, acl_type, value, "ya_existe", "ya hay una ACL con ese nombre en SquidManager")
            else:
                rv = extras.resolver_valor_acl(acl_type, value, companeros)
                usados_como_lista.update(rv.archivos)
                origen = ", ".join(rv.archivos)
                for a_ in rv.archivos:
                    if a_ not in resultado.archivos_lista:
                        resultado.archivos_lista.append(a_)
                if rv.problema:
                    item = ItemAcl(name, acl_type, value, "no_soportado", rv.problema, origen=origen)
                elif rv.lista is not None:
                    validos, rechazados = validar_lista_dominios(rv.lista)
                    motivo = f"lista de {len(validos)} dominios leída de «{origen}»; se carga como ACL de archivo"
                    if rechazados:
                        motivo += f" ({len(rechazados)} líneas no válidas se omiten)"
                    item = ItemAcl(name, acl_type, f"({len(validos)} dominios)", "importar", motivo, lista=validos, origen=origen)
                else:
                    motivo = f"{rv.entradas} entradas leídas de «{origen}»" if origen else ""
                    item = ItemAcl(name, acl_type, rv.valor, "importar", motivo, origen=origen)

            acls_de_este_import[name] = item
            resultado.acls.append(item)
            continue

        if d.nombre == "http_access":
            m = RULE_ACTION_RE.match(d.resto)
            if not m:
                resultado.desconocidas.append(Hallazgo(
                    "http_access", d.archivo, d.linea, "línea de regla con formato irreconocible",
                ))
                continue
            action, acl_names = m.group(1).lower(), m.group(2).strip()
            if aliases:
                acl_names = " ".join(
                    ("!" if t.startswith("!") else "") + aliases.get(t.lstrip("!"), t.lstrip("!"))
                    for t in acl_names.split()
                )

            if acl_names in REGLAS_BASE_REDUNDANTES:
                continue  # ya la genera la plantilla; no hace falta duplicarla

            def _resoluble(nombre_bare: str) -> bool:
                if nombre_bare in acl_names_conocidos:
                    return True
                importada = acls_de_este_import.get(nombre_bare)
                return importada is not None and importada.estado == "importar"

            nombres = acl_names.split()
            desconocidos = [
                n.lstrip("!") for n in nombres if not _resoluble(n.lstrip("!"))
            ]
            if desconocidos:
                resultado.reglas.append(ItemRegla(
                    action, acl_names, "no_importada",
                    "referencia una ACL no soportada o inexistente: " + ", ".join(desconocidos),
                ))
            else:
                resultado.reglas.append(ItemRegla(action, acl_names, "importar"))
            continue

        if d.nombre == "delay_class":
            m = DELAY_CLASS_RE.match(d.resto)
            if m:
                delay_class[int(m.group(1))] = int(m.group(2))
            continue

        if d.nombre == "delay_parameters":
            m = DELAY_PARAMS_RE.match(d.resto)
            if m:
                delay_params[int(m.group(1))] = m.group(2).strip()
            continue

        if d.nombre == "cache_peer":
            m = CACHE_PEER_RE.match(d.resto)
            if not m or m.group(2) != "parent":
                resultado.no_soportadas.append(Hallazgo(
                    "cache_peer", d.archivo, d.linea,
                    "solo se importa un cache_peer de tipo 'parent' simple; revisa el proxy padre a mano",
                ))
                continue
            host, http_port, opciones = m.group(1), int(m.group(3)), m.group(5)
            login_m = re.search(r"login=(\S+)", opciones)
            username = password = None
            estado, motivo = "importar", ""
            if login_m:
                login_val = login_m.group(1)
                if login_val.upper() in ("PASSTHRU", "PASS", "NEGOTIATE"):
                    estado, motivo = "no_soportado", f"login={login_val} no se importa; configúralo a mano en Proxy padre"
                elif ":" in login_val:
                    username, password = login_val.split(":", 1)
                else:
                    estado, motivo = "no_soportado", f"opción login='{login_val}' no reconocida"
            resultado.parent_proxy = ItemParentProxy(host, http_port, username, password, estado, motivo)
            continue

        if d.nombre == "never_direct":
            if re.match(r"^allow\s+all$", d.resto, re.IGNORECASE):
                resultado.never_direct = True
            else:
                resultado.no_soportadas.append(Hallazgo(
                    "never_direct", d.archivo, d.linea,
                    "solo se importa «never_direct allow all» (todo por el proxy padre); una condición por ACL no tiene equivalente",
                ))
            continue

        if d.nombre == "always_direct":
            m = RULE_ACTION_RE.match(d.resto)
            if m:
                always_direct.append((m.group(1).lower(), m.group(2).strip()))
            continue

        if d.nombre in DIRECTIVA_A_SETTING:
            resultado.settings.append(ItemSetting(DIRECTIVA_A_SETTING[d.nombre], d.resto.strip()))
            continue

        if d.nombre == "external_acl_type" and d.resto.split(" ", 1)[0] in _HELPERS_PROPIOS_DE_DOMINIO:
            continue  # declaración propia del panel, ver _HELPERS_PROPIOS_DE_DOMINIO

        if d.nombre == "auth_param":
            mapeo = _es_directiva_auth_param_basic(d.nombre, d.resto)
            if mapeo:
                resultado.settings.append(ItemSetting(mapeo[0], mapeo[1]))
                continue
            m_realm = re.match(r"^digest\s+realm\s+(.+)$", d.resto)
            if m_realm:
                resultado.realm_auth = m_realm.group(1).strip()
                continue
            m_prog = re.match(r"^(basic|digest)\s+program\b", d.resto)
            if m_prog:
                # El esquema que declara el squid.conf (el primero, si hay varios).
                resultado.esquema_auth = resultado.esquema_auth or m_prog.group(1)
                continue
            m_ch = re.match(r"^digest\s+children\s+(\d+)", d.resto)
            if m_ch:
                resultado.settings.append(ItemSetting("auth_children", m_ch.group(1)))
                continue
            resultado.no_soportadas.append(Hallazgo(
                d.nombre, d.archivo, d.linea, DIRECTIVAS_NO_SOPORTADAS["auth_param"],
            ))
            continue

        if d.nombre in DIRECTIVAS_NO_SOPORTADAS:
            resultado.no_soportadas.append(Hallazgo(
                d.nombre, d.archivo, d.linea, DIRECTIVAS_NO_SOPORTADAS[d.nombre],
            ))
            continue

        if d.nombre in extras.DIRECTIVAS_SQUID_CONOCIDAS:
            resultado.no_soportadas.append(Hallazgo(
                d.nombre, d.archivo, d.linea,
                MOTIVOS_ESPECIFICOS.get(d.nombre, "es una directiva de Squid sin equivalente en el panel: no se conserva; "
                                                   "si la necesitas, revisa si el valor por defecto de Squid te sirve"),
            ))
            continue

        resultado.desconocidas.append(Hallazgo(d.nombre, d.archivo, d.linea, "no es una directiva de Squid que este importador conozca"))

    for pool_num, pool_class in delay_class.items():
        resultado.delay_pools.append(ItemDelayPool(pool_class, delay_params.get(pool_num, "")))

    _resolver_salida_directa(resultado, always_direct, acls_de_este_import, companeros)
    _resolver_usuarios(resultado, companeros, usados_como_lista, usuarios_existentes or set(), ldap_habilitado)
    _ajustes_derivados(resultado)
    return resultado


def _resolver_salida_directa(resultado, always_direct, acls_de_este_import, companeros) -> None:
    """`always_direct allow <ACL de dominios>` -> «Dominios que van directo» del
    proxy padre. Lo que no se puede expresar así (por IP, por protocolo, con
    deny) se informa."""
    for accion, nombres in always_direct:
        if accion != "allow":
            resultado.no_soportadas.append(Hallazgo(
                "always_direct", "", 0,
                f"«always_direct deny {nombres}» no tiene equivalente: el proxy padre solo admite una lista de dominios que van directo"))
            continue
        for nombre in nombres.split():
            item = acls_de_este_import.get(nombre.lstrip("!"))
            if nombre.startswith("!") or item is None or item.type not in extras.TIPOS_DOMINIO:
                tipo = f" ({item.type})" if item else ""
                resultado.no_soportadas.append(Hallazgo(
                    "always_direct", "", 0,
                    f"«always_direct allow {nombre}»{tipo}: solo se convierten las ACL de dominios de destino; esta condición no se conserva "
                    "(añade a mano las redes internas a «Dominios que van directo» del proxy padre si hace falta)"))
                continue
            dominios = item.lista if item.lista is not None else item.value.split()
            for dom in dominios:
                if dom not in resultado.direct_domains:
                    resultado.direct_domains.append(dom)


def _resolver_usuarios(resultado, companeros, usados_como_lista, existentes, ldap_habilitado) -> None:
    creds, archivos_usr, realms = extras.leer_usuarios(companeros, usados_como_lista)
    if not creds:
        return
    resultado.archivos_usuarios = archivos_usr
    realm = extras.elegir_realm(resultado.realm_auth, realms)
    descartadas = extras.fijar_realm(creds, realm)

    con_ha1 = sum(1 for c in creds.values() if c.digest_ha1)
    con_hash = sum(1 for c in creds.values() if c.htpasswd_hash)
    esquema = resultado.esquema_auth or ("digest" if con_ha1 > con_hash else "basic")
    if esquema == "digest" and ldap_habilitado:
        resultado.notas.append("Este SquidManager tiene LDAP activo y Digest solo autentica usuarios locales: se mantiene el esquema actual "
                               "y los usuarios se importan con su hash de Basic si lo tienen.")
        esquema = "basic"
    resultado.esquema_auth = esquema
    resultado.realm_auth = realm if esquema == "digest" else resultado.realm_auth
    if descartadas:
        resultado.notas.append(f"{descartadas} línea(s) de usuarios de otro realm de Digest se descartaron: la clave lleva el realm dentro y solo sirve con «{realm}».")

    for nombre in sorted(creds):
        c = creds[nombre]
        if nombre in existentes:
            resultado.usuarios.append(ItemUsuario(nombre, "ya_existe", "ya hay un usuario con ese nombre", archivos=c.archivos))
            continue
        tiene = bool(c.digest_ha1) if esquema == "digest" else bool(c.htpasswd_hash)
        base = dict(htpasswd_hash=c.htpasswd_hash, hash_formato=c.hash_formato, digest_ha1=c.digest_ha1,
                    digest_realm=c.digest_realm, archivos=c.archivos)
        if tiene:
            resultado.usuarios.append(ItemUsuario(nombre, "importar", **base))
        else:
            falta = "clave de Digest" if esquema == "digest" else "hash de Basic"
            resultado.usuarios.append(ItemUsuario(
                nombre, "sin_credencial",
                f"solo tiene {'contraseña de Basic' if esquema == 'digest' else 'clave de Digest'} y el esquema elegido ({esquema}) necesita su {falta}: "
                "se importa DESHABILITADO; restablece su contraseña para activarlo",
                habilitado=False, **base))


def _ajustes_derivados(resultado) -> None:
    """Ajustes que se deducen de lo leído (esquema, realm, puertos): se listan
    junto al resto para que el admin los vea antes de aplicar."""
    if resultado.esquema_auth and resultado.usuarios:
        resultado.settings.append(ItemSetting("proxy_auth_scheme", resultado.esquema_auth))
        if resultado.esquema_auth == "digest" and resultado.realm_auth:
            resultado.settings = [x for x in resultado.settings if x.key != "auth_realm"]
            resultado.settings.append(ItemSetting("auth_realm", resultado.realm_auth))
    if resultado.extra_safe_ports:
        resultado.settings.append(ItemSetting("extra_safe_ports", " ".join(resultado.extra_safe_ports)))
    if resultado.extra_ssl_ports:
        resultado.settings.append(ItemSetting("extra_ssl_ports", " ".join(resultado.extra_ssl_ports)))


# Motivos concretos para directivas conocidas que el panel no replica.
MOTIVOS_ESPECIFICOS = {
    "http_reply_access": "las reglas sobre la respuesta (http_reply_access) no existen en el panel; si solo era «allow all», ya es el comportamiento por defecto",
    "icp_access": "ICP/HTCP (cachés hermanas) no se usa en el panel; no se conserva",
    "cache_swap_low": "umbral de limpieza de la caché: Squid usa su valor por defecto (90)",
    "cache_swap_high": "umbral de limpieza de la caché: Squid usa su valor por defecto (95)",
    "logfile_rotate": "la rotación de logs la hace logrotate del sistema, no Squid",
    "half_closed_clients": "opción interna de conexiones: Squid usa su valor por defecto",
    "mail_from": "correo de los avisos de Squid: el panel envía sus avisos por Notificaciones/SMTP",
    "ftp_passive": "FTP a través del proxy no se gestiona desde el panel",
    "error_directory": "las páginas de error propias no se importan: el panel muestra las suyas en el idioma elegido",
    "delay_access": "se reconstruye a partir de delay_pools/delay_class/delay_parameters; revisa el «Aplica a» de cada regla en Ancho de banda",
    "cache_peer_access": "el acceso por ACL a cada proxy padre no tiene equivalente; el panel usa un solo padre para todo el tráfico (salvo los dominios directos)",
    "read_timeout": "tiempo de espera de lectura: Squid usa su valor por defecto",
    "connect_timeout": "tiempo de espera de conexión: Squid usa su valor por defecto",
}


# --- Cache en memoria del análisis, para no volver a subir los archivos ----
# entre 'analizar' y 'aplicar'. TTL corto: es solo el tiempo que tarda el
# admin en leer el informe y decidir. Igual que el resto del proyecto
# (rate limiter en middleware/__init__.py), sin depender de Redis.

_TTL_SEGUNDOS = 15 * 60
_analisis_pendientes: dict[str, tuple[float, ResultadoAnalisis]] = {}


def guardar_analisis(resultado: ResultadoAnalisis) -> str:
    _purgar_vencidos()
    token = secrets.token_urlsafe(24)
    _analisis_pendientes[token] = (time.time(), resultado)
    return token


def recuperar_analisis(token: str) -> ResultadoAnalisis | None:
    _purgar_vencidos()
    entrada = _analisis_pendientes.pop(token, None)
    return entrada[1] if entrada else None


def _purgar_vencidos() -> None:
    ahora = time.time()
    vencidos = [t for t, (creado, _) in _analisis_pendientes.items() if ahora - creado > _TTL_SEGUNDOS]
    for t in vencidos:
        _analisis_pendientes.pop(t, None)


# --- Aplicación: recién acá se escribe algo en la base de datos -------------

def aplicar(db, resultado: ResultadoAnalisis) -> dict:
    """Escribe en la BD lo que el análisis marcó como 'importar'.

    Reutiliza los mismos validadores que ya usa el resto del panel
    (`squid_names.validate_*`): una ACL o regla que pasó el análisis pero
    que -por lo que sea, otro import concurrente, un nombre límite- ya no es
    válida al momento de aplicar, se rechaza acá también, nunca se cuela.
    """
    from app.models.acl import Acl
    from app.models.access_rule import AccessRule
    from app.models.squid_settings import SquidSetting
    from app.models.delay_pool import DelayPool
    from app.models.parent_proxy import ParentProxy

    detalle = {"acls": 0, "reglas": 0, "settings": 0, "delay_pools": 0, "parent_proxy": False, "usuarios": 0, "avisos": []}

    for item in resultado.acls:
        if item.estado != "importar":
            continue
        nombre = validate_name(item.name, "ACL")
        tipo = validate_acl_type(item.type)
        if item.lista is not None:
            from app.services.squid_service import aplicar_lista_dominios
            aplicar_lista_dominios(
                db, nombre, tipo, item.lista, "reemplazar",
                description="Importado de squid.conf", is_category=False,
                admin_id=None, admin_username="Importación de squid.conf",
            )
        else:
            valor = validate_value(item.value)
            db.add(Acl(name=nombre, type=tipo, value=valor,
                        description="Importado de squid.conf", enabled=True))
        detalle["acls"] += 1

    db.flush()
    reglas_a_importar = [r for r in resultado.reglas if r.estado == "importar"]
    conocidos = known_acl_names(db) if reglas_a_importar else set()

    orden_base = db.query(AccessRule).count()
    for i, item in enumerate(reglas_a_importar):
        acl_names = validate_acl_names(item.acl_names, conocidos)
        db.add(AccessRule(
            action=item.action, acl_names=acl_names,
            order=orden_base + i, description="Importado de squid.conf", enabled=True,
        ))
        detalle["reglas"] += 1

    for item in resultado.settings:
        if item.key in ("extra_safe_ports", "extra_ssl_ports"):
            if not all(extras._PUERTO_RE.match(t) for t in item.value.split()):
                raise ValueError(f"Puertos no válidos en «{item.key}»: {item.value}")
        if item.key == "proxy_auth_scheme" and item.value not in ("basic", "digest", "none"):
            continue
        valor = validate_value(item.value, field=f"valor de «{item.key}»") if item.value else item.value
        existente = db.query(SquidSetting).filter(SquidSetting.key == item.key).first()
        if existente:
            existente.value = valor
        else:
            db.add(SquidSetting(key=item.key, value=valor, category="imported",
                                  description="Importado de squid.conf"))
        detalle["settings"] += 1

    for item in resultado.delay_pools:
        parametros = validate_value(item.parameters, field="parámetros del delay pool") if item.parameters else ""
        db.add(DelayPool(
            pool_class=item.pool_class, parameters=parametros, acl_name="",
            description="Importado de squid.conf", enabled=True,
        ))
        detalle["delay_pools"] += 1

    if resultado.parent_proxy and resultado.parent_proxy.estado == "importar":
        p = resultado.parent_proxy
        config = db.query(ParentProxy).first()
        if not config:
            config = ParentProxy()
            db.add(config)
        config.host = validate_value(p.host, field="host del proxy padre")
        config.port = p.port
        config.username = validate_value(p.username, field="usuario del proxy padre") if p.username else None
        config.password = p.password
        config.auth_method = "fixed"
        config.never_direct = bool(resultado.never_direct)
        if resultado.direct_domains:
            config.direct_domains = "\n".join(validate_value(x, field="dominio directo") for x in resultado.direct_domains)
        # Se importa DESACTIVADO a propósito: activar un proxy padre sin
        # probarlo primero puede cortar toda la salida a Internet. El admin
        # lo prueba (Proxy padre > Probar) y lo activa a mano.
        config.enabled = False
        detalle["parent_proxy"] = True
        detalle["avisos"].append(
            "El proxy padre se importó DESACTIVADO. Pruébalo en «Proxy padre» "
            "antes de activarlo: activarlo sin probar puede cortar toda la "
            "navegación."
        )

    detalle["usuarios"] = _aplicar_usuarios(db, resultado, detalle)

    if resultado.no_soportadas:
        detalle["avisos"].append(
            f"{len(resultado.no_soportadas)} directiva(s) reconocida(s) pero sin "
            "equivalente en el panel no se importaron. Revisa el informe."
        )
    if resultado.desconocidas:
        detalle["avisos"].append(
            f"{len(resultado.desconocidas)} directiva(s) no reconocida(s) no se "
            "importaron. Revisa el informe."
        )
    if resultado.includes_faltantes:
        detalle["avisos"].append(
            "Estos archivos incluidos con 'include' no se subieron, así que su "
            "contenido no se analizó: " + ", ".join(resultado.includes_faltantes)
        )

    return detalle


def _aplicar_usuarios(db, resultado, detalle) -> int:
    """Crea los usuarios leídos de los archivos htpasswd/htdigest con las
    credenciales que traían, para que sigan entrando con su contraseña de
    siempre. Nadie recibe una contraseña nueva ni se guarda ninguna en claro."""
    from app.models.proxy_user import ProxyUser
    from app.services.auth_service import get_password_hash
    from app.services.squid_service import realm_actual, write_digest_file, write_passwd_file
    import re as _re

    pendientes = [u for u in resultado.usuarios if u.estado in ("importar", "sin_credencial")]
    if not pendientes:
        return 0
    db.flush()
    realm = realm_actual(db)
    n = 0
    for u in pendientes:
        if not _re.match(r"^[A-Za-z0-9._-]{1,64}$", u.username):
            detalle["avisos"].append(f"El usuario «{u.username}» tiene caracteres no admitidos y no se importó.")
            continue
        if db.query(ProxyUser).filter(ProxyUser.username == u.username).first():
            continue
        usa_ha1 = bool(u.digest_ha1 and u.digest_realm)
        db.add(ProxyUser(
            username=u.username,
            # La contraseña real no se conoce (solo su hash): el hash interno del panel
            # es aleatorio y no sirve para entrar; la autenticación del proxy usa los
            # hashes importados.
            password_hash=get_password_hash(secrets.token_urlsafe(24)),
            htpasswd_hash=f"{u.username}:{u.htpasswd_hash}" if u.htpasswd_hash else None,
            digest_ha1=u.digest_ha1 if usa_ha1 else None,
            digest_ha1_realm=u.digest_realm if usa_ha1 else None,
            enabled=u.habilitado,
        ))
        n += 1
    db.flush()
    write_passwd_file(db)
    write_digest_file(db, realm)
    sin_cred = sum(1 for u in pendientes if u.estado == "sin_credencial")
    if sin_cred:
        detalle["avisos"].append(
            f"{sin_cred} usuario(s) se importaron DESHABILITADOS por no tener credencial para el esquema {resultado.esquema_auth}: "
            "restablece su contraseña en Usuarios para activarlos.")
    return n
