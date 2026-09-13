"""Servicio para controlar Squid y generar sus archivos auxiliares.

Todo lo que depende de COMO este desplegado Squid (contenedor o instalacion del
sistema) vive detras de `app.services.runtime`. Aqui solo queda lo que es igual
en los dos casos: generar la configuracion, validarla antes de escribirla y
mantener los ficheros de usuarios y de LDAP.
"""

import logging
import os
import threading
from pathlib import Path

from app.config import settings
from app.services.runtime import get_runtime

# Se reexportan para no romper a quien ya los importaba de aqui. Su
# implementacion es especifica de Docker y vive con el resto de ese modo.
from app.services.runtime.docker_runtime import (  # noqa: F401
    project_dir as _project_dir,
    sync_env_port,
)
from app.utils import utcnow

logger = logging.getLogger(__name__)

PASSWD_PATH = Path("/etc/squid/squid_passwd")
DIGEST_PATH = Path("/etc/squid/squid_digest")
LDAP_CONF_PATH = Path("/etc/squid/ldap_helper.conf")
LDAP_ALLOWLIST_PATH = Path("/etc/squid/ldap_allowlist")
# ACLs de dominio respaldadas por archivo (Acl.source == 'file'): una por
# cada una, nombrada por el nombre de la ACL -no hay nada secreto en una
# lista de dominios, pero el archivo solo lo escribe este backend.
ACL_LISTS_DIR = Path("/etc/squid/acl_lists")

# uid/gid del usuario 'proxy'. En la imagen del proyecto y en una Debian recien
# instalada son 13:13, pero no se pueden dar por sentados: si el usuario no
# existia al instalar el paquete de Squid, se crea con el primer id libre. Se
# resuelven del sistema y los valores de abajo son solo el ultimo recurso.
PROXY_UID = 13
PROXY_GID = 13


def _proxy_ids() -> tuple[int, int]:
    """uid/gid reales del usuario con el que corre Squid."""
    try:
        import pwd

        entrada = pwd.getpwnam("proxy")
        return entrada.pw_uid, entrada.pw_gid
    except Exception:
        return PROXY_UID, PROXY_GID


def _write_private(path: Path, content: str) -> None:
    """Escribe un fichero con secretos: legible solo por Squid y por el panel.

    Estos ficheros contienen la contraseña de bind de LDAP y los hashes de los
    usuarios del proxy. Con los permisos por defecto (644) los lee cualquier
    proceso de la máquina. Ver `_write_atomic` para el resto (el porqué del
    rename atómico, en vez de truncar in situ, está documentado ahí).
    """
    _write_atomic(path, content, mode=0o640)


def _write_atomic(path: Path, content: str, mode: int) -> None:
    """Escribe un fichero legible por Squid, con el modo que pida quien llama.

    El modo es 640 (grupo `proxy`) para secretos, o 644 para algo público
    como una lista de dominios -no hay nada que ocultar ahí, pero conviene
    que solo el backend pueda escribirlo-. Los dos casos llegan al mismo
    sitio por caminos distintos:

    - En contenedor el backend corre como `squidmgr`, cuyo grupo primario es
      `proxy` (mismo gid que usa Squid en su propia imagen): no hace falta
      chown, el fichero ya nace con el grupo correcto.
    - En instalación nativa pasa exactamente lo mismo: el backend corre con
      su propio usuario, cuyo grupo primario también es `proxy`.

    En los dos casos el conjunto de quien puede leerlo es el mismo: root, el
    panel y Squid.

    Se escribe a un temporal en el mismo directorio y se reemplaza con
    `os.replace` (rename atómico), en vez de truncar el fichero existente in
    situ. No es solo estilo: un `O_TRUNC` sobre el fichero existente exige
    permiso de ESCRITURA sobre ese inodo concreto, y el contenedor de Squid
    (que corre con su propio usuario `proxy` del sistema, no con el
    `squidmgr` de este backend) puede haber creado ese mismo fichero antes
    -vacío, con el modo restrictivo 600- al arrancar sin encontrar aún los
    ficheros de autenticación. Un rename solo necesita permiso de escritura
    sobre el DIRECTORIO, que el backend sí tiene siempre sobre /etc/squid.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    # Crear con los permisos definitivos, no escribir y luego ajustar.
    fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
        os.chmod(tmp_path, mode)

        # Solo root puede reasignar propietario. Intentarlo sin serlo falla
        # siempre y llenaría el log de avisos en cada aplicación de la
        # configuración. Sin root, el fichero ya nace con el grupo `proxy`
        # porque es el grupo primario del usuario que corre este proceso
        # (squidmgr en contenedor, el usuario nativo fuera de él) -no hace
        # falta chown para que Squid pueda leerlo por grupo.
        if getattr(os, "geteuid", lambda: 1)() == 0:
            uid, gid = _proxy_ids()
            try:
                os.chown(tmp_path, uid, gid)
            except (PermissionError, OSError) as e:
                logger.warning(f"No se pudo cambiar el propietario de {tmp_path}: {e}")
        os.replace(tmp_path, path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


def active_proxy_users(db):
    """Usuarios del proxy que deben poder autenticarse ahora mismo.

    Filtra por habilitado y por fecha de caducidad: sin esta comprobación el
    campo `expires_at` se guardaba pero no surtía efecto nunca.
    """
    from app.models.proxy_user import ProxyUser
    from sqlalchemy import or_

    now = utcnow()
    return (
        db.query(ProxyUser)
        .filter(ProxyUser.enabled == True)  # noqa: E712
        .filter(or_(ProxyUser.expires_at.is_(None), ProxyUser.expires_at > now))
        .all()
    )


def write_passwd_file(db) -> int:
    """Regenera /etc/squid/squid_passwd a partir de la base de datos.

    Devuelve el número de usuarios escritos.
    """
    users = active_proxy_users(db)
    lines = [u.htpasswd_hash for u in users if u.htpasswd_hash]
    _write_private(PASSWD_PATH, "\n".join(lines) + ("\n" if lines else ""))
    logger.info(f"Archivo passwd regenerado con {len(lines)} usuarios activos")
    return len(lines)


# Mismo valor por defecto que config_generator.py:
# settings.get('auth_realm', 'SquidManager Proxy'). Si uno de los dos cambia
# sin el otro, el HA1 de cada usuario no coincidiría con el realm que Squid
# declara de verdad en auth_param digest realm.
REALM_POR_DEFECTO = "SquidManager Proxy"


def realm_actual(db) -> str:
    """El realm vigente, para regenerar squid_digest con el mismo valor que
    Squid usará al validar (ver digest_ha1_realm en el modelo ProxyUser)."""
    from app.models.squid_settings import SquidSetting

    ajuste = db.query(SquidSetting).filter(SquidSetting.key == "auth_realm").first()
    return ajuste.value if ajuste and ajuste.value else REALM_POR_DEFECTO


def write_digest_file(db, realm: str) -> int:
    """Regenera /etc/squid/squid_digest ('usuario:realm:HA1' por línea).

    Se regenera SIEMPRE junto al htpasswd, esté Digest activo o no: así,
    activar Digest desde Configuración no exige que cada usuario reingrese su
    contraseña -el HA1 ya está calculado desde que se creó/reseteó el
    usuario. Si el realm guardado en cada fila no coincide con el `realm`
    vigente (se cambió auth_realm después de calcularlo), esa línea se omite:
    un HA1 con el realm viejo no sirve para nada y solo confundiría un
    `grep` manual del archivo.
    """
    users = active_proxy_users(db)
    lines = [
        f"{u.username}:{realm}:{u.digest_ha1}"
        for u in users
        if u.digest_ha1 and u.digest_ha1_realm == realm
    ]
    _write_private(DIGEST_PATH, "\n".join(lines) + ("\n" if lines else ""))
    logger.info(f"Archivo digest regenerado con {len(lines)} usuarios activos")
    return len(lines)


def hash_domain_list(dominios: list[str]) -> str:
    """sha256 de una lista de dominios ya normalizada (una línea por
    dominio, sin vacías), en el mismo formato exacto con el que
    write_acl_list_file() escribe el archivo. Pública para que
    acls.bulk_domains pueda calcular el hash de una carga ANTES de decidir
    si hace falta reescribir el archivo -re-subir exactamente la misma
    blocklist (por ejemplo, una sincronización diaria contra un proveedor
    externo que no cambió nada) no debería volver a escribir cientos de MB
    en disco ni marcar la configuración como pendiente de aplicar."""
    import hashlib

    h = hashlib.sha256()
    for linea in dominios:
        h.update(linea.encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def write_acl_list_file(name: str, dominios: list[str]) -> tuple[str, int]:
    """Escribe (o reemplaza) el archivo de una ACL 'file' con esta lista de
    dominios, uno por línea. Único punto que escribe estos archivos -lo usan
    tanto la carga masiva (acls.bulk_domains, al recibir un archivo nuevo)
    como build_acl_list_files (al migrar una ACL vieja que todavía tiene el
    contenido en `Acl.value`)-, para que el hash que se guarda en la BD
    siempre se calcule sobre exactamente lo mismo que se escribió.

    Devuelve (content_hash, line_count) para guardar en la fila de la ACL.
    """
    ACL_LISTS_DIR.mkdir(parents=True, exist_ok=True)
    contenido = "\n".join(dominios) + ("\n" if dominios else "")
    _write_atomic(ACL_LISTS_DIR / f"{name}.txt", contenido, mode=0o644)
    return hash_domain_list(dominios), len(dominios)


def build_acl_list_files(db) -> int:
    """Sincroniza /etc/squid/acl_lists/ con las ACLs 'file' de la BD, y
    borra los archivos que ya no correspondan a ninguna.

    Desde la migración 0023, el archivo es la fuente de verdad de una ACL
    'file': esta función YA NO reescribe nada en el caso normal, solo lo
    hace cuando hace falta:

    - `Acl.value` todavía tiene contenido (ACL creada antes de 0023, sin
      migrar todavía): se escribe el archivo por primera vez con ese
      contenido, se guarda su hash/conteo, y se limpia `value` -a partir de
      ahí esa ACL ya quedó en el camino nuevo, para siempre.
    - El archivo esperado no existe (se borró a mano, o es una instalación
      restaurada sin sus archivos): se recrea igual que antes, si hay
      contenido en `value`; si no lo hay tampoco (backup restaurado sin el
      archivo), se registra un aviso y esa ACL queda sin lista hasta que se
      vuelva a cargar -mejor que journal vacío en silencio.
    - Todo lo demás (el caso normal, apply tras apply, sin cambios en la
      lista) no toca el disco para nada: ni lee ni escribe el archivo, solo
      compara metadatos ya en memoria.
    """
    from app.models.acl import Acl

    ACL_LISTS_DIR.mkdir(parents=True, exist_ok=True)
    acls_de_archivo = db.query(Acl).filter(Acl.source == "file").all()

    esperados = set()
    migradas = 0
    for acl in acls_de_archivo:
        nombre_archivo = f"{acl.name}.txt"
        esperados.add(nombre_archivo)
        ruta = ACL_LISTS_DIR / nombre_archivo

        if acl.value is not None:
            # Todavía sin migrar (venía de antes de 0023), o se le volvió a
            # asignar `value` a mano por algún camino viejo: el contenido de
            # la BD manda, se escribe y se limpia `value` para no volver a
            # pasar por aquí la próxima vez.
            dominios = [d.strip() for d in acl.value.splitlines() if d.strip()]
            content_hash, line_count = write_acl_list_file(acl.name, dominios)
            acl.value = None
            acl.content_hash = content_hash
            acl.line_count = line_count
            migradas += 1
        elif not ruta.exists():
            # Ya migrada (value en NULL) pero el archivo no está: no hay de
            # dónde reconstruirla. Se deja constancia en el log en vez de
            # fallar todo el apply -las demás ACLs sí pueden aplicarse bien.
            logger.error(
                f"ACL de archivo '{acl.name}' no tiene contenido en la BD ni "
                f"el archivo {ruta} existe: quedará sin dominios hasta que se "
                "vuelva a cargar desde 'Cargar dominios'."
            )
        # Si el archivo existe y `value` ya es NULL: nada que hacer, es el
        # caso normal -el archivo ya es correcto, escrito directamente por
        # bulk_domains() o por una migración anterior de este mismo bucle.

    if migradas:
        db.commit()
        logger.info(f"{migradas} ACL(s) de archivo migrada(s) al nuevo esquema (value -> archivo)")

    borrados = 0
    for existente in ACL_LISTS_DIR.glob("*.txt"):
        if existente.name not in esperados:
            existente.unlink()
            borrados += 1

    if borrados:
        logger.info(f"{borrados} archivo(s) de ACL sobrante(s) eliminado(s) de {ACL_LISTS_DIR}")
    return len(acls_de_archivo)


def reload_squid() -> tuple[bool, str]:
    """Recarga la configuracion de Squid (squid -k reconfigure).

    Nota: cambiar http_port requiere reiniciar Squid, no solo reconfigure.
    El llamador debe verificar si el puerto cambio y llamar a restart_squid()
    en su lugar.
    """
    return get_runtime().reconfigure()


def purge_credentials() -> tuple[bool, str]:
    """Reinicia Squid para purgar SU cache de credenciales validadas.

    IMPORTANTE - limite real, no un detalle de implementacion: esto NO hace
    que el navegador de un usuario vuelva a pedirle la contrasena si esa
    contrasena sigue siendo valida. El navegador tiene su propia cache de
    credenciales (HTTP Basic Auth), separada de la de Squid, y ningun
    servidor puede borrarla de forma remota. Lo unico que hace esto es
    obligar a Squid a re-validar contra la fuente (htpasswd o LDAP) en la
    siguiente peticion de cada quien, en vez de confiar en una validacion
    anterior hasta que venza `credentialsttl`. Sirve para que un cambio de
    permisos (grupo, deshabilitar) surta efecto mas rapido - no sirve para
    "desloguear" a nadie que siga teniendo una contrasena valida. Para
    forzar una re-autenticacion visible de verdad hay que invalidar la
    credencial: resetear la contrasena, o deshabilitar la cuenta.
    """
    ok, msg = get_runtime().restart()
    if not ok:
        logger.error(f"Error purgando credenciales: {msg}")
        return False, msg

    logger.info("Squid reiniciado para purgar la caché de credenciales")
    return True, (
        "Caché de credenciales purgada (Squid reiniciado). Squid revalidará a cada usuario en su "
        "próxima petición, pero quien tenga una contraseña todavía válida seguirá navegando sin que "
        "se le pida nada: esto no fuerza un re-login visible. Para eso, resetea su contraseña o "
        "deshabilita la cuenta desde Usuarios."
    )


def validate_squid_config(config_text: str) -> tuple[bool, str]:
    """Valida la configuracion ejecutando `squid -k parse` donde hay Squid.

    La comprobacion se delega en el runtime porque tiene que correr donde este
    el binario: en el contenedor del backend no existe, y la version original
    capturaba el FileNotFoundError y devolvia «valido» para cualquier entrada.
    """
    # Se escribe a un fichero aparte para no tocar el squid.conf en uso hasta
    # saber que la configuracion nueva es correcta.
    candidate = Path(settings.SQUID_CONFIG_PATH).with_suffix(".conf.candidate")
    try:
        candidate.write_text(config_text)
    except Exception as e:
        return False, f"No se pudo escribir la configuración candidata: {e}"

    try:
        exit_code, output = get_runtime().parse_config(str(candidate))
    except Exception as e:
        return False, f"Error ejecutando la validación: {e}"

    # Quedarse con las lineas de error, que es lo accionable.
    errors = [
        line for line in output.splitlines()
        if "ERROR" in line or "FATAL" in line or "aborting" in line.lower()
    ]

    # No basta con mirar el codigo de salida. Ante una directiva obsoleta o
    # desconocida, `squid -k parse` avisa por ERROR pero termina con exito: la
    # configuracion se daba por buena y la directiva quedaba en el fichero sin
    # hacer nada, con el unico rastro de una linea en un log que nadie mira.
    # Asi se colo un `dns_v4_first` que Squid 6 ya no soporta.
    if exit_code != 0 or errors:
        detalle = "\n".join(errors[:10]) or output[-1000:]
        return False, detalle

    warnings = [line for line in output.splitlines() if "WARNING" in line]
    return True, "\n".join(warnings[:10]) if warnings else "Configuración válida"


def write_ldap_aux_files(ldap_config, allowed_usernames: list[str]) -> bool:
    """Escribe los archivos auxiliares de auth LDAP en el volumen compartido.

    - /etc/squid/ldap_helper.conf : configuración de conexión LDAP (key=value)
    - /etc/squid/ldap_allowlist   : usuarios LDAP autorizados (allow-list estricto)

    El helper personalizado (squidmanager_auth_helper) lee estos archivos.
    """
    try:
        if ldap_config and getattr(ldap_config, "enabled", False):
            conf_lines = [
                f"server_url={ldap_config.server_url or ''}",
                f"bind_dn={ldap_config.bind_dn or ''}",
                f"bind_password={ldap_config.bind_password or ''}",
                f"search_base={ldap_config.search_base or ''}",
                f"user_filter={ldap_config.user_filter or '(sAMAccountName=%s)'}",
            ]
            _write_private(LDAP_CONF_PATH, "\n".join(conf_lines) + "\n")
        else:
            # LDAP deshabilitado: vaciar config (solo queda auth local)
            _write_private(LDAP_CONF_PATH, "")

        content = "\n".join(allowed_usernames) + ("\n" if allowed_usernames else "")
        _write_private(LDAP_ALLOWLIST_PATH, content)

        logger.info(f"Archivos auxiliares LDAP escritos (allow-list: {len(allowed_usernames)} usuarios)")
        return True
    except Exception as e:
        logger.error(f"Error escribiendo archivos auxiliares LDAP: {e}")
        return False


def verify_published_port(expected_port: str) -> tuple[bool, str]:
    """Comprueba que el proxy es accesible de verdad en el puerto esperado.

    Es la comprobacion que faltaba: un desajuste entre el puerto que se publica
    y el que Squid escucha no lo detectaba nadie, porque el proceso seguia vivo
    y «sano» mientras el proxy era inalcanzable desde fuera.
    """
    return get_runtime().verify_port(expected_port)


def restart_squid() -> tuple[bool, str]:
    """Hace efectivo en Squid el puerto que indica la base de datos.

    Que significa «hacerlo efectivo» depende del despliegue y lo resuelve el
    runtime: en contenedor hay que recrearlo, porque el puerto publicado se
    fija al crearlo; en instalacion nativa basta con reiniciar, porque el
    puerto ya esta en el squid.conf recien escrito.
    """
    try:
        from app.database import SessionLocal
        from app.models.squid_settings import SquidSetting

        db = SessionLocal()
        try:
            port_setting = db.query(SquidSetting).filter(SquidSetting.key == "http_port").first()
            if not port_setting:
                return False, "No se encontró http_port en la BD"
            new_port = str(port_setting.value).strip()
        finally:
            db.close()

        if not new_port.isdigit():
            return False, f"El puerto configurado no es un número: '{new_port}'"

        return get_runtime().apply_port(new_port)
    except Exception as e:
        logger.error(f"Error aplicando el puerto en Squid: {e}")
        return False, f"Error: {e}"


# El hilo de arranque (main.py) y el endpoint POST /apply pueden llamar a esto
# al mismo tiempo, y ambos escriben sobre el mismo fichero .conf.candidate: sin
# este lock, una ejecución puede pisar el candidate de la otra a mitad de
# escritura, o las dos validar sobre un mismo intermedio inconsistente.
_apply_lock = threading.Lock()


def apply_squid_config(db) -> dict:
    """Aplica la configuración de Squid, serializado: una ejecución a la vez."""
    with _apply_lock:
        return _apply_squid_config(db)


def _apply_squid_config(db) -> dict:
    """Genera y aplica la configuración de Squid de extremo a extremo.

    Flujo:
      0. Escribe los archivos de las ACLs respaldadas por archivo (listas de
         dominio grandes): Squid los abre AL PARSEAR, así que tienen que
         existir antes del paso 2, a diferencia del resto de auxiliares.
      1. Genera squid.conf desde la BD.
      2. Valida la sintaxis DENTRO del contenedor de Squid.
      3. Solo si es válida, la escribe sobre el squid.conf en uso.
      4. Escribe los archivos auxiliares de auth LDAP y el fichero de usuarios.
      5. Recarga con `squid -k reconfigure` (o reinicia, solo si cambió el
         puerto: eso sí exige reabrir el socket de escucha).
      6. Marca el estado «limpio».

    Si la validación falla no se toca nada: antes se escribía primero y se
    validaba con una comprobación que siempre daba «válido», de modo que una
    configuración rota tumbaba el proxy.
    """
    from app.services.config_generator import generate_squid_config
    from app.services.config_state import mark_clean, mark_dirty
    from app.models.ldap_config import LdapConfig
    from app.models.ldap_user import LdapUser
    from app.models.kerberos_config import KerberosConfig

    # Se consulta una sola vez: generate_squid_config y escribir_keytab (mas
    # abajo) necesitan la misma fila unica, y antes cada una la volvia a
    # pedir por su cuenta.
    kerberos = db.query(KerberosConfig).first()
    config_text = generate_squid_config(db, kerberos=kerberos)
    preview = config_text[:500] + ("..." if len(config_text) > 500 else "")

    # 0. Las ACLs respaldadas por archivo se escriben ANTES de validar -única
    # excepción a "nada se toca antes de validar squid.conf"-, porque a
    # diferencia de squid_passwd/squid_digest (que el helper de auth abre en
    # caliente, cuando llega una petición real) Squid abre el archivo de una
    # ACL dstdomain/dstdom_regex DURANTE EL PROPIO PARSEO de la config. Sin
    # esto, la primera vez que se crea una ACL así la validación fallaba con
    # "Can not open file ... for reading" -confirmado en vivo- aunque el
    # squid.conf generado fuera perfectamente válido. Escribir estos
    # archivos no afecta al Squid en producción: son datos independientes de
    # que el candidato de squid.conf termine aplicándose o no.
    build_acl_list_files(db)

    # 1. Validar ANTES de escribir squid.conf.
    valid, msg = validate_squid_config(config_text)
    if not valid:
        mark_dirty()
        return {
            "status": "error",
            "message": f"Configuración inválida, no se ha aplicado nada:\n{msg}",
            "needs_restart": False,
            "config_preview": preview,
        }

    # 1b. Si hay servidores DNS propios, comprobar que responden de verdad.
    #     La sintaxis puede ser correcta y el servidor estar caído: en ese caso
    #     no falla una web, dejan de resolver todas a la vez, y el síntoma no
    #     apunta a la causa. Mejor rechazar el cambio que dejar el proxy ciego.
    from app.models.squid_settings import SquidSetting as _Ajuste
    from app.services.dns_service import parsear_lista, probar_servidores

    ajuste_dns = db.query(_Ajuste).filter(_Ajuste.key == "dns_nameservers").first()
    servidores_dns = parsear_lista(ajuste_dns.value if ajuste_dns else None)
    if servidores_dns:
        dns_ok, dns_msg = probar_servidores(servidores_dns)
        if not dns_ok:
            mark_dirty()
            return {
                "status": "error",
                "message": (
                    "Los servidores DNS configurados no responden, no se ha "
                    f"aplicado nada:\n{dns_msg}\n\nCorrige el ajuste «Servidores "
                    "DNS» o déjalo vacío para usar la resolución del sistema."
                ),
                "needs_restart": False,
                "config_preview": preview,
            }

    # 1c. Si la salida va por otro proxy, comprobar que ese proxy responde.
    #     Un padre inalcanzable no degrada la navegación: la corta entera, para
    #     todos los usuarios a la vez, y encima con `never_direct` activo Squid
    #     ni siquiera intenta la salida directa.
    from app.models.parent_proxy import ParentProxy
    from app.services.parent_proxy_service import probar_configuracion

    padre = db.query(ParentProxy).first()
    if padre and padre.enabled:
        padre_ok, padre_msg = probar_configuracion(padre)
        if not padre_ok:
            mark_dirty()
            return {
                "status": "error",
                "message": (
                    "El proxy padre no responde, no se ha aplicado nada:\n"
                    f"{padre_msg}\n\nCorrige la configuración en «Proxy padre» "
                    "o desactívalo para salir directamente a Internet."
                ),
                "needs_restart": False,
                "config_preview": preview,
            }

        # 1d. 'passthru' reenvía las credenciales del cliente al padre, y no
        #     se puede combinar con que este mismo Squid autentique a sus
        #     clientes. A diferencia de la comprobación de PUT /parent-proxy,
        #     esta cubre el caso de habilitar LDAP/Kerberos/un usuario local
        #     DESPUÉS de haber dejado el padre en passthru.
        from app.services.parent_proxy_service import validar_auth_method_compatible

        auth_ok, auth_msg = validar_auth_method_compatible(padre.auth_method or "fixed", db)
        if not auth_ok:
            mark_dirty()
            return {
                "status": "error",
                "message": f"No se ha aplicado nada:\n{auth_msg}",
                "needs_restart": False,
                "config_preview": preview,
            }

    # 2. El puerto elegido en el panel tiene que ser el que el proxy atiende
    #    de verdad. Se lee de la base de datos, que es donde lo deja el panel,
    #    y el runtime comprueba si hace falta actuar: recrear el contenedor en
    #    modo Docker, reiniciar el servicio en modo nativo.
    from app.models.squid_settings import SquidSetting

    port_setting = db.query(SquidSetting).filter(SquidSetting.key == "http_port").first()
    desired_port = str(port_setting.value).strip() if port_setting else ""
    port_changed = False
    if desired_port.isdigit():
        published_ok, published_msg = verify_published_port(desired_port)
        port_changed = not published_ok
        if port_changed:
            logger.info(f"Hay que recrear el contenedor: {published_msg}")

    # 3. Escribir la configuración ya validada.
    with open(settings.SQUID_CONFIG_PATH, "w") as f:
        f.write(config_text)

    # El .env se sincroniza en cada aplicación, no solo cuando cambia el
    # puerto: así una instalación antigua o una edición manual del fichero se
    # corrigen solas en el siguiente «Aplicar cambios», en vez de quedar como
    # una divergencia latente que solo se manifiesta al reiniciar la máquina.
    if desired_port.isdigit():
        estado_ok, estado_msg = get_runtime().sync_port_state(desired_port)
        if not estado_ok:
            logger.warning(f"No se pudo sincronizar el estado del puerto: {estado_msg}")

    # 4. Archivos auxiliares: LDAP y usuarios del proxy.
    # Certificado del proxy padre: tiene que estar en el volumen antes de que
    # Squid lea la configuración que lo declara.
    from app.services.parent_proxy_service import escribir_ca_padre

    escribir_ca_padre(padre)

    # Keytab y krb5.conf de Kerberos: tienen que estar en el volumen antes de
    # que Squid lea la configuración que declara el bloque de autenticación
    # Negotiate. `kerberos` ya se cargó arriba, antes de generar el config.
    # Sin krb5.conf, Squid rechaza tickets reales de un AD con "Bad
    # encryption type" pese a tener el keytab correcto -confirmado en vivo-.
    from app.services.kerberos_service import escribir_keytab, escribir_krb5_conf

    escribir_keytab(kerberos)
    escribir_krb5_conf(kerberos)

    ldap_config = db.query(LdapConfig).first()
    allowed_ldap = [u.username for u in db.query(LdapUser).filter(LdapUser.enabled == True).all()]  # noqa: E712
    write_ldap_aux_files(ldap_config, allowed_ldap)
    write_passwd_file(db)
    write_digest_file(db, realm_actual(db))

    mark_clean()

    warnings = msg if msg != "Configuración válida" else ""

    # 5a. Cambió el puerto: hay que recrear el contenedor.
    if port_changed:
        ok, restart_msg = restart_squid()
        return {
            "status": "ok" if ok else "warning",
            "message": f"Puerto actualizado: {restart_msg}",
            "needs_restart": False,
            "warnings": warnings,
            "config_preview": preview,
        }

    # 5b. Recargar en caliente. `squid -k reconfigure` sí re-lee correctamente
    # el flag `ssl-bump` del `http_port` (activarlo, desactivarlo o dejarlo
    # igual) sin reiniciar el proceso: verificado en vivo en Squid 6.14, mismo
    # PID y "Accepting SSL bumped HTTP Socket connections" en las tres
    # transiciones. Antes se forzaba un `systemctl restart`/recreación de
    # contenedor completos cada vez que el config tenía SSL Bump —que es el
    # caso por defecto—, aunque el cambio fuera ajeno a TLS (una ACL, un delay
    # pool): un reinicio nativo puede tardar hasta ~60s en `_wait_until_active`
    # y de paso corta las conexiones activas y purga la caché de credenciales
    # de todo el mundo. Reconfigure es ahora el camino único para todo lo que
    # no sea un cambio de puerto.
    success, reload_msg = reload_squid()
    return {
        "status": "ok" if success else "warning",
        "message": f"Squid reconfigurado: {reload_msg}",
        "needs_restart": False,
        "warnings": warnings,
        "config_preview": preview,
    }


def get_squid_status() -> dict:
    """Obtiene el estado del servicio Squid."""
    return get_runtime().status()
