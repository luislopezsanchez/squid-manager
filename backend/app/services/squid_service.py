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
LDAP_CONF_PATH = Path("/etc/squid/ldap_helper.conf")
LDAP_ALLOWLIST_PATH = Path("/etc/squid/ldap_allowlist")

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
    proceso de la máquina.

    El modo es 640 con grupo `proxy`, no 600, y la razón es que los dos
    despliegues llegan al mismo sitio por caminos distintos:

    - En contenedor el backend es root, puede hacer chown a proxy:proxy y el
      fichero queda accesible para Squid como propietario.
    - En instalación nativa el backend corre con su propio usuario, cuyo grupo
      primario es `proxy`. No puede hacer chown —ni falta—, porque el fichero
      ya nace con el grupo correcto y Squid lo lee por grupo.

    En los dos casos el conjunto de quien puede leerlo es el mismo: root, el
    panel y Squid.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    # Crear con los permisos definitivos, no escribir y luego ajustar.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o640)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
    finally:
        pass
    os.chmod(path, 0o640)

    # Solo root puede reasignar propietario. Intentarlo sin serlo falla siempre
    # y llenaría el log de avisos en cada aplicación de la configuración.
    if getattr(os, "geteuid", lambda: 1)() == 0:
        uid, gid = _proxy_ids()
        try:
            os.chown(path, uid, gid)
        except (PermissionError, OSError) as e:
            logger.warning(f"No se pudo cambiar el propietario de {path}: {e}")


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


def apply_squid_config(db, force_reconfigure: bool = False) -> dict:
    """Aplica la configuración de Squid, serializado: una ejecución a la vez."""
    with _apply_lock:
        return _apply_squid_config(db, force_reconfigure=force_reconfigure)


def _apply_squid_config(db, force_reconfigure: bool = False) -> dict:
    """Genera y aplica la configuración de Squid de extremo a extremo.

    Flujo:
      1. Genera squid.conf desde la BD.
      2. Valida la sintaxis DENTRO del contenedor de Squid.
      3. Solo si es válida, la escribe sobre el squid.conf en uso.
      4. Escribe los archivos auxiliares de auth LDAP y el fichero de usuarios.
      5. Recarga (o reinicia, si hay SSL Bump o cambió el puerto).
      6. Marca el estado «limpio».

    Si la validación falla no se toca nada: antes se escribía primero y se
    validaba con una comprobación que siempre daba «válido», de modo que una
    configuración rota tumbaba el proxy.

    Parámetro `force_reconfigure`: fuerza `squid -k reconfigure` en lugar de un
    reinicio completo aunque el config tenga SSL Bump. Útil para cambios de
    solo-ACL (p. ej. miembros de un grupo), que reconfigure recarga sin purgar
    credenciales ni cortar conexiones activas.
    """
    from app.services.config_generator import generate_squid_config
    from app.services.config_state import mark_clean, mark_dirty
    from app.models.ldap_config import LdapConfig
    from app.models.ldap_user import LdapUser

    config_text = generate_squid_config(db)
    preview = config_text[:500] + ("..." if len(config_text) > 500 else "")

    # 1. Validar ANTES de escribir nada.
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

    ldap_config = db.query(LdapConfig).first()
    allowed_ldap = [u.username for u in db.query(LdapUser).filter(LdapUser.enabled == True).all()]  # noqa: E712
    write_ldap_aux_files(ldap_config, allowed_ldap)
    write_passwd_file(db)

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

    # 5b. SSL Bump: reinicio completo, salvo que se pida reconfigure.
    if "ssl-bump" in config_text and not force_reconfigure:
        ok, restart_msg = get_runtime().restart()
        if not ok:
            return {
                "status": "warning",
                "message": f"Configuración aplicada, pero Squid no reinició bien: {restart_msg}",
                "needs_restart": True,
                "warnings": warnings,
                "config_preview": preview,
            }
        return {
            "status": "ok",
            "message": "Squid reiniciado con SSL Bump (configuración aplicada)",
            "needs_restart": False,
            "warnings": warnings,
            "config_preview": preview,
        }

    # 5c. Sin SSL Bump: reconfigure normal.
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
