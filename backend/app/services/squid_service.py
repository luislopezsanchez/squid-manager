"""Servicio para controlar el contenedor Squid y generar archivos auxiliares."""

import os
import re
import shutil
import subprocess
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

# Nombre del servicio Squid dentro del docker-compose.yml (distinto del nombre
# del contenedor, que es SQUID_CONTAINER_NAME).
SQUID_COMPOSE_SERVICE = "squid"

# Puerto interno fijo en el que Squid escucha dentro del contenedor. El puerto
# que se elige en el panel es el que Docker publica hacia fuera y se mapea
# contra este.
from app.services.config_generator import INTERNAL_SQUID_PORT  # noqa: E402

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

    # Quedarse con las líneas de error, que es lo accionable.
    errors = [
        line for line in output.splitlines()
        if "ERROR" in line or "FATAL" in line or "aborting" in line.lower()
    ]

    # No basta con mirar el código de salida. Ante una directiva obsoleta o
    # desconocida, `squid -k parse` avisa por ERROR pero termina con éxito: la
    # configuración se daba por buena y la directiva quedaba en el fichero sin
    # hacer nada, con el único rastro de una línea en un log que nadie mira.
    # Así se coló un `dns_v4_first` que Squid 6 ya no soporta.
    if result.exit_code != 0 or errors:
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


def _project_dir() -> Path | None:
    """Directorio del proyecto (docker-compose.yml + .env), si está montado.

    El compose monta este directorio en el contenedor del backend usando la
    MISMA ruta absoluta que tiene en el host. Esa igualdad no es un capricho:
    Docker Compose graba la ruta de trabajo en las etiquetas del contenedor, y
    si el backend la viera bajo otra ruta, cada `docker compose up -d` lanzado
    desde el host detectaría una diferencia y recrearía Squid sin motivo.
    """
    raw = os.environ.get("PROJECT_DIR", "").strip()
    if not raw:
        return None
    base = Path(raw)
    return base if (base / "docker-compose.yml").is_file() else None


def _compose_cmd() -> list[str] | None:
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
    """Deja PROXY_PORT del .env en sintonía con el puerto elegido en el panel.

    PROXY_PORT es el puerto que Docker publica hacia fuera, y es el único sitio
    donde vive el puerto del proxy: Squid escucha siempre en un puerto interno
    fijo (INTERNAL_SQUID_PORT) contra el que se mapea. Antes el puerto estaba
    además en el squid.conf, y cuando las dos copias divergían Docker publicaba
    un puerto donde Squid ya no escuchaba: el proxy quedaba inalcanzable desde
    fuera y el contenedor seguía figurando como sano.

    La escritura es atómica (fichero temporal + rename) porque este .env
    contiene también la contraseña de la base de datos y la clave de firma de
    los JWT: una escritura a medias dejaría el sistema sin arrancar.
    """
    base = _project_dir()
    if not base:
        return False, (
            "El directorio del proyecto no está montado en el backend "
            "(variable PROJECT_DIR): no se puede sincronizar el .env."
        )

    env_file = base / ".env"
    if not env_file.is_file():
        return False, f"No se encontró el fichero {env_file}"

    try:
        original = env_file.read_text()
    except Exception as e:
        return False, f"No se pudo leer el .env: {e}"

    lines = original.splitlines()
    found = False

    for i, line in enumerate(lines):
        # Solo asignaciones reales: una línea comentada que mencione la
        # variable debe quedarse como está.
        if re.match(r"^\s*PROXY_PORT\s*=", line):
            lines[i] = f"PROXY_PORT={new_port}"
            found = True

    if not found:
        lines.append(f"PROXY_PORT={new_port}")

    updated = "\n".join(lines) + "\n"
    if updated == original:
        return True, "El .env ya estaba sincronizado"

    tmp = env_file.with_name(f".env.tmp-{os.getpid()}")
    try:
        # Conservar los permisos del original: lleva secretos.
        mode = env_file.stat().st_mode & 0o777
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
        with os.fdopen(fd, "w") as f:
            f.write(updated)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, env_file)
    except Exception as e:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
        return False, f"No se pudo escribir el .env: {e}"

    logger.info(f".env sincronizado: PROXY_PORT = {new_port}")
    return True, f".env actualizado a {new_port}"


def _recreate_with_compose(new_port: str) -> tuple[bool, str]:
    """Recrea el contenedor de Squid con Docker Compose.

    Se prefiere a construirlo a mano con el SDK porque Compose aplica el
    docker-compose.yml entero: si mañana el servicio gana una opción nueva
    (capabilities, sysctls, dns, límites), se respeta sola. La versión que
    copiaba campos del contenedor viejo uno a uno perdía en silencio todo lo
    que no estuviera en esa lista.
    """
    base = _project_dir()
    if not base:
        return False, "El directorio del proyecto no está montado (PROJECT_DIR)"

    compose = _compose_cmd()
    if not compose:
        return False, "Docker Compose no está disponible dentro del backend"

    # El nombre del proyecto se fija explícitamente: sin él, Compose lo deduce
    # del nombre del directorio y podría no coincidir con el de los
    # contenedores que ya existen.
    project = os.environ.get("COMPOSE_PROJECT_NAME", "").strip() or base.name

    # --no-deps es imprescindible, no una optimización: sin él, Compose puede
    # arrastrar a los servicios de los que Squid depende, y uno de ellos es el
    # propio backend, que es quien está ejecutando este comando. Se estaría
    # matando a sí mismo a mitad de la operación.
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
        return False, "Docker Compose tardó demasiado (180 s) en recrear Squid"
    except Exception as e:
        return False, f"No se pudo ejecutar Docker Compose: {e}"

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        return False, f"Docker Compose falló: {detail[-500:]}"

    return True, f"Contenedor recreado con Docker Compose en el puerto {new_port}"


def verify_published_port(expected_port: str) -> tuple[bool, str]:
    """Comprueba que Docker publica de verdad el puerto que Squid escucha.

    Es la comprobación que faltaba: hasta ahora un desajuste entre el puerto
    publicado y el de escucha no lo detectaba nadie, porque el contenedor
    seguía estando «sano» (el proceso vivía) mientras el proxy era
    inalcanzable desde fuera.
    """
    try:
        client = _get_docker_client()
        if not client:
            return False, "No se pudo conectar a Docker para verificar el puerto"
        container = client.containers.get(settings.SQUID_CONTAINER_NAME)
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
        f"{sorted(p for p in published if p) or 'ninguno'}: el proxy no será "
        f"accesible desde fuera."
    )


def restart_squid() -> tuple[bool, str]:
    """Recrea el contenedor Squid con el puerto que indica la base de datos.

    Orden deliberado:
      1. Sincronizar el .env con el puerto de la BD.
      2. Recrear el contenedor con Docker Compose.
      3. Verificar que el puerto publicado es el esperado.

    El paso 1 va primero a propósito: aunque la recreación falle, el .env queda
    correcto y el siguiente `docker compose up -d` deja el sistema bien. Al
    revés (recrear y luego escribir) una caída a medias dejaba una divergencia
    silenciosa entre lo que publica Docker y lo que escucha Squid.
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

        # 1. El .env primero: es lo que hace que el cambio sobreviva a un
        #    `docker compose up -d` o a un reinicio de la máquina.
        env_ok, env_msg = sync_env_port(new_port)
        if not env_ok:
            logger.warning(f"No se pudo sincronizar el .env: {env_msg}")

        # 2. Recrear con Compose; el SDK queda de reserva para instalaciones
        #    donde el directorio del proyecto no esté montado en el backend.
        ok, msg = _recreate_with_compose(new_port)
        if not ok:
            logger.warning(f"Compose no pudo recrear Squid ({msg}); se recurre al SDK")
            ok, msg = _recreate_with_sdk(new_port)
            if not ok:
                return False, msg

        # 3. Comprobar que el puerto quedó realmente publicado.
        port_ok, port_msg = verify_published_port(new_port)
        if not port_ok:
            return False, f"{msg}, pero {port_msg}"

        if not env_ok:
            return True, (
                f"{msg}, pero no se pudo actualizar el .env ({env_msg}): un "
                f"`docker compose up -d` podría devolver el puerto al valor viejo."
            )
        return True, f"{msg} ({env_msg})"
    except Exception as e:
        logger.error(f"Error recreando Squid: {e}")
        return False, f"Error: {e}"


def _recreate_with_sdk(new_port: str) -> tuple[bool, str]:
    """Recrea el contenedor a mano con el SDK de Docker (camino de reserva).

    Solo se usa si Compose no está disponible. Reconstruye el contenedor
    copiando la configuración del anterior, así que **solo conserva los campos
    que se copian aquí de forma explícita**: cualquier opción que se añada al
    docker-compose.yml y no se refleje en esta lista se perdería al cambiar el
    puerto. Por eso el camino preferente es Compose.

    El contenedor anterior se renombra en lugar de borrarse: si la creación del
    nuevo falla, se restaura y el proxy sigue funcionando.
    """
    try:
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
                # Puerto interno fijo, publicado en el que eligió el panel.
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

        from app.database import SessionLocal

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

    # 2. El puerto elegido en el panel es el que Docker tiene que publicar.
    #    Ya no se deduce del squid.conf —donde ahora hay una constante— sino
    #    de la base de datos, que es donde lo deja el panel.
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
        env_ok, env_msg = sync_env_port(desired_port)
        if not env_ok:
            logger.warning(f"No se pudo sincronizar el .env: {env_msg}")

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
