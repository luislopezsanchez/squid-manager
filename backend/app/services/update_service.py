"""Comprobación y aplicación de actualizaciones de SquidManager, consultando
el repositorio de GitHub del proyecto.

Diseño deliberado, no accidental -léase antes de tocar este archivo-:

- **Solo instalación nativa.** En Docker, el contenedor del backend no puede
  reconstruirse ni reiniciar a sus hermanos sin el socket de Docker montado
  (el mismo riesgo, ya activo y ya anotado, que evitamos sumar aquí). Cada
  llamada de este servicio comprueba `settings.DEPLOY_MODE == "native"`
  antes de hacer nada.

- **La web nunca ejecuta nada con privilegios.** Este proceso corre con el
  mismo usuario restringido de siempre (`squidmgr`, sin sudo salvo 4 líneas
  fijas en /etc/sudoers.d/squidmanager). Todo lo que hace esta capa es leer
  GitHub (sin credenciales, solo tráfico saliente) y escribir un archivo de
  estado. La única llamada con `sudo` invoca un script fijo, sin argumentos
  variables, que ni siquiera confía en haber sido invocado con legitimidad:
  vuelve a comprobar por su cuenta si corresponde actualizar antes de tocar
  nada -ver `autoupdate-check.sh`-. Aprobar una actualización "para ahora"
  solo adelanta cuándo ese script se fija si debe actuar, nunca le dice qué
  hacer.

- **El estado vive en un archivo, no en la base de datos.** El script que
  aplica la actualización corre como root, sin las credenciales de Postgres
  del backend (que además son deliberadamente no-superusuario). Depender de
  la base de datos para esto acopla el mecanismo que arregla el sistema a
  una pieza (Postgres) que podría ser justo la que está fallando. Un
  archivo JSON, con escritura atómica (temporal + rename), es lo mínimo que
  hace falta y sobrevive a cualquier problema de la base.
"""

import json
import logging
import os
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

import httpx

from app.config import settings
from app.database import SessionLocal
from app.models.update_config import UpdateConfig
from app.services.runtime.native_runtime import _sudo_prefix
from app.utils import utcnow

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
ESTADO_PATH = BACKEND_DIR / ".update_state.json"

REPO = "luislopezsanchez/squid-manager"
GITHUB_API = "https://api.github.com"

# Script fijo, sin argumentos: es la única orden que /etc/sudoers.d/squidmanager
# le permite correr como root a este proceso. Nunca cambia entre versiones a
# propósito -si algún día necesita parámetros, deben ir en el archivo de
# estado que el propio script lee, jamás en la línea de sudo-.
SCRIPT_TRIGGER = "/usr/local/lib/squidmanager/autoupdate-check.sh"

# Unidad transient que lanza ese script para la actualización real -ver
# autoupdate-check.sh-, usada aquí solo para poder mostrar "en curso" sin
# esperar al próximo tic del temporizador.
UNIDAD_APLICACION = "squidmanager-autoupdate-run"


class UpdateServiceError(Exception):
    """Error al comprobar o gestionar una actualización, para mostrar al admin."""


def _iso(dt: datetime) -> str:
    """ISO 8601 con sufijo Z explícito: las fechas del proyecto son naive-UTC

    (ver app/utils/timeutil.py), y sin marca de zona un `date -d` de bash
    -que es quien lee este archivo del lado del script privilegiado- las
    interpretaría como hora LOCAL del servidor, no UTC. Ambiguo incluso
    aunque hoy coincidan (todo el parque corre en UTC): mejor explícito.
    """
    return dt.isoformat() + "Z"


def _es_nativo() -> bool:
    return settings.DEPLOY_MODE.strip().lower() == "native"


def _rama_actual() -> str:
    """Rama que este checkout tiene desactivada -mismo truco que ya usa

    main.py para el commit desplegado: `git branch --show-current` sobre el
    propio repo, sin persistir nada nuevo en .env.
    """
    try:
        r = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=BACKEND_DIR.parent, capture_output=True, text=True, timeout=3,
        )
        rama = r.stdout.strip()
        return rama if r.returncode == 0 and rama else "main"
    except Exception:
        return "main"


def _commit_actual() -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=BACKEND_DIR.parent, capture_output=True, text=True, timeout=3,
        )
        return r.stdout.strip() if r.returncode == 0 else ""
    except Exception:
        return ""


def _estado_por_defecto() -> dict:
    return {
        "check": {
            "last_checked_at": None,
            "local_commit": None,
            "remote_commit": None,
            "update_available": False,
            "commits": [],
            "last_check_error": None,
        },
        "request": {
            "approved": False,
            "scheduled_at": None,
            "requested_by": None,
            "requested_at": None,
        },
        "apply": {
            "status": None,  # None | "running" | "ok" | "error"
            "started_at": None,
            "finished_at": None,
            "commit": None,
            "log_tail": None,
        },
    }


def leer_estado() -> dict:
    if not ESTADO_PATH.exists():
        return _estado_por_defecto()
    try:
        datos = json.loads(ESTADO_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _estado_por_defecto()
    # Completa con los valores por defecto cualquier clave que falte -por
    # ejemplo, tras sumar un campo nuevo en una versión futura- en vez de
    # fallar con un KeyError.
    base = _estado_por_defecto()
    for seccion in base:
        base[seccion].update(datos.get(seccion, {}))
    return base


def _escribir_estado(estado: dict) -> None:
    """Escritura atómica: temporal + rename, mismo patrón que ya usa

    consolidate-monthly-logs.sh para no dejar el archivo a medias si el
    proceso se corta a mitad de escritura.
    """
    tmp = ESTADO_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(estado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, ESTADO_PATH)


def _unidad_en_curso() -> bool:
    """Consulta de solo lectura -`systemctl is-active` no requiere sudo-,

    para poder mostrar "en curso" en el panel sin esperar al próximo tic
    del temporizador que confirma el resultado final.
    """
    try:
        r = subprocess.run(
            ["systemctl", "is-active", UNIDAD_APLICACION],
            capture_output=True, text=True, timeout=3,
        )
        return r.stdout.strip() == "active"
    except Exception:
        return False


# Si una aprobación sigue esperando bastante más de lo que el temporizador
# debería tardar en notarla (1 minuto, con margen), algo no anda bien -el
# temporizador caído, sudoers roto, etc.-. No se cancela sola (podría ser
# solo un tic lento) pero sí se avisa, en vez de dejar "programada" para
# siempre sin ninguna pista de que algo falla.
_MARGEN_DEMORA_SEGUNDOS = 3 * 60


def estado_actual() -> dict:
    estado = leer_estado()
    if estado["apply"]["status"] == "running" and not _unidad_en_curso():
        # El temporizador (cada 1 min) va a terminar de confirmar el
        # resultado igual, pero si la unidad ya no está activa el dato ya no
        # sirve como "en curso" -mejor decir "verificando" que mentir con un
        # estado viejo mientras se espera el próximo tic.
        estado["apply"] = dict(estado["apply"], status="verificando")

    programado = estado["request"].get("scheduled_at")
    if estado["request"].get("approved") and programado and estado["apply"]["status"] not in ("running", "verificando"):
        try:
            vencido_hace = (utcnow() - datetime.fromisoformat(programado.replace("Z", ""))).total_seconds()
            estado["request"]["atrasada"] = vencido_hace > _MARGEN_DEMORA_SEGUNDOS
        except ValueError:
            estado["request"]["atrasada"] = False
    else:
        estado["request"]["atrasada"] = False

    return estado


def comprobar_actualizacion() -> dict:
    """Consulta GitHub y actualiza la sección "check" del estado.

    Sin privilegios, sin credenciales: la API de commits/compare de un repo
    público no las necesita. Falla de forma silenciosa hacia el estado (se
    guarda el error, no se lanza al llamador salvo que sea DEPLOY_MODE
    distinto de nativo) porque la puede llamar tanto un admin a mano como el
    hilo de fondo cada varias horas, y una falla de red pasajera no debería
    verse como un error del panel.
    """
    if not _es_nativo():
        raise UpdateServiceError(
            "La comprobación de actualizaciones solo está disponible en instalación nativa."
        )

    estado = leer_estado()
    local = _commit_actual()
    rama = _rama_actual()

    try:
        with httpx.Client(timeout=15, headers={"Accept": "application/vnd.github+json"}) as cliente:
            r = cliente.get(f"{GITHUB_API}/repos/{REPO}/commits/{rama}")
            r.raise_for_status()
            remoto = r.json()["sha"]

            commits = []
            if local and remoto and local != remoto:
                cmp = cliente.get(f"{GITHUB_API}/repos/{REPO}/compare/{local}...{remoto}")
                if cmp.status_code == 200:
                    for c in cmp.json().get("commits", [])[-30:]:
                        mensaje = c.get("commit", {}).get("message", "").split("\n")[0]
                        commits.append({"sha": c.get("sha", "")[:7], "message": mensaje})
                    commits.reverse()  # mas reciente primero

        estado["check"] = {
            "last_checked_at": _iso(utcnow()),
            "local_commit": local[:7] if local else None,
            "remote_commit": remoto[:7] if remoto else None,
            "update_available": bool(local and remoto and local != remoto),
            "commits": commits,
            "last_check_error": None,
        }
    except httpx.HTTPError as e:
        estado["check"]["last_checked_at"] = _iso(utcnow())
        estado["check"]["last_check_error"] = str(e)
        logger.warning(f"No se pudo comprobar actualizaciones en GitHub: {e}")

    _escribir_estado(estado)
    return estado



# Margen de tolerancia para "en el pasado": "ahora" se calcula en el
# frontend, viaja por la red y se procesa acá unos milisegundos (a veces
# uno o dos segundos) más tarde -sin este margen, la propia opción "ahora"
# se rechazaría a sí misma por llegar ya "vencida"-. Cualquier fecha más
# vieja que esto sí es un error real del usuario (una fecha pasada de
# verdad), no un artefacto de la latencia de la petición.
_TOLERANCIA_PASADO_SEGUNDOS = 30


def aprobar_actualizacion(admin_username: str, programado_para: datetime | None) -> dict:
    """Deja aprobada una actualización, para ahora (`programado_para=None`)

    o para una fecha/hora futura. Nunca ejecuta nada con privilegios por sí
    misma: siempre dispara -con el único comando fijo que permite sudoers-
    el script que confirma la condición y recién ahí actúa; si la fecha es
    futura, ese disparo inmediato no hace nada todavía (el script vuelve a
    comprobar por su cuenta), pero evita el peor caso de esperar hasta el
    próximo tic del temporizador para una hora ya vencida o a punto de
    cumplirse.
    """
    if not _es_nativo():
        raise UpdateServiceError("La actualización solo está disponible en instalación nativa.")

    estado = leer_estado()
    if estado["apply"]["status"] in ("running", "verificando"):
        raise UpdateServiceError("Ya hay una actualización en curso.")

    ahora = utcnow()
    if programado_para is not None:
        diferencia = (ahora - programado_para).total_seconds()
        if diferencia > _TOLERANCIA_PASADO_SEGUNDOS:
            raise UpdateServiceError(
                "La fecha y hora elegidas ya pasaron. Elegí un momento futuro, o dejalo "
                "en blanco para aplicar ahora mismo."
            )

    estado["request"] = {
        "approved": True,
        "scheduled_at": _iso(programado_para or ahora),
        "requested_by": admin_username,
        "requested_at": _iso(ahora),
    }
    _escribir_estado(estado)

    # Siempre se dispara, sea "ahora" o programada: si programado_para ya
    # está vencida o muy próxima, esto ahorra hasta 1 minuto de espera del
    # temporizador; si es una fecha realmente futura, el script confirma
    # que todavía no corresponde y no hace nada -disparar de más nunca
    # rompe nada, ver autoupdate-check.sh-.
    _disparar_verificacion_inmediata()

    return estado


def cancelar_actualizacion() -> dict:
    estado = leer_estado()
    if estado["apply"]["status"] in ("running", "verificando"):
        raise UpdateServiceError("La actualización ya está en curso; no se puede cancelar.")
    estado["request"] = _estado_por_defecto()["request"]
    _escribir_estado(estado)
    return estado


def _disparar_verificacion_inmediata() -> None:
    """Adelanta el chequeo del script privilegiado, en vez de esperar hasta

    1 minuto al próximo tic del temporizador. `sudo -n` (sin pedir
    contraseña interactiva): si la regla de sudoers no está o no coincide
    exactamente, falla rápido en vez de colgarse esperando una contraseña
    que nadie va a escribir.
    """
    try:
        # Mismo prefijo que ya usa native_runtime.py para hablar con Squid:
        # "sudo -n", vacío si este proceso ya es root (despliegue atípico).
        r = subprocess.run(
            _sudo_prefix() + [SCRIPT_TRIGGER],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode != 0:
            logger.warning(
                f"No se pudo disparar la actualización inmediata (sudo devolvió {r.returncode}): "
                f"{r.stderr.strip()}. El temporizador la aplicará de todos modos en el próximo minuto."
            )
    except Exception as e:
        logger.warning(f"No se pudo disparar la actualización inmediata: {e}. El temporizador la aplicará igual.")


# Cada 6 horas: frecuente para notar una actualización el mismo día que se
# publica, sin martillar la API de GitHub -pública, sin autenticar, con un
# límite de 60 peticiones/hora POR IP que comparten todas las instalaciones
# detrás del mismo NAT-.
_INTERVALO_COMPROBACION = 6 * 60 * 60
# Primera comprobación a poco de arrancar, no inmediata: si el backend
# arranca en un boot con la red todavía inicializando, mejor no sumar un
# fallo de DNS al arranque.
_PRIMERA_ESPERA = 60


def _checker_loop():
    time.sleep(_PRIMERA_ESPERA)
    while True:
        try:
            db = SessionLocal()
            try:
                config = db.query(UpdateConfig).first()
            finally:
                db.close()

            if _es_nativo() and (not config or config.check_enabled):
                comprobar_actualizacion()
        except Exception as e:
            logger.error(f"Error comprobando actualizaciones de SquidManager: {e}")

        time.sleep(_INTERVALO_COMPROBACION)


def start_update_checker():
    """Arranca el hilo de fondo una sola vez, al iniciar el backend.

    Mismo patrón que start_syslog_forwarder(): hilo daemon, el propio bucle
    relee la configuración en cada vuelta.
    """
    thread = threading.Thread(target=_checker_loop, name="update-checker", daemon=True)
    thread.start()
