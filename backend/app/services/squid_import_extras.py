"""Piezas del importador de squid.conf que trabajan sobre los ARCHIVOS que
acompañan al squid.conf: listas de ACL, ficheros de usuarios y lo que se
deduce de ellos. Sin base de datos: todo son funciones puras sobre texto, para
poder probarlas con el squid.conf real de quien migra.

Un Squid administrado a mano casi nunca es un único archivo. Es el
squid.conf más ficheros de texto que este referencia con rutas absolutas del
servidor de origen (`acl moviles src "/etc/squid/ip_moviles"`), los ficheros de
usuarios (htpasswd / htdigest) y a veces scripts. El importador recibe todo lo
que el admin sube y resuelve las referencias por NOMBRE de archivo (basename),
nunca por ruta: `/etc/squid/x` no existe en este servidor.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Listas de ACL en archivo
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r'"[^"]*"|\'[^\']*\'|\S+')

# Tipos cuyo valor por línea es un patrón regex: una línea con espacios no se
# puede pegar en una sola línea de squid.conf sin partir el patrón.
TIPOS_REGEX = {"url_regex", "urlpath_regex", "dstdom_regex", "srcdom_regex", "referer_regex", "browser"}
TIPOS_DOMINIO = {"dstdomain", "srcdomain"}

MAX_ENTRADAS_INLINE = 300  # por encima, una ACL de dominios se carga como lista de archivo


def basename(ruta: str) -> str:
    return ruta.strip().strip('"').strip("'").replace("\\", "/").split("/")[-1]


def entradas_de_archivo(texto: str) -> list[str]:
    """Líneas útiles de un fichero de lista de Squid: sin comentarios (`#`,
    también al final de la línea) ni líneas en blanco."""
    salida = []
    for cruda in texto.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        linea = re.sub(r"(?<!\\)#.*$", "", cruda).strip()
        if linea:
            salida.append(linea)
    return salida


@dataclass
class ValorAcl:
    """Valor de una ACL ya resuelto. `valor` es la cadena inline (vacía si la
    lista es grande y va como `lista`); `problema` explica por qué no se pudo
    importar."""
    valor: str = ""
    lista: list[str] | None = None
    opciones: str = ""
    archivos: list[str] = field(default_factory=list)  # ficheros de los que salió
    problema: str = ""
    entradas: int = 0


def resolver_valor_acl(acl_type: str, valor_crudo: str, companeros: dict[str, str]) -> ValorAcl:
    """Convierte el valor de una línea `acl` en algo importable.

    Los tokens entre comillas son rutas de archivo: se buscan por nombre entre
    los archivos subidos y se sustituyen por su contenido. Las opciones de
    Squid (`-i`, `-n`...) delante de los valores se conservan tal cual.
    """
    tokens = _TOKEN_RE.findall(valor_crudo)
    opciones, valores, archivos = [], [], []
    for tk in tokens:
        if len(tk) >= 2 and tk[0] in "\"'" and tk[-1] == tk[0]:
            ruta = tk[1:-1]
            nombre = basename(ruta)
            texto = companeros.get(nombre)
            if texto is None:
                return ValorAcl(problema=f"la lista «{ruta}» no se subió junto con el squid.conf (súbela para importar esta ACL)",
                                archivos=[nombre])
            archivos.append(nombre)
            valores.extend(entradas_de_archivo(texto))
        elif tk.startswith("-") and not valores and len(tk) <= 3:
            opciones.append(tk)
        else:
            valores.append(tk)

    if not valores:
        return ValorAcl(problema="la ACL no tiene ningún valor", archivos=archivos)

    if acl_type in TIPOS_REGEX and any(re.search(r"\s", v) for v in valores):
        return ValorAcl(problema="un patrón regex contiene espacios y no se puede llevar a una sola línea de squid.conf sin partirlo; "
                                 "revisa esa lista a mano", archivos=archivos)

    if acl_type in TIPOS_DOMINIO and len(valores) > MAX_ENTRADAS_INLINE:
        return ValorAcl(lista=valores, opciones=" ".join(opciones), archivos=archivos, entradas=len(valores))
    return ValorAcl(valor=" ".join(opciones + valores), opciones=" ".join(opciones), archivos=archivos, entradas=len(valores))


# ---------------------------------------------------------------------------
# Puertos: SSL_ports / Safe_ports con puertos propios del admin
# ---------------------------------------------------------------------------

BASE_SAFE_PORTS = {"80", "443", "21", "70", "210", "1025-65535", "280", "488", "591", "777"}
BASE_SSL_PORTS = {"443"}
_PUERTO_RE = re.compile(r"^\d{1,5}(-\d{1,5})?$")


def _cubierto(puerto: str, base: set[str]) -> bool:
    """¿La base ya permite este puerto (o todo este rango)?"""
    if puerto in base:
        return True
    lo, _, hi = puerto.partition("-")
    desde, hasta = int(lo), int(hi or lo)
    for b in base:
        b_lo, _, b_hi = b.partition("-")
        if int(b_lo) <= desde and hasta <= int(b_hi or b_lo):
            return True
    return False


def puertos_extra(valor: str, base: set[str]) -> list[str]:
    """Puertos de una ACL Safe_ports/SSL_ports que la base del panel NO trae."""
    extra = []
    for tk in valor.split():
        if _PUERTO_RE.match(tk) and not _cubierto(tk, base) and tk not in extra:
            extra.append(tk)
    return extra


# ---------------------------------------------------------------------------
# Usuarios: htpasswd / htdigest
# ---------------------------------------------------------------------------

_USER = r"[A-Za-z0-9._@-]{1,64}"
_HTPASSWD_HASH = re.compile(
    r"^(\$2[aby]\$\d\d\$[./A-Za-z0-9]{53}|\$apr1\$[./0-9A-Za-z]{1,8}\$[./0-9A-Za-z]{22}|\{SHA\}[A-Za-z0-9+/]{27}=|"
    r"\$[156]\$[./0-9A-Za-z$]{6,}|[./0-9A-Za-z]{13})$"
)
_HTPASSWD_LINE = re.compile(rf"^({_USER}):(\S+)$")
_HTDIGEST_LINE = re.compile(rf"^({_USER}):([^:\s][^:]*):([0-9a-fA-F]{{32}})$")


@dataclass
class CredencialesUsuario:
    username: str
    htpasswd_hash: str | None = None       # hash de htpasswd tal cual (cualquier formato admitido)
    hash_formato: str = ""                 # 'bcrypt', 'apr1', 'sha1', 'crypt'
    digest_ha1: str | None = None
    digest_realm: str | None = None
    archivos: list[str] = field(default_factory=list)


def formato_hash(h: str) -> str:
    if h.startswith(("$2a$", "$2b$", "$2y$")):
        return "bcrypt"
    if h.startswith("$apr1$"):
        return "apr1"
    if h.startswith("{SHA}"):
        return "sha1"
    return "crypt"


def clasificar_linea_usuario(linea: str) -> tuple[str, tuple] | None:
    """('digest', (user, realm, ha1)) | ('htpasswd', (user, hash)) | None."""
    linea = linea.strip()
    m = _HTDIGEST_LINE.match(linea)
    if m:
        return "digest", (m.group(1), m.group(2), m.group(3).lower())
    m = _HTPASSWD_LINE.match(linea)
    if m and _HTPASSWD_HASH.match(m.group(2)):
        return "htpasswd", (m.group(1), m.group(2))
    return None


def es_archivo_de_usuarios(texto: str) -> bool:
    """Un archivo cuenta como lista de usuarios si al menos 80 % de sus líneas
    útiles son líneas de htpasswd o htdigest (y hay alguna): así se distingue de
    una lista de IPs, de dominios o de un script."""
    lineas = entradas_de_archivo(texto)
    if not lineas:
        return False
    buenas = sum(1 for l in lineas if clasificar_linea_usuario(l))
    return buenas >= 1 and buenas / len(lineas) >= 0.8


def leer_usuarios(companeros: dict[str, str], excluir: set[str]) -> tuple[dict[str, CredencialesUsuario], list[str], dict[str, int]]:
    """Recorre los archivos subidos (menos los ya usados como lista de ACL) y
    junta las credenciales por usuario. Devuelve (usuarios, archivos_de_usuarios,
    conteo_de_realms)."""
    usuarios: dict[str, CredencialesUsuario] = {}
    archivos_usuarios: list[str] = []
    realms: dict[str, int] = {}
    for nombre, texto in companeros.items():
        if nombre in excluir or not es_archivo_de_usuarios(texto):
            continue
        archivos_usuarios.append(nombre)
        for linea in entradas_de_archivo(texto):
            c = clasificar_linea_usuario(linea)
            if not c:
                continue
            tipo, datos = c
            u = usuarios.setdefault(datos[0], CredencialesUsuario(datos[0]))
            if nombre not in u.archivos:
                u.archivos.append(nombre)
            if tipo == "digest":
                realm = datos[1]
                realms[realm] = realms.get(realm, 0) + 1
                # Un mismo usuario puede tener varias líneas de realms distintos: se
                # guarda una por realm; el que se use lo decide la directiva
                # `auth_param digest realm` (ver elegir_realm).
                u.__dict__.setdefault("_digests", {})[realm] = datos[2]
            else:
                u.htpasswd_hash = datos[1]
                u.hash_formato = formato_hash(datos[1])
    return usuarios, archivos_usuarios, realms


def elegir_realm(realm_configurado: str | None, realms: dict[str, int]) -> str | None:
    """El realm de digest a usar: el que declara el squid.conf; si no lo dice,
    el que más líneas tenga."""
    if realm_configurado:
        return realm_configurado
    if realms:
        return max(realms.items(), key=lambda kv: kv[1])[0]
    return None


def fijar_realm(usuarios: dict[str, CredencialesUsuario], realm: str | None) -> int:
    """Deja en cada usuario la HA1 del realm elegido. Devuelve cuántas líneas de
    OTROS realms se descartaron (no sirven con el realm activo: la HA1 lleva el
    realm dentro)."""
    descartadas = 0
    for u in usuarios.values():
        digests = u.__dict__.pop("_digests", {})
        if realm and realm in digests:
            u.digest_ha1, u.digest_realm = digests[realm], realm
            descartadas += len(digests) - 1
        else:
            descartadas += len(digests)
    return descartadas


# ---------------------------------------------------------------------------
# Directivas de Squid conocidas (para distinguir «no tiene equivalente» de
# «no existe»)
# ---------------------------------------------------------------------------

DIRECTIVAS_SQUID_CONOCIDAS = {
    "acl", "http_access", "http_reply_access", "icp_access", "htcp_access", "htcp_clr_access",
    "miss_access", "ident_lookup_access", "reply_body_max_size", "delay_pools", "delay_class",
    "delay_parameters", "delay_access", "client_delay_pools", "client_delay_parameters",
    "client_delay_access", "cache_peer", "cache_peer_access", "cache_peer_domain", "neighbor_type_domain",
    "dead_peer_timeout", "forward_max_tries", "forward_timeout", "connect_timeout", "peer_connect_timeout",
    "read_timeout", "request_timeout", "persistent_request_timeout", "client_lifetime", "half_closed_clients",
    "pconn_timeout", "ident_timeout", "shutdown_lifetime", "always_direct", "never_direct", "prefer_direct",
    "nonhierarchical_direct", "hierarchy_stoplist", "cache", "no_cache", "cache_mem", "cache_dir",
    "cache_swap_low", "cache_swap_high", "maximum_object_size", "minimum_object_size",
    "maximum_object_size_in_memory", "memory_cache_mode", "memory_replacement_policy", "cache_replacement_policy",
    "max_open_disk_fds", "minimum_direct_hops", "minimum_direct_rtt", "store_dir_select_algorithm",
    "cache_effective_user", "cache_effective_group", "cache_log", "cache_store_log", "access_log",
    "logfile_rotate", "logfile_daemon", "log_mime_hdrs", "log_fqdn", "logformat", "strip_query_terms",
    "buffered_logs", "netdb_filename", "pid_filename", "coredump_dir", "mime_table", "icon_directory",
    "error_directory", "error_default_language", "error_log_languages", "err_html_text", "email_err_data",
    "deny_info", "ftp_user", "ftp_passive", "ftp_sanitycheck", "ftp_epsv", "ftp_epsv_all", "ftp_list_width",
    "ftp_telnet_protocol", "cache_mgr", "mail_from", "mail_program", "visible_hostname", "unique_hostname",
    "hostname_aliases", "append_domain", "dns_nameservers", "dns_timeout", "dns_retransmit_interval",
    "dns_v4_first", "ignore_unknown_nameservers", "positive_dns_ttl", "negative_dns_ttl", "hosts_file",
    "ipcache_size", "ipcache_low", "ipcache_high", "fqdncache_size", "cachemgr_passwd", "refresh_pattern",
    "quick_abort_min", "quick_abort_max", "quick_abort_pct", "read_ahead_gap", "negative_ttl", "range_offset_limit",
    "collapsed_forwarding", "offline_mode", "uri_whitespace", "http_port", "https_port", "ftp_port", "icp_port",
    "htcp_port", "udp_incoming_address", "udp_outgoing_address", "tcp_outgoing_address", "tcp_outgoing_tos",
    "tcp_outgoing_mark", "tcp_outgoing_dscp", "qos_flows", "sslproxy_cert_error", "sslproxy_flags",
    "sslproxy_options", "sslproxy_cafile", "sslproxy_capath", "sslproxy_session_cache_size", "ssl_bump",
    "sslcrtd_program", "sslcrtd_children", "sslcrtd_program", "ssl_unclean_shutdown", "tls_outgoing_options",
    "auth_param", "authenticate_cache_garbage_interval", "authenticate_ttl", "authenticate_ip_ttl",
    "external_acl_type", "url_rewrite_program", "url_rewrite_children", "url_rewrite_concurrency",
    "url_rewrite_host_header", "url_rewrite_access", "url_rewrite_bypass", "store_id_program",
    "store_id_children", "store_id_access", "store_id_bypass", "redirector_bypass", "redirect_children",
    "request_header_access", "reply_header_access", "request_header_replace", "reply_header_replace",
    "request_header_add", "reply_header_add", "via", "forwarded_for", "follow_x_forwarded_for",
    "acl_uses_indirect_client", "delay_pool_uses_indirect_client", "log_uses_indirect_client",
    "tproxy_uses_indirect_client", "max_filedescriptors", "workers", "cpu_affinity_map", "snmp_port",
    "snmp_access", "snmp_incoming_address", "snmp_outgoing_address", "wccp_router", "wccp2_router",
    "wccp2_version", "wccp2_service", "wccp2_forwarding_method", "wccp2_return_method", "wccp2_assignment_method",
    "wccp2_service_info", "wccp2_weight", "wccp2_rebuild_wait", "wccp_version", "icp_query_timeout",
    "maximum_icp_query_timeout", "minimum_icp_query_timeout", "background_ping_rate", "mcast_groups",
    "mcast_miss_addr", "mcast_miss_ttl", "mcast_miss_port", "mcast_miss_encode_key", "mcast_icp_query_timeout",
    "test_reachability", "client_persistent_connections", "server_persistent_connections",
    "detect_broken_pconn", "pipeline_prefetch", "cache_miss_revalidate", "check_hostnames", "allow_underscore",
    "httpd_suppress_version_string", "short_icon_urls", "reload_into_ims", "maximum_single_addr_tries",
    "retry_on_error", "request_body_max_size", "client_request_buffer_max_size", "chunked_request_body_max_size",
    "as_whois_server", "icap_enable", "icap_service", "icap_class", "icap_access", "adaptation_access",
    "adaptation_service_set", "adaptation_service_chain", "ecap_service", "loadable_modules", "high_response_time_warning",
    "high_page_fault_warning", "high_memory_warning", "sleep_after_fork", "max_stale", "dns_defnames",
    "relaxed_header_parser", "digest_generation", "digest_bits_per_entry", "digest_rebuild_period",
    "digest_rewrite_period", "digest_swapout_chunk_size", "digest_rebuild_chunk_percentage", "ie_refresh",
    "vary_ignore_expire", "cachemgr_passwd", "umask", "include", "memory_pools", "memory_pools_limit",
    "forward_log", "emulate_httpd_log", "debug_options", "syslog_facility", "syslog_priority", "logfile_daemon",
    "host_verify_strict", "client_dst_passthru", "on_unsupported_protocol", "shared_transient_entries_limit",
}
