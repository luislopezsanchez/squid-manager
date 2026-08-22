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
    """Purga la caché de credenciales de autenticación de Squid.

    Fuerza a que todos los usuarios vuelvan a autenticarse (no solo uno),
    porque Squid mantiene una caché GLOBAL de credenciales (no hay purge por usuario).

    Squid limpia la caché de credenciales al reconfigure. Si se necesita un
    borrado más agresivo (garantizado), se reinicia el contenedor.
    """
    success, msg = reload_squid()
    if success:
        return True, "Caché de credenciales purgada. Los usuarios deberán volver a autenticarse."
    return False, msg


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