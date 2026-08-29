"""Runtime de Squid cuando corre como contenedor Docker.

Es el modo por defecto y el que usan todas las instalaciones existentes. El
codigo de este fichero estaba antes repartido por `squid_service`; aqui no
cambia de comportamiento, solo de sitio.
"""

import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

import docker as docker_sdk

from app.config import settings

from .base import INTERNAL_SQUID_PORT, ProxyRuntime

logger = logging.getLogger(__name__)

# Nombre del servicio Squid dentro del docker-compose.yml (distinto del nombre
# del contenedor, que es SQUID_CONTAINER_NAME).
SQUID_COMPOSE_SERVICE = "squid"

# Un unico exec que trae red, memoria y CPU. Las etiquetas evitan tener que
# adivinar que valor es cual por el orden de las lineas.
STATS_CMD = (
    "cat /proc/net/dev; "
    "echo '#CG#'; "
    'echo "memcur $(cat /sys/fs/cgroup/memory.current 2>/dev/null)"; '
    'echo "memmax $(cat /sys/fs/cgroup/memory.max 2>/dev/null)"; '
    "grep -h usage_usec /sys/fs/cgroup/cpu.stat 2>/dev/null; "
    "grep -h '^inactive_file ' /sys/fs/cgroup/memory.stat 2>/dev/null; "
    "grep -h MemTotal /proc/meminfo"
)


def get_docker_client():
    """Obtiene un cliente Docker usando el socket montado."""
    try:
        return docker_sdk.from_env()
    except Exception as e:
        logger.error(f"No se pudo conectar a Docker: {e}")
        return None


def project_dir() -> Path | None:
    """Directorio del proyecto (docker-compose.yml + .env), si esta montado.

    El compose monta este directorio en el contenedor del backend usando la
    MISMA ruta absoluta que tiene en el host. Esa igualdad no es un capricho:
    Docker Compose graba la ruta de trabajo en las etiquetas del contenedor, y
    si el backend la viera bajo otra ruta, cada `docker compose up -d` lanzado
    desde el host detectaria una diferencia y recrearia Squid sin motivo.
    """
    raw = os.environ.get("PROJECT_DIR", "").strip()
    if not raw:
        return None
    base = Path(raw)
    return base if (base / "docker-compose.yml").is_file() else None


def compose_cmd() -> list[str] | None:
    """Devuelve el comando de Docker Compose disponible, o None si no lo hay."""
    if shutil.which("docker") is None:
        return None
    try:
        probe = subprocess.run(
            ["docker", "compose", "version"],
            capture_output=True, timeout=15,
        )
        if probe.returncode == 0:
            return ["docker", "compose"]
    except Exception:
        pass
    if shutil.which("docker-compose"):
        return ["docker-compose"]
    return None


def sync_env_port(new_port: str) -> tuple[bool, str]:
    """Deja PROXY_PORT del .env en sintonia con el puerto elegido en el panel.

    PROXY_PORT es el puerto que Docker publica hacia fuera, y es el unico sitio
    donde vive el puerto del proxy: Squid escucha siempre en un puerto interno
    fijo (INTERNAL_SQUID_PORT) contra el que se mapea. Antes el puerto estaba
    ademas en el squid.conf, y cuando las dos copias divergian Docker publicaba
    un puerto donde Squid ya no escuchaba: el proxy quedaba inalcanzable desde
    fuera y el contenedor seguia figurando como sano.

    La escritura es atomica (fichero temporal + rename) porque este .env
    contiene tambien la contrasena de la base de datos y la clave de firma de
    los JWT: una escritura a medias dejaria el sistema sin arrancar.
    """
    base = project_dir()
    if not base:
        return False, (
            "El directorio del proyecto no esta montado en el backend "
            "(variable PROJECT_DIR): no se puede sincronizar el .env."
        )

    from app.services.runtime.env_file import escribir_puerto

    return escribir_puerto(base / ".env", new_port)


class DockerRuntime(ProxyRuntime):
    """Controla el Squid que vive en el contenedor `SQUID_CONTAINER_NAME`."""

    name = "docker"

    # ------------------------------------------------------------------
    # Utilidades internas
    # ------------------------------------------------------------------
    def _container(self):
        client = get_docker_client()
        if not client:
            return None, "No se pudo conectar al daemon Docker"
        try:
            return client.containers.get(settings.SQUID_CONTAINER_NAME), ""
        except Exception as e:
            return None, f"No se encontro el contenedor de Squid: {e}"

    @staticmethod
    def _wait_until_running(container, timeout: int = 60) -> bool:
        """Espera a que el contenedor vuelva a estar en marcha tras un reinicio.

        Un `restart()` devuelve el control antes de que el proceso este listo, y
        cualquier exec lanzado mientras tanto falla con 409 "is restarting".
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                container.reload()
                if container.status == "running":
                    # Squid tarda un poco mas en abrir el puerto que el
                    # contenedor en pasar a "running".
                    time.sleep(2)
                    return True
            except Exception:
                pass
            time.sleep(1)
        return False

    # ------------------------------------------------------------------
    # Interfaz
    # ------------------------------------------------------------------
    def listen_port(self, desired_port: str) -> str:
        return INTERNAL_SQUID_PORT

    def sync_port_state(self, port: str) -> tuple[bool, str]:
        """El puerto vive tambien en el .env, que es quien alimenta el mapeo.

        Se sincroniza en cada aplicacion, no solo cuando el puerto cambia: asi
        una instalacion antigua o una edicion manual del fichero se corrigen
        solas en el siguiente «Aplicar cambios», en vez de quedar como una
        divergencia latente que solo se manifiesta al reiniciar la maquina.
        """
        return sync_env_port(port)

    def reconfigure(self) -> tuple[bool, str]:
        container, err = self._container()
        if not container:
            return False, err
        try:
            result = container.exec_run(["squid", "-k", "reconfigure"])
            output = result.output.decode("utf-8", errors="replace") if result.output else ""
        except Exception as e:
            logger.error(f"Error recargando Squid: {e}")
            return False, f"Error: {e}"

        if result.exit_code == 0:
            return True, "Squid reconfigurado correctamente"
        return False, f"Error (exit {result.exit_code}): {output}"

    def restart(self) -> tuple[bool, str]:
        container, err = self._container()
        if not container:
            return False, err
        try:
            container.restart(timeout=10)
            if not self._wait_until_running(container):
                return False, "Squid tarda en arrancar tras el reinicio"
            return True, "Squid reiniciado"
        except Exception as e:
            logger.error(f"Error reiniciando Squid: {e}")
            return False, f"Error: {e}"

    def parse_config(self, path: str) -> tuple[int, str]:
        container, err = self._container()
        if not container:
            raise RuntimeError(err)
        if container.status != "running":
            raise RuntimeError(
                "El contenedor de Squid no esta en ejecucion: no se puede validar"
            )
        result = container.exec_run(["squid", "-k", "parse", "-f", str(path)])
        output = result.output.decode("utf-8", errors="replace") if result.output else ""
        return result.exit_code, output

    def status(self) -> dict:
        status = {"running": False, "state": "unknown", "pid": None, "errors": []}
        container, err = self._container()
        if not container:
            status["errors"].append(err)
            return status
        try:
            status["running"] = container.status == "running"
            status["state"] = container.status
            container.reload()
            status["pid"] = container.attrs.get("State", {}).get("Pid")
        except Exception as e:
            status["errors"].append(str(e))
        return status

    def read_stats_raw(self) -> str:
        container, err = self._container()
        if not container:
            raise RuntimeError(err)
        return container.exec_run(["sh", "-c", STATS_CMD]).output.decode(
            "utf-8", errors="replace"
        )

    def verify_port(self, expected_port: str) -> tuple[bool, str]:
        """Comprueba que Docker publica de verdad el puerto que Squid escucha."""
        container, err = self._container()
        if not container:
            return False, err
        try:
            container.reload()
            bindings = container.attrs.get("HostConfig", {}).get("PortBindings") or {}
            published = {
                b.get("HostPort")
                for binds in bindings.values() if binds
                for b in binds
            }
        except Exception as e:
            return False, f"No se pudo comprobar el puerto publicado: {e}"

        if expected_port in published:
            return True, f"Docker publica el puerto {expected_port}"
        return False, (
            f"Squid escucha en el puerto {expected_port} pero Docker publica "
            f"{sorted(p for p in published if p) or 'ninguno'}: el proxy no sera "
            f"accesible desde fuera."
        )

    def apply_port(self, new_port: str) -> tuple[bool, str]:
        """Recrea el contenedor para que publique el puerto nuevo.

        Orden deliberado:
          1. Sincronizar el .env con el puerto de la BD.
          2. Recrear el contenedor con Docker Compose.
          3. Verificar que el puerto publicado es el esperado.

        El paso 1 va primero a proposito: aunque la recreacion falle, el .env
        queda correcto y el siguiente `docker compose up -d` deja el sistema
        bien. Al reves (recrear y luego escribir) una caida a medias dejaba una
        divergencia silenciosa entre lo que publica Docker y lo que escucha
        Squid.
        """
        # 1. El .env primero: es lo que hace que el cambio sobreviva a un
        #    `docker compose up -d` o a un reinicio de la maquina.
        env_ok, env_msg = sync_env_port(new_port)
        if not env_ok:
            logger.warning(f"No se pudo sincronizar el .env: {env_msg}")

        # 2. Recrear con Compose; el SDK queda de reserva para instalaciones
        #    donde el directorio del proyecto no este montado en el backend.
        ok, msg = self._recreate_with_compose(new_port)
        if not ok:
            logger.warning(f"Compose no pudo recrear Squid ({msg}); se recurre al SDK")
            ok, msg = self._recreate_with_sdk(new_port)
            if not ok:
                return False, msg

        # 3. Comprobar que el puerto quedo realmente publicado.
        port_ok, port_msg = self.verify_port(new_port)
        if not port_ok:
            return False, f"{msg}, pero {port_msg}"

        if not env_ok:
            return True, (
                f"{msg}, pero no se pudo actualizar el .env ({env_msg}): un "
                f"`docker compose up -d` podria devolver el puerto al valor viejo."
            )
        return True, f"{msg} ({env_msg})"

    # ------------------------------------------------------------------
    # Recreacion del contenedor
    # ------------------------------------------------------------------
    def _recreate_with_compose(self, new_port: str) -> tuple[bool, str]:
        """Recrea el contenedor de Squid con Docker Compose.

        Se prefiere a construirlo a mano con el SDK porque Compose aplica el
        docker-compose.yml entero: si manana el servicio gana una opcion nueva
        (capabilities, sysctls, dns, limites), se respeta sola. La version que
        copiaba campos del contenedor viejo uno a uno perdia en silencio todo lo
        que no estuviera en esa lista.
        """
        base = project_dir()
        if not base:
            return False, "El directorio del proyecto no esta montado (PROJECT_DIR)"

        compose = compose_cmd()
        if not compose:
            return False, "Docker Compose no esta disponible dentro del backend"

        # El nombre del proyecto se fija explicitamente: sin el, Compose lo
        # deduce del nombre del directorio y podria no coincidir con el de los
        # contenedores que ya existen.
        project = os.environ.get("COMPOSE_PROJECT_NAME", "").strip() or base.name

        # --no-deps es imprescindible, no una optimizacion: sin el, Compose
        # puede arrastrar a los servicios de los que Squid depende, y uno de
        # ellos es el propio backend, que es quien esta ejecutando este
        # comando. Se estaria matando a si mismo a mitad de la operacion.
        cmd = compose + [
            "--project-directory", str(base),
            "-p", project,
            "up", "-d", "--no-deps", "--force-recreate", SQUID_COMPOSE_SERVICE,
        ]

        try:
            result = subprocess.run(
                cmd, cwd=str(base), capture_output=True, text=True, timeout=180,
            )
        except subprocess.TimeoutExpired:
            return False, "Docker Compose tardo demasiado (180 s) en recrear Squid"
        except Exception as e:
            return False, f"No se pudo ejecutar Docker Compose: {e}"

        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            return False, f"Docker Compose fallo: {detail[-500:]}"

        return True, f"Contenedor recreado con Docker Compose en el puerto {new_port}"

    def _recreate_with_sdk(self, new_port: str) -> tuple[bool, str]:
        """Recrea el contenedor a mano con el SDK de Docker (camino de reserva).

        Solo se usa si Compose no esta disponible. Reconstruye el contenedor
        copiando la configuracion del anterior, asi que **solo conserva los
        campos que se copian aqui de forma explicita**: cualquier opcion que se
        anada al docker-compose.yml y no se refleje en esta lista se perderia al
        cambiar el puerto. Por eso el camino preferente es Compose.

        El contenedor anterior se renombra en lugar de borrarse: si la creacion
        del nuevo falla, se restaura y el proxy sigue funcionando.
        """
        try:
            client = get_docker_client()
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

            volumes = []
            for mount in old_config.get("Mounts", []):
                if mount["Type"] == "volume":
                    volumes.append(f"{mount['Name']}:{mount['Destination']}")
                elif mount["Type"] == "bind":
                    volumes.append(f"{mount['Source']}:{mount['Destination']}")

            net_settings = old_config.get("NetworkSettings", {}).get("Networks", {})
            network = list(net_settings.keys())[0] if net_settings else None

            # Conservar lo que define Compose, que antes se perdia.
            labels = old_config["Config"].get("Labels") or {}
            restart_policy = host_config.get("RestartPolicy") or {"Name": "unless-stopped"}
            healthcheck = old_config["Config"].get("Healthcheck")

            # Apartar el contenedor viejo sin destruirlo todavia.
            backup_name = f"{settings.SQUID_CONTAINER_NAME}-old-{int(time.time())}"
            old_container.stop(timeout=10)
            old_container.rename(backup_name)

            try:
                new_container = client.containers.create(
                    image=image,
                    name=settings.SQUID_CONTAINER_NAME,
                    environment=env,
                    # Puerto interno fijo, publicado en el que eligio el panel.
                    ports={f"{INTERNAL_SQUID_PORT}/tcp": int(new_port)},
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
                    return False, f"No se pudo recrear el contenedor ({e}). Se restauro el anterior."
                except Exception as rollback_error:
                    return False, (
                        f"No se pudo recrear el contenedor ({e}) y tampoco restaurar el "
                        f"anterior ({rollback_error}). Revisa con: docker ps -a"
                    )

            # El nuevo arranco: ya se puede retirar el viejo.
            try:
                old_container.remove(force=True)
            except Exception as e:
                logger.warning(f"El contenedor anterior no se pudo eliminar ({backup_name}): {e}")

            self._wait_until_running(new_container)

            from app.database import SessionLocal
            from app.services.squid_service import write_passwd_file

            db = SessionLocal()
            try:
                write_passwd_file(db)
                new_container.exec_run(["squid", "-k", "reconfigure"])
            finally:
                db.close()

            logger.info(f"Contenedor Squid recreado en puerto {new_port}")
            return True, f"Contenedor recreado en puerto {new_port} (usuarios regenerados)"
        except Exception as e:
            logger.error(f"Error recreando Squid con el SDK: {e}")
            return False, f"Error: {e}"
