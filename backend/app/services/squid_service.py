"""Servicio para controlar el contenedor Squid y generar archivos auxiliares."""

import subprocess
import logging
from pathlib import Path

import docker as docker_sdk

from app.config import settings

logger = logging.getLogger(__name__)


def _get_docker_client():
    """Obtiene un cliente Docker usando el socket montado."""
    try:
        return docker_sdk.from_env()
    except Exception as e:
        logger.error(f"No se pudo conectar a Docker: {e}")
        return None


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
    """Reinicia Squid para purgar la caché de credenciales de autenticación.

    IMPORTANTE: `squid -k reconfigure` NO limpia la caché de credenciales de
    autenticación de Squid. La única forma fiable de forzar la re-autenticación
    de todos los usuarios es REINICIAR el proceso de Squid, lo que purga la
    caché por completo.
    """
    try:
        client = _get_docker_client()
        if not client:
            return False, "No se pudo conectar al daemon Docker"

        container = client.containers.get(settings.SQUID_CONTAINER_NAME)
        container.restart(timeout=10)
        logger.info("Squid reiniciado para purgar la caché de credenciales")
        return True, "Caché de credenciales purgada (Squid reiniciado). Todos los usuarios deberán volver a autenticarse."
    except Exception as e:
        logger.error(f"Error purgando credenciales: {e}")
        return False, f"Error: {e}"


def write_ldap_aux_files(ldap_config, allowed_usernames: list[str]) -> bool:
    """Escribe los archivos auxiliares de auth LDAP en el volumen compartido.

    - /etc/squid/ldap_helper.conf : configuración de conexión LDAP (key=value)
    - /etc/squid/ldap_allowlist   : usuarios LDAP autorizados (allow-list estricto)

    El helper personalizado (squidmanager_auth_helper) lee estos archivos.
    """
    try:
        conf_path = Path("/etc/squid/ldap_helper.conf")
        allow_path = Path("/etc/squid/ldap_allowlist")

        # ldap_helper.conf
        if ldap_config and getattr(ldap_config, "enabled", False):
            conf_lines = [
                f"server_url={ldap_config.server_url or ''}",
                f"bind_dn={ldap_config.bind_dn or ''}",
                f"bind_password={ldap_config.bind_password or ''}",
                f"search_base={ldap_config.search_base or ''}",
                f"user_filter={ldap_config.user_filter or '(sAMAccountName=%s)'}",
            ]
            conf_path.write_text("\n".join(conf_lines) + "\n")
        else:
            # LDAP deshabilitado: vaciar config (solo queda auth local)
            conf_path.write_text("")

        # ldap_allowlist
        content = "\n".join(allowed_usernames) + ("\n" if allowed_usernames else "")
        allow_path.write_text(content)

        logger.info(f"Archivos auxiliares LDAP escritos (allow-list: {len(allowed_usernames)} usuarios)")
        return True
    except Exception as e:
        logger.error(f"Error escribiendo archivos auxiliares LDAP: {e}")
        return False


def restart_squid() -> tuple[bool, str]:
    """Recrea el contenedor Squid con el nuevo puerto.

    Usa el SDK de Docker para:
    1. Leer el puerto de la BD
    2. Actualizar el .env del host (via volumen montado)
    3. Detener y recrear el contenedor con el nuevo mapeo de puertos
    """
    try:
        import subprocess
        import re as regex
        from pathlib import Path
        from app.database import SessionLocal
        from app.models.squid_settings import SquidSetting

        # 1. Leer el puerto de la BD
        db = SessionLocal()
        try:
            port_setting = db.query(SquidSetting).filter(SquidSetting.key == "http_port").first()
            if not port_setting:
                return False, "No se encontró http_port en la BD"
            new_port = port_setting.value
        finally:
            db.close()

        # 2. Actualizar .env del host
        # El backend tiene montado ./app pero no el directorio del proyecto completo.
        # Sin embargo, podemos escribir el .env a traves del socket de Docker
        # o usar docker exec para actualizarlo.
        # Mas simple: usar el SDK para recrear el contenedor directamente.

        client = _get_docker_client()
        if not client:
            return False, "No se pudo conectar a Docker"

        # 3. Obtener el contenedor actual
        try:
            old_container = client.containers.get(settings.SQUID_CONTAINER_NAME)
        except Exception:
            return False, f"Contenedor {settings.SQUID_CONTAINER_NAME} no encontrado"

        # 4. Leer la configuración del contenedor actual
        old_container.reload()
        old_config = old_container.attrs

        # 5. Detener y eliminar el contenedor viejo
        old_container.stop(timeout=10)
        old_container.remove()

        # 6. Crear el nuevo contenedor con los mismos settings pero nuevo puerto
        image = old_config["Config"]["Image"]
        env = old_config["Config"]["Env"] or []
        # Actualizar SQUID_PORT en las variables de entorno
        env = [e if not e.startswith("SQUID_PORT=") else f"SQUID_PORT={new_port}" for e in env]

        # Volumes: reconstruir desde la config del contenedor
        volumes = []
        mounts = old_config.get("Mounts", [])
        for mount in mounts:
            if mount["Type"] == "volume":
                volumes.append(f"{mount['Name']}:{mount['Destination']}")
            elif mount["Type"] == "bind":
                volumes.append(f"{mount['Source']}:{mount['Destination']}")

        # Networks
        networks = {}
        net_settings = old_config.get("NetworkSettings", {}).get("Networks", {})
        for net_name in net_settings:
            networks[net_name] = {}

        # Crear nuevo contenedor
        new_container = client.containers.create(
            image=image,
            name=settings.SQUID_CONTAINER_NAME,
            environment=env,
            ports={f"{new_port}/tcp": new_port},
            volumes=volumes,
            network=list(net_settings.keys())[0] if net_settings else None,
            tty=True,
            stdin_open=True,
        )
        new_container.start()

        # 7. Esperar a que Squid arranque
        import time
        time.sleep(3)

        # 8. Regenerar archivo de usuarios y reconfigurar Squid
        db = SessionLocal()
        try:
            from app.models.proxy_user import ProxyUser
            users = db.query(ProxyUser).filter(ProxyUser.enabled == True).all()
            user_dicts = [
                {
                    "username": u.username,
                    "htpasswd_hash": u.htpasswd_hash,
                    "enabled": u.enabled,
                }
                for u in users
            ]
            # Escribir archivo passwd
            passwd_path = Path("/etc/squid/squid_passwd")
            passwd_path.parent.mkdir(parents=True, exist_ok=True)
            with open(passwd_path, "w") as f:
                for u in user_dicts:
                    if u["enabled"] and u.get("htpasswd_hash"):
                        f.write(f"{u['htpasswd_hash']}\n")
            logger.info(f"Archivo passwd regenerado con {len(user_dicts)} usuarios")

            # Reconfigurar Squid para que lea el nuevo config y passwd
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

    Flujo completo (el mismo que usaba el endpoint /squid/apply):
      1. Genera squid.conf desde la BD.
      2. Detecta cambio de puerto (requiere recrear contenedor).
      3. Escribe squid.conf.
      4. Escribe archivos auxiliares de auth LDAP (helper + allow-list).
      5. Valida sintaxis.
      6. Si hay SSL Bump -> reinicio completo del contenedor + regenera passwd.
         Si no -> reconfigure normal.
      7. Marca el estado "limpio" (sin cambios pendientes).

    Parámetro `force_reconfigure`: cuando es True, se fuerza `squid -k reconfigure`
    en lugar de un reinicio completo aunque el config tenga SSL Bump. Útil para
    cambios de solo-ACL (p. ej. añadir/quitar miembros de un grupo), que
    reconfigure recarga sin purgar credenciales ni cortar conexiones activas.

    Devuelve un dict {status, message, needs_restart, config_preview} apto para
    ser devuelto tal cual por el endpoint, o interpretado por otros servicios.
    """
    import re as regex
    import time

    from app.services.config_generator import generate_squid_config, validate_squid_config
    from app.services.config_state import mark_clean
    from app.models.ldap_config import LdapConfig
    from app.models.ldap_user import LdapUser
    from app.models.proxy_user import ProxyUser
    from app.database import SessionLocal

    config_text = generate_squid_config(db)

    # 2. Extraer el puerto nuevo del config generado
    new_port_match = regex.search(r"^http_port\s+(\d+)", config_text, regex.MULTILINE)
    new_port = new_port_match.group(1) if new_port_match else None

    # 3. Comparar con el puerto que Docker publica actualmente
    needs_restart = False
    if new_port:
        try:
            client = docker_sdk.from_env()
            container = client.containers.get(settings.SQUID_CONTAINER_NAME)
            container.reload()
            published_ports = container.attrs.get("NetworkSettings", {}).get("Ports", {})
            for port_key, bindings in published_ports.items():
                if bindings and isinstance(bindings, list):
                    for binding in bindings:
                        published = binding.get("HostPort")
                        if published and published != new_port:
                            needs_restart = True
                            logger.info(f"Puerto cambió: Docker publica {published}, BD dice {new_port}. Recreando contenedor.")
                            break
        except Exception as e:
            logger.warning(f"No se pudo comparar puertos con Docker: {e}")

    # 4. Escribir squid.conf
    config_path = settings.SQUID_CONFIG_PATH
    with open(config_path, "w") as f:
        f.write(config_text)

    # 4b. Escribir archivos auxiliares de auth LDAP
    ldap_config = db.query(LdapConfig).first()
    allowed_ldap = [u.username for u in db.query(LdapUser).filter(LdapUser.enabled == True).all()]
    write_ldap_aux_files(ldap_config, allowed_ldap)

    # 5. Validar sintaxis
    valid, msg = validate_squid_config(config_path)
    if not valid:
        return {"status": "error", "message": f"Configuración inválida: {msg}"}
    mark_clean()

    preview = config_text[:500] + ("..." if len(config_text) > 500 else "")

    # 5b. SSL Bump -> reinicio completo (no reconfigure), salvo que se fuerce reconfigure
    if "ssl-bump" in config_text and not force_reconfigure:
        try:
            client = docker_sdk.from_env()
            container = client.containers.get(settings.SQUID_CONTAINER_NAME)
            container.restart(timeout=10)
            time.sleep(5)
            # Regenerar usuarios tras el reinicio
            db2 = SessionLocal()
            try:
                users = db2.query(ProxyUser).filter(ProxyUser.enabled == True).all()
                passwd_path = Path("/etc/squid/squid_passwd")
                with open(passwd_path, "w") as f:
                    for u in users:
                        if u.htpasswd_hash:
                            f.write(f"{u.htpasswd_hash}\n")
                container.exec_run(["squid", "-k", "reconfigure"])
            finally:
                db2.close()
            return {
                "status": "ok",
                "message": "Squid reiniciado con SSL Bump (configuración aplicada)",
                "needs_restart": True,
                "config_preview": preview,
            }
        except Exception as e:
            return {
                "status": "warning",
                "message": f"Config escrito pero error reiniciando: {e}",
                "needs_restart": True,
                "config_preview": preview,
            }

    # 5a. Sin SSL Bump -> reconfigure normal
    success, reload_msg = reload_squid()
    return {
        "status": "ok" if success else "warning",
        "message": f"Squid reconfigurado: {reload_msg}",
        "needs_restart": needs_restart,
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


def write_passwd_file(users: list[dict], path: str = "/etc/squid/squid_passwd") -> bool:
    """Genera el archivo htpasswd usando el comando htpasswd del contenedor backend.

    Squid basic_ncsa_auth requiere formato htpasswd (Apache), no hashes bcrypt.
    Por eso usamos el comando 'htpasswd' para generar cada entrada.

    Args:
        users: Lista de dicts con 'username', 'password' (texto plano), 'enabled'
        path: Ruta del archivo htpasswd
    """
    try:
        passwd_path = Path(path)
        passwd_path.parent.mkdir(parents=True, exist_ok=True)

        # Eliminar archivo anterior
        if passwd_path.exists():
            passwd_path.unlink()

        for user in users:
            if not user.get("enabled", True):
                continue

            username = user["username"]
            password = user["password"]  # contraseña en texto plano

            # Usar htpasswd para crear el archivo (primer usuario) o añadir (resto)
            if not passwd_path.exists():
                cmd = ["htpasswd", "-bcB", str(passwd_path), username, password]
            else:
                cmd = ["htpasswd", "-bB", str(passwd_path), username, password]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                logger.error(f"Error htpasswd para {username}: {result.stderr}")

        logger.info(f"Archivo passwd generado con {len(users)} usuarios")
        return True
    except Exception as e:
        logger.error(f"Error escribiendo passwd file: {e}")
        return False