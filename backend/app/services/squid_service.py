"""Servicio para controlar el contenedor Squid y generar archivos auxiliares."""

import os
import time
import logging
from pathlib import Path

import docker as docker_sdk

from app.config import settings
from app.utils import utcnow

logger = logging.getLogger(__name__)

PASSWD_PATH = Path("/etc/squid/squid_passwd")
LDAP_CONF_PATH = Path("/etc/squid/ldap_helper.conf")
LDAP_ALLOWLIST_PATH = Path("/etc/squid/ldap_allowlist")

# uid/gid del usuario 'proxy' en la imagen de Squid (Ubuntu 24.04).
PROXY_UID = 13
PROXY_GID = 13


def _get_docker_client():
    """Obtiene un cliente Docker usando el socket montado."""
    try:
        return docker_sdk.from_env()
    except Exception as e:
        logger.error(f"No se pudo conectar a Docker: {e}")
        return None


def _write_private(path: Path, content: str) -> None:
    """Escribe un fichero con secretos: solo legible por su propietario.

    Estos ficheros viven en un volumen compartido con el contenedor de Squid y
    contienen la contraseña de bind de LDAP y los hashes de los usuarios del
    proxy. Con los permisos por defecto (644) los lee cualquier proceso de
    cualquiera de los dos contenedores.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    # Crear con 600 desde el principio, no escribir y luego ajustar.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
    finally:
        pass
    os.chmod(path, 0o600)
    try:
        # Squid corre como 'proxy' y necesita poder leerlos.
        os.chown(path, PROXY_UID, PROXY_GID)
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


def _wait_until_running(container, timeout: int = 60) -> bool:
    """Espera a que el contenedor vuelva a estar en marcha tras un reinicio.

    Un `restart()` devuelve el control antes de que el proceso esté listo, y
    cualquier exec lanzado mientras tanto falla con 409 "is restarting".
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            container.reload()
            if container.status == "running":
                # Squid tarda un poco más en abrir el puerto que el contenedor
                # en pasar a "running".
                time.sleep(2)
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def reload_squid() -> tuple[bool, str]:
    """Recarga la configuración de Squid (squid -k reconfigure).

    Nota: cambiar http_port requiere reiniciar Squid, no solo reconfigure.
    El llamador debe verificar si el puerto cambió y llamar a restart_squid() en su lugar.
    """
    try:
        client = _get_docker_client()
        if not client:
            return False, "No se pudo conectar al daemon Docker"

        container = client.containers.get(settings.SQUID_CONTAINER_NAME)
        result = container.exec_run(["squid", "-k", "reconfigure"])
        output = result.output.decode("utf-8", errors="replace") if result.output else ""

        if result.exit_code == 0:
            return True, "Squid reconfigurado correctamente"
        return False, f"Error (exit {result.exit_code}): {output}"
    except Exception as e:
        logger.error(f"Error recargando Squid: {e}")
        return False, f"Error: {e}"


def purge_credentials() -> tuple[bool, str]:
    """Reinicia Squid para purgar SU caché de credenciales validadas.

    IMPORTANTE — límite real, no un detalle de implementación: esto NO hace
    que el navegador de un usuario vuelva a pedirle la contraseña si esa
    contraseña sigue siendo válida. El navegador tiene su propia caché de
    credenciales (HTTP Basic Auth), separada de la de Squid, y ningún
    servidor puede borrarla de forma remota. Lo único que hace esto es
    obligar a Squid a re-validar contra la fuente (htpasswd o LDAP) en la
    siguiente petición de cada quien, en vez de confiar en una validación
    anterior hasta que venza `credentialsttl`. Sirve para que un cambio de
    permisos (grupo, deshabilitar) surta efecto más rápido — no sirve para
    "desloguear" a nadie que siga teniendo una contraseña válida. Para
    forzar una re-autenticación visible de verdad hay que invalidar la
    credencial: resetear la contraseña, o deshabilitar la cuenta.
    """
    try:
        client = _get_docker_client()
        if not client:
            return False, "No se pudo conectar al daemon Docker"

        container = client.containers.get(settings.SQUID_CONTAINER_NAME)
        container.restart(timeout=10)
        _wait_until_running(container)
        logger.info("Squid reiniciado para purgar la caché de credenciales")
        return True, (
            "Caché de credenciales purgada (Squid reiniciado). Squid revalidará a cada usuario en su "
            "próxima petición, pero quien tenga una contraseña todavía válida seguirá navegando sin que "
            "se le pida nada: esto no fuerza un re-login visible. Para eso, reseteá su contraseña o "
            "deshabilitá la cuenta desde Usuarios."
        )
    except Exception as e:
        logger.error(f"Error purgando credenciales: {e}")
        return False, f"Error: {e}"


def validate_squid_config(config_text: str) -> tuple[bool, str]:
    """Valida la configuración ejecutando `squid -k parse` donde hay Squid.

    La comprobación se hace dentro del contenedor de Squid: en el del backend
    el binario no existe, así que la versión anterior capturaba el
    FileNotFoundError y devolvía «válido» para cualquier entrada.
    """
    client = _get_docker_client()
    if not client:
        return False, "No se pudo conectar a Docker para validar la configuración"

    try:
        container = client.containers.get(settings.SQUID_CONTAINER_NAME)
    except Exception as e:
        return False, f"No se encontró el contenedor de Squid para validar: {e}"

    if container.status != "running":
        return False, "El contenedor de Squid no está en ejecución: no se puede validar"

    # Se escribe a un fichero aparte para no tocar el squid.conf en uso hasta
    # saber que la configuración nueva es correcta.
    candidate = Path("/etc/squid/squid.conf.candidate")
    try:
        candidate.write_text(config_text)
    except Exception as e:
        return False, f"No se pudo escribir la configuración candidata: {e}"

    try:
        result = container.exec_run(["squid", "-k", "parse", "-f", str(candidate)])
        output = result.output.decode("utf-8", errors="replace") if result.output else ""
    except Exception as e:
        return False, f"Error ejecutando la validación: {e}"

    if result.exit_code != 0:
        # Quedarse con las líneas de error, que es lo accionable.
        errors = [
            line for line in output.splitlines()
            if "ERROR" in line or "FATAL" in line or "aborting" in line.lower()
        ]
        return False, "\n".join(errors[:10]) or output[-1000:]

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


def restart_squid() -> tuple[bool, str]:
    """Recrea el contenedor Squid con el puerto que indica la base de datos.

    El contenedor anterior se renombra en lugar de borrarse: si la creación del
    nuevo falla, se restaura y el proxy sigue funcionando. También se copian la
    política de reinicio, el healthcheck y las etiquetas de Docker Compose, que
    antes se perdían al recrear.
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

        client = _get_docker_client()
        if not client:
            return False, "No se pudo conectar a Docker"

        try:
            old_container = client.containers.get(settings.SQUID_CONTAINER_NAME)
        except Exception:
            return False, f"Contenedor {settings.SQUID_CONTAINER_NAME} no encontrado"

        old_container.reload()
        old_config = old_container.attrs
        host_config = old_config.get("HostConfig", {})

        image = old_config["Config"]["Image"]
        env = old_config["Config"].get("Env") or []
        env = [e if not e.startswith("SQUID_PORT=") else f"SQUID_PORT={new_port}" for e in env]

        volumes = []
        for mount in old_config.get("Mounts", []):
            if mount["Type"] == "volume":
                volumes.append(f"{mount['Name']}:{mount['Destination']}")
            elif mount["Type"] == "bind":
                volumes.append(f"{mount['Source']}:{mount['Destination']}")

        net_settings = old_config.get("NetworkSettings", {}).get("Networks", {})
        network = list(net_settings.keys())[0] if net_settings else None

        # Conservar lo que define Compose, que antes se perdía.
        labels = old_config["Config"].get("Labels") or {}
        restart_policy = host_config.get("RestartPolicy") or {"Name": "unless-stopped"}
        healthcheck = old_config["Config"].get("Healthcheck")

        # Apartar el contenedor viejo sin destruirlo todavía.
        backup_name = f"{settings.SQUID_CONTAINER_NAME}-old-{int(time.time())}"
        old_container.stop(timeout=10)
        old_container.rename(backup_name)

        try:
            new_container = client.containers.create(
                image=image,
                name=settings.SQUID_CONTAINER_NAME,
                environment=env,
                ports={f"{new_port}/tcp": int(new_port)},
                volumes=volumes,
                network=network,
                labels=labels,
                restart_policy={"Name": restart_policy.get("Name") or "unless-stopped"},
                healthcheck=healthcheck,
                tty=True,
                stdin_open=True,
            )
            new_container.start()
        except Exception as e:
            # Rollback: devolver el contenedor original a su sitio.
            logger.error(f"Fallo recreando Squid, restaurando el contenedor anterior: {e}")
            try:
                old_container.rename(settings.SQUID_CONTAINER_NAME)
                old_container.start()
                return False, f"No se pudo recrear el contenedor ({e}). Se restauró el anterior."
            except Exception as rollback_error:
                return False, (
                    f"No se pudo recrear el contenedor ({e}) y tampoco restaurar el "
                    f"anterior ({rollback_error}). Revisa con: docker ps -a"
                )

        # El nuevo arrancó: ya se puede retirar el viejo.
        try:
            old_container.remove(force=True)
        except Exception as e:
            logger.warning(f"El contenedor anterior no se pudo eliminar ({backup_name}): {e}")

        _wait_until_running(new_container)

        db = SessionLocal()
        try:
            write_passwd_file(db)
            new_container.exec_run(["squid", "-k", "reconfigure"])
        finally:
            db.close()

        logger.info(f"Contenedor Squid recreado en puerto {new_port}")
        return True, f"Contenedor recreado en puerto {new_port} (usuarios regenerados)"
    except Exception as e:
        logger.error(f"Error recreando Squid: {e}")
        return False, f"Error: {e}"


def apply_squid_config(db, force_reconfigure: bool = False) -> dict:
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
    import re as regex

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

    # 2. ¿Cambió el puerto respecto a lo que Docker publica?
    new_port_match = regex.search(r"^http_port\s+(\d+)", config_text, regex.MULTILINE)
    new_port = new_port_match.group(1) if new_port_match else None
    port_changed = False
    if new_port:
        try:
            client = docker_sdk.from_env()
            container = client.containers.get(settings.SQUID_CONTAINER_NAME)
            container.reload()
            published_ports = container.attrs.get("NetworkSettings", {}).get("Ports", {})
            for _port_key, bindings in published_ports.items():
                if bindings and isinstance(bindings, list):
                    for binding in bindings:
                        published = binding.get("HostPort")
                        if published and published != new_port:
                            port_changed = True
                            logger.info(
                                f"Puerto cambió: Docker publica {published}, BD dice {new_port}."
                            )
                            break
        except Exception as e:
            logger.warning(f"No se pudo comparar puertos con Docker: {e}")

    # 3. Escribir la configuración ya validada.
    with open(settings.SQUID_CONFIG_PATH, "w") as f:
        f.write(config_text)

    # 4. Archivos auxiliares: LDAP y usuarios del proxy.
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
        try:
            client = docker_sdk.from_env()
            container = client.containers.get(settings.SQUID_CONTAINER_NAME)
            container.restart(timeout=10)
            if not _wait_until_running(container):
                return {
                    "status": "warning",
                    "message": "Configuración aplicada, pero Squid tarda en arrancar. Revisa el estado del proxy.",
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
        except Exception as e:
            return {
                "status": "warning",
                "message": f"Config escrito pero error reiniciando: {e}",
                "needs_restart": True,
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
    status = {"running": False, "state": "unknown", "pid": None, "errors": []}
    try:
        client = _get_docker_client()
        if not client:
            status["errors"].append("No se pudo conectar a Docker")
            return status

        container = client.containers.get(settings.SQUID_CONTAINER_NAME)
        status["running"] = container.status == "running"
        status["state"] = container.status
        try:
            container.reload()
            status["pid"] = container.attrs.get("State", {}).get("Pid")
        except Exception:
            pass
    except Exception as e:
        status["errors"].append(str(e))
    return status
