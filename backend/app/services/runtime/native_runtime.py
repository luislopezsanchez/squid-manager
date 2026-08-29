"""Runtime de Squid cuando esta instalado en el propio sistema (systemd).

Pensado para el paquete `squid-openssl` de Debian/Ubuntu, que trae compiladas
las mismas opciones que la imagen del proyecto: OpenSSL, ssl-crtd, delay pools
y los helpers de autenticacion basica. El paquete `squid` a secas NO sirve: es
la variante GnuTLS, sin SSL bump ni generador de certificados.

Diferencias de fondo con el modo Docker, todas deliberadas:

- **El puerto vive en el squid.conf.** No hay mapeo que traducir, asi que Squid
  escucha directamente en el puerto que elige el panel y todo el trabajo de
  recrear un contenedor desaparece: cambiar de puerto es reescribir el fichero
  y reiniciar.
- **El trafico se mide del host entero**, no de una interfaz virtual dedicada.
  En un equipo que hace de proxy y poco mas la diferencia es despreciable, pero
  conviene saberlo: si la maquina hace otras cosas, su trafico tambien cuenta.
- **Las rutas de cgroup son las del servicio**, no las de la raiz del
  contenedor.
"""

import logging
import os
import shutil
import subprocess
import time

from app.config import settings

from .base import ProxyRuntime

logger = logging.getLogger(__name__)

# Rutas absolutas a proposito. Es la misma leccion que dejo el fallo de
# logrotate: bajo un PATH reducido (cron, o una unidad de systemd sin PATH
# heredado) invocar `squid` por su nombre falla con "not found", y si ese fallo
# se traga se convierte en una averia silenciosa.
SQUID_BINARIES = ("/usr/sbin/squid", "/usr/local/sbin/squid", "/usr/bin/squid")
SYSTEMCTL_BINARIES = ("/usr/bin/systemctl", "/bin/systemctl")

# Estados de socket en /proc/net/tcp: 0A es LISTEN.
_TCP_LISTEN = "0A"

# Donde mira el sistema quien escucha. Se declara aparte para poder sustituirlo
# en las pruebas.
PROC_TCP = ("/proc/net/tcp", "/proc/net/tcp6")


def _find(candidates: tuple[str, ...], nombre: str) -> str | None:
    for ruta in candidates:
        if os.path.isfile(ruta) and os.access(ruta, os.X_OK):
            return ruta
    return shutil.which(nombre)


def _sudo_prefix() -> list[str]:
    """Prefijo para elevar privilegios, vacio si ya somos root.

    El backend nativo corre con su propio usuario y un sudoers estrecho que
    solo le permite recargar y reiniciar Squid. Si alguien lo despliega como
    root, sudo sobra y se omite.
    """
    try:
        if os.geteuid() == 0:
            return []
    except AttributeError:  # pragma: no cover - Windows, solo en desarrollo
        return []
    # -n: nunca preguntar contrasena. Si el sudoers no esta puesto preferimos
    # un fallo inmediato y legible a un proceso colgado esperando una entrada
    # que nadie va a escribir.
    return ["sudo", "-n"]


class NativeRuntime(ProxyRuntime):
    """Controla el Squid instalado en el sistema mediante systemd."""

    name = "native"

    def __init__(self) -> None:
        self.squid = _find(SQUID_BINARIES, "squid")
        self.systemctl = _find(SYSTEMCTL_BINARIES, "systemctl")
        self.service = (settings.NATIVE_SQUID_SERVICE or "squid").strip()
        self.config_path = settings.SQUID_CONFIG_PATH
        if not self.squid:
            logger.error(
                "No se encontro el binario de Squid. Instala el paquete "
                "squid-openssl (la variante 'squid' a secas no trae SSL bump)."
            )
        if not self.systemctl:
            logger.error("No se encontro systemctl: no se podra reiniciar Squid.")

    # ------------------------------------------------------------------
    # Utilidades internas
    # ------------------------------------------------------------------
    def _run(self, cmd: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

    def _squid_cmd(self, *args: str) -> list[str]:
        return _sudo_prefix() + [self.squid, "-f", self.config_path, *args]

    def _systemctl_cmd(self, *args: str) -> list[str]:
        return _sudo_prefix() + [self.systemctl, *args]

    @staticmethod
    def _listening_ports(ficheros: tuple[str, ...] = PROC_TCP) -> set[int]:
        """Puertos TCP en escucha, leidos de /proc.

        Se lee /proc directamente en lugar de invocar `ss` o `netstat` para no
        depender de que esten instalados: en una instalacion minima puede que
        no lo esten, y el diagnostico fallaria justo cuando hace falta.

        El parametro existe para poder probar el analisis con ficheros de
        ejemplo, no para cambiar de sitio en produccion.
        """
        puertos: set[int] = set()
        for fichero in ficheros:
            try:
                with open(fichero) as f:
                    next(f, None)  # cabecera
                    for linea in f:
                        campos = linea.split()
                        if len(campos) < 4 or campos[3] != _TCP_LISTEN:
                            continue
                        _, _, puerto_hex = campos[1].rpartition(":")
                        try:
                            puertos.add(int(puerto_hex, 16))
                        except ValueError:
                            continue
            except (OSError, StopIteration):
                continue
        return puertos

    def _service_state(self) -> tuple[str, int | None]:
        """(ActiveState, MainPID) del servicio, segun systemd."""
        if not self.systemctl:
            return "unknown", None
        try:
            result = self._run(
                [self.systemctl, "show", self.service, "-p", "ActiveState", "-p", "MainPID"],
                timeout=15,
            )
        except Exception as e:
            logger.error(f"No se pudo consultar el estado de {self.service}: {e}")
            return "unknown", None

        estado, pid = "unknown", None
        for linea in (result.stdout or "").splitlines():
            clave, _, valor = linea.partition("=")
            if clave == "ActiveState":
                estado = valor.strip() or "unknown"
            elif clave == "MainPID":
                try:
                    pid = int(valor.strip()) or None
                except ValueError:
                    pid = None
        return estado, pid

    def _wait_until_active(self, timeout: int = 60) -> bool:
        """Espera a que el servicio quede activo tras un reinicio."""
        limite = time.time() + timeout
        while time.time() < limite:
            estado, _ = self._service_state()
            if estado == "active":
                # Igual que en Docker: activo no significa que el puerto ya
                # este abierto. Squid tarda un poco mas.
                time.sleep(2)
                return True
            if estado == "failed":
                return False
            time.sleep(1)
        return False

    def _cgroup_dir(self) -> str | None:
        """Directorio de cgroup v2 del servicio, si existe."""
        candidatos = (
            f"/sys/fs/cgroup/system.slice/{self.service}.service",
            f"/sys/fs/cgroup/system.slice/system-{self.service}.slice",
        )
        for ruta in candidatos:
            if os.path.isdir(ruta):
                return ruta
        return None

    # ------------------------------------------------------------------
    # Interfaz
    # ------------------------------------------------------------------
    def listen_port(self, desired_port: str) -> str:
        # Sin mapeo de por medio: Squid escucha donde diga el panel.
        return desired_port

    def sync_port_state(self, port: str) -> tuple[bool, str]:
        # El puerto solo vive en el squid.conf, que se acaba de escribir: no
        # hay una segunda copia que pueda quedar desincronizada.
        return True, "el puerto vive solo en el squid.conf"

    def reconfigure(self) -> tuple[bool, str]:
        if not self.squid:
            return False, "No se encontro el binario de Squid en el sistema"
        try:
            result = self._run(self._squid_cmd("-k", "reconfigure"))
        except Exception as e:
            logger.error(f"Error recargando Squid: {e}")
            return False, f"Error: {e}"

        salida = ((result.stderr or "") + (result.stdout or "")).strip()
        if result.returncode == 0:
            return True, "Squid reconfigurado correctamente"
        return False, f"Error (exit {result.returncode}): {salida}"

    def restart(self) -> tuple[bool, str]:
        if not self.systemctl:
            return False, "No se encontro systemctl: no se puede reiniciar Squid"
        try:
            result = self._run(self._systemctl_cmd("restart", self.service), timeout=120)
        except Exception as e:
            logger.error(f"Error reiniciando Squid: {e}")
            return False, f"Error: {e}"

        if result.returncode != 0:
            detalle = ((result.stderr or "") + (result.stdout or "")).strip()
            return False, f"systemctl restart {self.service} fallo: {detalle[-500:]}"

        if not self._wait_until_active():
            return False, f"{self.service} no llego a quedar activo tras el reinicio"
        return True, "Squid reiniciado"

    def parse_config(self, path: str) -> tuple[int, str]:
        if not self.squid:
            raise RuntimeError(
                "No se encontro el binario de Squid: no se puede validar la "
                "configuracion. Instala el paquete squid-openssl."
            )
        result = self._run(_sudo_prefix() + [self.squid, "-k", "parse", "-f", str(path)])
        # Squid escribe el resultado del parse por stderr; se juntan los dos
        # flujos para que quien analiza la salida no dependa de cual usa.
        salida = (result.stderr or "") + (result.stdout or "")
        return result.returncode, salida

    def status(self) -> dict:
        estado, pid = self._service_state()
        status = {
            "running": estado == "active",
            "state": estado,
            "pid": pid,
            "errors": [],
        }
        if estado == "unknown":
            status["errors"].append(
                f"No se pudo determinar el estado del servicio {self.service}"
            )
        return status

    def read_stats_raw(self) -> str:
        """Contadores del host y del cgroup del servicio, en el formato comun.

        Se construye el mismo texto etiquetado que produce el modo Docker para
        que el analizador de metricas sea identico en los dos despliegues.
        """
        partes: list[str] = []
        try:
            with open("/proc/net/dev") as f:
                partes.append(f.read())
        except OSError as e:
            raise RuntimeError(f"No se pudo leer /proc/net/dev: {e}")

        partes.append("#CG#")

        cgroup = self._cgroup_dir()

        def _leer(ruta: str) -> str:
            try:
                with open(ruta) as f:
                    return f.read().strip()
            except OSError:
                return ""

        if cgroup:
            partes.append(f"memcur {_leer(os.path.join(cgroup, 'memory.current'))}")
            # Un servicio de systemd normalmente no tiene tope de memoria y
            # aqui pone "max": no es un numero, se ignora y se cae a la RAM
            # total del equipo, que es justo lo que se quiere mostrar.
            partes.append(f"memmax {_leer(os.path.join(cgroup, 'memory.max'))}")
            for linea in _leer(os.path.join(cgroup, "cpu.stat")).splitlines():
                if linea.startswith("usage_usec"):
                    partes.append(linea)
            for linea in _leer(os.path.join(cgroup, "memory.stat")).splitlines():
                if linea.startswith("inactive_file "):
                    partes.append(linea)

        for linea in _leer("/proc/meminfo").splitlines():
            if linea.startswith("MemTotal"):
                partes.append(linea)
                break

        return "\n".join(partes)

    def verify_port(self, expected_port: str) -> tuple[bool, str]:
        """Comprueba que hay algo escuchando de verdad en ese puerto."""
        try:
            puerto = int(str(expected_port).strip())
        except (TypeError, ValueError):
            return False, f"El puerto configurado no es un numero: '{expected_port}'"

        if puerto in self._listening_ports():
            return True, f"Squid escucha en el puerto {puerto}"

        estado, _ = self._service_state()
        return False, (
            f"Nadie escucha en el puerto {puerto} (servicio {self.service}: "
            f"{estado}): el proxy no sera accesible."
        )

    def apply_port(self, new_port: str) -> tuple[bool, str]:
        """Hace efectivo el puerto nuevo reiniciando el servicio.

        El puerto ya esta escrito en el squid.conf que se acaba de generar, asi
        que no hay nada que sincronizar en ningun otro sitio. Un `reconfigure`
        no basta: cambiar `http_port` exige reiniciar.
        """
        ok, msg = self.restart()
        if not ok:
            return False, msg

        port_ok, port_msg = self.verify_port(new_port)
        if not port_ok:
            return False, f"{msg}, pero {port_msg}"
        return True, f"Squid reiniciado en el puerto {new_port}"
