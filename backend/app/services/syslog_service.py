"""Reenvío opcional de logs de acceso a un syslog externo.

Canal apagado por defecto (SyslogConfig.enabled=False). Cuando se activa, un
hilo de fondo sigue el access.log igual que `tail -f` (sin `docker exec`: el
backend ya monta el mismo volumen que Squid) y reenvía cada línea nueva al
destino configurado, con el formato de mensaje syslog (RFC 3164 o RFC 5424)
y el cuerpo (línea nativa de Squid o el mismo JSON de la exportación NDJSON)
que se hayan elegido.
"""

import json
import logging
import socket
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from app.database import SessionLocal
from app.models.syslog_config import SyslogConfig
from app.services.log_service import ACCESS_LOG_PATH, parse_line

logger = logging.getLogger(__name__)

_STATE_FILE = "/tmp/squidmgr_syslog_offset.json"
_POLL_SECONDS = 2.0

_FACILITY_CODES = {
    "kern": 0, "user": 1, "mail": 2, "daemon": 3, "auth": 4, "syslog": 5,
    "lpr": 6, "news": 7, "uucp": 8, "cron": 9, "authpriv": 10, "ftp": 11,
    "local0": 16, "local1": 17, "local2": 18, "local3": 19,
    "local4": 20, "local5": 21, "local6": 22, "local7": 23,
}
_SEVERITY_INFO = 6  # Informational: es tráfico normal de proxy, no un error del sistema.


def _load_offset() -> int:
    try:
        p = Path(_STATE_FILE)
        if p.exists():
            return json.loads(p.read_text()).get("offset", 0)
    except Exception:
        pass
    return 0


def _save_offset(offset: int) -> None:
    try:
        Path(_STATE_FILE).write_text(json.dumps({"offset": offset}))
    except Exception:
        pass


def _pri(facility: str) -> int:
    return _FACILITY_CODES.get(facility, _FACILITY_CODES["local0"]) * 8 + _SEVERITY_INFO


def _body(entry: dict, log_format: str) -> str:
    """El contenido del mensaje: la línea de Squid tal cual, o NDJSON."""
    if log_format == "ndjson":
        return json.dumps({k: v for k, v in entry.items() if k != "raw_line"}, ensure_ascii=False)
    return entry["raw_line"]


def build_syslog_message(entry: dict, config: SyslogConfig) -> bytes:
    """Arma el mensaje syslog completo (cabecera + cuerpo), listo para enviar."""
    pri = _pri(config.facility)
    now = datetime.fromtimestamp(entry["timestamp"], tz=timezone.utc)
    msg = _body(entry, config.log_format)

    if config.rfc_format == "rfc5424":
        ts = now.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        line = f"<{pri}>1 {ts} squidmanager squid - - - {msg}"
    else:
        # RFC 3164: "Mmm dd hh:mm:ss" sin año, con el día en dos posiciones
        # (espacio en vez de cero a la izquierda si es menor que 10).
        ts = now.strftime("%b %e %H:%M:%S")
        line = f"<{pri}>{ts} squidmanager squid: {msg}"

    return line.encode("utf-8", errors="replace")


def send_test_message(config: SyslogConfig) -> tuple[bool, str]:
    """Envía un mensaje de prueba al destino configurado, ahora mismo."""
    if not config.host:
        return False, "Falta el host de destino"

    test_entry = {
        "timestamp": time.time(),
        "raw_line": (
            f"{time.time():.3f} 0 127.0.0.1 TCP_MISS/200 0 GET "
            "http://test.squidmanager.local/ - HIER_NONE/- text/plain"
        ),
        "elapsed_ms": 0, "client_ip": "127.0.0.1", "action": "TCP_MISS", "status": 200,
        "bytes": 0, "method": "GET", "url": "http://test.squidmanager.local/",
        "domain": "test.squidmanager.local", "user": "squidmanager-test",
        "hierarchy": "HIER_NONE/-", "content_type": "text/plain", "denied": False,
    }
    message = build_syslog_message(test_entry, config)

    try:
        if config.protocol == "tcp":
            with socket.create_connection((config.host, config.port), timeout=5) as s:
                s.sendall(message + b"\n")
        else:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.settimeout(5)
                s.sendto(message, (config.host, config.port))
            finally:
                s.close()
    except Exception as e:
        return False, f"No se pudo enviar: {e}"

    nota = " (UDP no confirma entrega: solo indica que el sistema aceptó enviarlo)" if config.protocol == "udp" else ""
    return True, f"Mensaje de prueba enviado a {config.host}:{config.port}/{config.protocol.upper()}{nota}"


def _forward_batch(entries: list[dict], config: SyslogConfig) -> int:
    """Envía un lote de líneas ya parseadas. Devuelve cuántas se mandaron."""
    if not entries:
        return 0
    sent = 0
    try:
        if config.protocol == "tcp":
            with socket.create_connection((config.host, config.port), timeout=5) as s:
                for entry in entries:
                    s.sendall(build_syslog_message(entry, config) + b"\n")
                    sent += 1
        else:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                s.settimeout(5)
                for entry in entries:
                    s.sendto(build_syslog_message(entry, config), (config.host, config.port))
                    sent += 1
            finally:
                s.close()
    except Exception as e:
        logger.error(f"Error reenviando a syslog ({sent}/{len(entries)} enviados): {e}")
    return sent


def _read_new_lines(offset: int) -> tuple[list[str], int]:
    """Lee las líneas nuevas desde `offset`. Si el fichero se rotó (es más
    chico que el offset guardado), se relee desde el principio."""
    p = Path(ACCESS_LOG_PATH)
    if not p.exists():
        return [], offset

    size = p.stat().st_size
    if size < offset:
        offset = 0

    with open(p, "rb") as f:
        f.seek(offset)
        chunk = f.read()

    if not chunk:
        return [], offset

    # La última línea puede estar incompleta si se leyó a mitad de escritura;
    # se deja para la próxima pasada en vez de reenviarla partida.
    text = chunk.decode("utf-8", errors="replace")
    if text.endswith("\n"):
        new_offset = offset + len(chunk)
        lines = text.splitlines()
    else:
        last_nl = text.rfind("\n")
        if last_nl == -1:
            return [], offset
        new_offset = offset + len(text[: last_nl + 1].encode("utf-8"))
        lines = text[:last_nl].splitlines()

    return lines, new_offset


def _forwarder_loop():
    offset = _load_offset()
    logger.info("Reenviador de syslog iniciado (canal apagado hasta que se habilite en Configuración)")

    while True:
        try:
            db = SessionLocal()
            try:
                config = db.query(SyslogConfig).first()
            finally:
                db.close()

            if not config or not config.enabled or not config.host:
                # Sin destino activo: no tiene sentido acumular una cola de
                # líneas para cuando se habilite, así que se sigue avanzando
                # el offset para no reenviar de golpe todo lo perdido mientras
                # estuvo apagado.
                lines, offset = _read_new_lines(offset)
                _save_offset(offset)
                time.sleep(_POLL_SECONDS)
                continue

            lines, new_offset = _read_new_lines(offset)
            if lines:
                entries = [e for e in (parse_line(l) for l in lines) if e]
                sent = _forward_batch(entries, config)
                if sent < len(entries):
                    logger.warning(f"Syslog: solo se reenviaron {sent} de {len(entries)} líneas de este lote")
            offset = new_offset
            _save_offset(offset)
        except Exception as e:
            logger.error(f"Error en el reenviador de syslog: {e}")

        time.sleep(_POLL_SECONDS)


def start_syslog_forwarder():
    """Arranca el hilo de fondo una sola vez, al iniciar el backend.

    Hilo daemon: si el proceso principal termina, este no lo bloquea. El
    propio bucle comprueba en cada vuelta si el canal sigue habilitado, así
    que no hace falta pararlo ni reiniciarlo al cambiar la configuración.
    """
    thread = threading.Thread(target=_forwarder_loop, name="syslog-forwarder", daemon=True)
    thread.start()
