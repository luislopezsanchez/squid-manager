"""Servicio de notificaciones: envío de alertas por email, Telegram y XMPP."""

import logging
import threading
import time
import smtplib
import urllib.parse
import urllib.request
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from types import SimpleNamespace

logger = logging.getLogger(__name__)

# --- Estado y «corte automático» por canal -----------------------------------------------------------------------
# Con un canal caído (servidor de correo, Telegram o XMPP sin respuesta) y eventos frecuentes, cada aviso esperaba su
# tiempo máximo (15-45 s) y las tareas se iban acumulando. Ahora: como mucho 2 envíos a la vez por canal y, tras
# FALLOS_PARA_PAUSAR fallos seguidos, el canal se pausa PAUSA_SEGUNDOS (los avisos se descartan y se cuentan). El primer
# éxito —o una prueba correcta— lo reactiva. El estado vive en memoria (el backend corre con un único proceso) y se
# muestra en la pantalla Notificaciones: antes un fallo sólo quedaba en el log.
FALLOS_PARA_PAUSAR = 3
PAUSA_SEGUNDOS = 300
ENVIOS_SIMULTANEOS = 2
CANALES = ("email", "telegram", "xmpp")

_estado_lock = threading.Lock()
_estado: dict[str, dict] = {}
_semaforos = {c: threading.BoundedSemaphore(ENVIOS_SIMULTANEOS) for c in CANALES}


def _nuevo_estado() -> dict:
    return {"fallos_seguidos": 0, "pausado_hasta": 0.0, "ultimo_error": None, "ultimo_error_en": None,
            "ultimo_ok_en": None, "descartados": 0}


def _canal(nombre: str) -> dict:
    return _estado.setdefault(nombre, _nuevo_estado())


def estado_canales() -> dict:
    """Resumen por canal para la pantalla: estado (sin_actividad | ok | con_errores | pausado), último error, etc."""
    ahora = time.time()
    salida = {}
    with _estado_lock:
        for nombre in CANALES:
            e = _canal(nombre)
            pausado = e["pausado_hasta"] > ahora
            if pausado:
                st = "pausado"
            elif e["fallos_seguidos"] > 0:
                st = "con_errores"
            elif e["ultimo_ok_en"]:
                st = "ok"
            else:
                st = "sin_actividad"
            salida[nombre] = {
                "estado": st, "fallos_seguidos": e["fallos_seguidos"], "descartados": e["descartados"],
                "ultimo_error": e["ultimo_error"], "ultimo_error_en": e["ultimo_error_en"],
                "ultimo_ok_en": e["ultimo_ok_en"],
                "pausado_segundos": int(e["pausado_hasta"] - ahora) if pausado else 0,
            }
    return salida


def reiniciar_canal(nombre: str) -> None:
    """Reactiva un canal (una prueba correcta lo hace)."""
    with _estado_lock:
        e = _canal(nombre)
        e.update(fallos_seguidos=0, pausado_hasta=0.0)
        e["ultimo_ok_en"] = time.time()


def _registrar(nombre: str, ok: bool, mensaje: str) -> None:
    ahora = time.time()
    with _estado_lock:
        e = _canal(nombre)
        if ok:
            e.update(fallos_seguidos=0, pausado_hasta=0.0, ultimo_ok_en=ahora)
            return
        e["fallos_seguidos"] += 1
        e["ultimo_error"], e["ultimo_error_en"] = (mensaje or "")[:300], ahora
        if e["fallos_seguidos"] >= FALLOS_PARA_PAUSAR:
            e["pausado_hasta"] = ahora + PAUSA_SEGUNDOS
            logger.warning("Canal de notificación %s en pausa %d s tras %d fallos seguidos: %s",
                           nombre, PAUSA_SEGUNDOS, e["fallos_seguidos"], mensaje)


def _por_canal(nombre: str, enviar) -> bool:
    """Ejecuta `enviar()` -> (ok, mensaje) respetando la pausa y el tope de envíos simultáneos."""
    with _estado_lock:
        if _canal(nombre)["pausado_hasta"] > time.time():
            _canal(nombre)["descartados"] += 1
            return False
    if not _semaforos[nombre].acquire(blocking=False):
        with _estado_lock:
            _canal(nombre)["descartados"] += 1
        return False
    try:
        ok, mensaje = enviar()
    except Exception as e:  # un canal roto nunca debe romper a quien notifica
        ok, mensaje = False, f"{type(e).__name__}: {e}"
    finally:
        _semaforos[nombre].release()
    _registrar(nombre, ok, mensaje)
    return ok

# Mapa de eventos a atributos de config
EVENT_CONFIG_MAP = {
    "apply": "notify_on_apply",
    "user_change": "notify_on_user_change",
    "acl_change": "notify_on_acl_change",
    "rule_change": "notify_on_rule_change",
    "security_alert": "notify_on_security_alert",
    "node_down": "notify_on_node_down",
    "quota_reached": "notify_on_quota_reached",
    "blocked_access": "notify_on_blocked_access",
}


def _snapshot_config(notif_config, smtp_config, idioma: str = "es") -> SimpleNamespace:
    """Crea una copia plana combinando Notificaciones (cuándo/a quién) y
    SmtpConfig (el servidor en sí), para usarla fuera de la sesión de BD.
    """
    return SimpleNamespace(
        email_enabled=notif_config.email_enabled,
        smtp_host=smtp_config.smtp_host if smtp_config else None,
        smtp_port=smtp_config.smtp_port if smtp_config else 587,
        smtp_user=smtp_config.smtp_user if smtp_config else None,
        smtp_password=smtp_config.smtp_password if smtp_config else None,
        smtp_from=smtp_config.smtp_from if smtp_config else None,
        smtp_encryption=smtp_config.smtp_encryption if smtp_config else "starttls",
        email_recipients=notif_config.email_recipients,
        telegram_enabled=notif_config.telegram_enabled,
        telegram_bot_token=notif_config.telegram_bot_token,
        telegram_chat_id=notif_config.telegram_chat_id,
        xmpp_enabled=notif_config.xmpp_enabled,
        xmpp_host=notif_config.xmpp_host,
        xmpp_port=notif_config.xmpp_port,
        xmpp_jid=notif_config.xmpp_jid,
        xmpp_password=notif_config.xmpp_password,
        xmpp_encryption=notif_config.xmpp_encryption,
        xmpp_verify_cert=notif_config.xmpp_verify_cert,
        xmpp_recipients=notif_config.xmpp_recipients,
        xmpp_room=notif_config.xmpp_room,
        idioma=idioma,
    )


def _snapshot_si_habilitado(db, event_type: str) -> SimpleNamespace | None:
    """Verifica que el evento esté habilitado en la config (notify_on_*) y
    que al menos un canal (email, Telegram o XMPP) esté habilitado; si es así,
    devuelve el snapshot listo para `notify()`, si no, None.
    """
    from app.models.notification_config import NotificationConfig
    from app.models.smtp_config import SmtpConfig

    config = db.query(NotificationConfig).first()
    if not config:
        return None

    attr = EVENT_CONFIG_MAP.get(event_type)
    if attr and not getattr(config, attr, False):
        return None

    if not (config.email_enabled or config.telegram_enabled or config.xmpp_enabled):
        return None

    smtp_config = db.query(SmtpConfig).first()
    # Idioma en que se redactan los correos: el del panel cuando se guardaron las notificaciones.
    try:
        from sqlalchemy import text
        fila = db.execute(text("SELECT v FROM app_settings WHERE k='report_lang'")).fetchone()
        idioma = fila[0] if fila and fila[0] in ("es", "en", "pt") else "es"
    except Exception:
        idioma = "es"
    return _snapshot_config(config, smtp_config, idioma)


def queue_notification(background_tasks, db, event_type: str, subject: str, message: str):
    """Encarga el envío de una notificación en segundo plano si está habilitada.

    Si corresponde, agrega un background task para enviar sin bloquear la
    petición -para eso hace falta el `background_tasks` de una request en
    curso (ver `notify_now` para el caso sin request, ej. un hilo de fondo).
    """
    snapshot = _snapshot_si_habilitado(db, event_type)
    if snapshot:
        background_tasks.add_task(notify, snapshot, subject, message, event_type)


def notify_now(db, event_type: str, subject: str, message: str) -> None:
    """Igual que `queue_notification`, pero para cuando no hay una request
    HTTP de por medio -no existe un `BackgroundTasks` de FastAPI fuera de
    una petición-, como el detector de anomalías (ver anomaly_service.py),
    que ya corre en su propio hilo de fondo y puede mandar la notificación
    directo sin bloquear nada ajeno.
    """
    snapshot = _snapshot_si_habilitado(db, event_type)
    if snapshot:
        notify(snapshot, subject, message, event_type)


def _enviar_smtp(config, destinatarios: list[str], subject: str, body: str, reply_to: str | None = None,
                 html_body: str | None = None) -> tuple[bool, str]:
    """Mecánica SMTP compartida: arma el mensaje y lo entrega al servidor
    configurado. `send_email` (destinatarios de la config) y
    `send_contact_message` (destinatario fijo de soporte) comparten esto en
    vez de repetir la conexión/autenticación dos veces.

    Devuelve (ok, mensaje) donde mensaje describe el resultado o el error.
    """
    if not config.smtp_host:
        return False, "Falta el servidor SMTP (host)"
    if not destinatarios:
        return False, "No hay destinatarios válidos"

    encryption = (config.smtp_encryption or "starttls").lower()

    try:
        msg = MIMEMultipart("alternative") if html_body else MIMEMultipart()
        from_addr = config.smtp_from or config.smtp_user or "squidmanager@localhost"
        msg["From"] = from_addr
        msg["To"] = ", ".join(destinatarios)
        msg["Subject"] = subject
        if reply_to:
            msg["Reply-To"] = reply_to
        msg.attach(MIMEText(body, "plain", "utf-8"))
        if html_body:  # el cliente de correo elige la última parte que sepa mostrar
            msg.attach(MIMEText(html_body, "html", "utf-8"))

        # Conexión según el método de cifrado
        if encryption == "ssl":
            # SSL/TLS implícito (puerto 465)
            server = smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, timeout=15)
        elif encryption == "starttls":
            # STARTTLS (puerto 587)
            server = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=15)
            server.ehlo()
            server.starttls()
            server.ehlo()
        else:
            # Sin cifrado
            server = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=15)
            server.ehlo()

        if config.smtp_user:
            server.login(config.smtp_user, config.smtp_password or "")

        server.sendmail(from_addr, destinatarios, msg.as_string())
        server.quit()
        logger.info(f"Email enviado a {len(destinatarios)} destinatarios")
        return True, f"Email enviado a {len(destinatarios)} destinatario(s)"
    except smtplib.SMTPAuthenticationError:
        return False, "Error de autenticación SMTP: usuario o contraseña incorrectos"
    except smtplib.SMTPException as e:
        return False, f"Error SMTP: {e}"
    except Exception as e:
        return False, f"Error de conexión: {e}"


def send_email(config, subject: str, body: str, html_body: str | None = None) -> tuple[bool, str]:
    """Envía un email a los destinatarios configurados en Notificaciones."""
    if not config.email_enabled:
        return False, "Notificaciones por email deshabilitadas"
    if not config.email_recipients:
        return False, "Falta el destinatario (email_recipients)"
    recipients = [r.strip() for r in config.email_recipients.split(",") if r.strip()]
    return _enviar_smtp(config, recipients, subject, body, html_body=html_body)


# Destino de los mensajes de Contacto (Ayuda > Contacto): lo fija quien instala, con CONTACT_EMAIL en el
# .env (por defecto, el autor del proyecto; vacío = no enviar por correo). Reusa el SMTP que el admin ya
# haya configurado en Notificaciones como relay de salida; si no hay SMTP o no hay destino, el mensaje
# igual queda guardado en `contact_messages` (ver ContactMessage), solo no se envía por correo.
def destino_contacto() -> str:
    from app.config import settings
    return (settings.CONTACT_EMAIL or "").strip()


def send_contact_message(config, subject: str, body: str, reply_to: str | None = None) -> tuple[bool, str]:
    """Envía un mensaje de Contacto al soporte del producto, vía el SMTP que
    el admin ya tenga configurado en Notificaciones (si lo tiene)."""
    destino = destino_contacto()
    if not destino:
        return False, "El envío por correo del formulario de Contacto está desactivado en esta instalación"
    if not config or not config.smtp_host:
        return False, "No hay un servidor SMTP configurado en Notificaciones"
    return _enviar_smtp(config, [destino], subject, body, reply_to=reply_to)


def send_telegram(config, message: str) -> tuple[bool, str]:
    """Envía un mensaje por Telegram usando el bot configurado."""
    if not config.telegram_enabled:
        return False, "Notificaciones por Telegram deshabilitadas"
    if not config.telegram_bot_token or not config.telegram_chat_id:
        return False, "Falta el token del bot o el chat_id de Telegram"

    try:
        url = f"https://api.telegram.org/bot{config.telegram_bot_token}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": config.telegram_chat_id,
            "text": message,
            "parse_mode": "HTML",
        }).encode()
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode()
        logger.info("Mensaje de Telegram enviado")
        # Verificar respuesta de la API de Telegram
        import json
        resp_json = json.loads(body)
        if resp_json.get("ok"):
            return True, "Mensaje de Telegram enviado"
        return False, f"Error de Telegram: {resp_json.get('description', 'respuesta no válida')}"
    except Exception as e:
        return False, f"Error enviando Telegram: {e}"


def xmpp_destinos(config) -> list[str]:
    """JIDs de usuario a los que se escribe (coma-separados en la config)."""
    return [r.strip() for r in (config.xmpp_recipients or "").split(",") if r.strip()]


async def _enviar_xmpp_async(config, texto: str, destinos: list[str], sala: str | None) -> tuple[bool, str]:
    import asyncio
    import ssl
    import slixmpp

    cifrado = (config.xmpp_encryption or "starttls").lower()
    xmpp = slixmpp.ClientXMPP(config.xmpp_jid, config.xmpp_password or "")
    xmpp.enable_direct_tls = cifrado == "ssl"
    xmpp.enable_starttls = cifrado == "starttls"
    xmpp.enable_plaintext = cifrado == "none"
    if cifrado == "none":  # sin cifrado el servidor sólo ofrece PLAIN: se permite porque el admin lo eligió
        xmpp["feature_mechanisms"].unencrypted_plain = True
    if not config.xmpp_verify_cert:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        xmpp.ssl_context = ctx
    xmpp.register_plugin("xep_0199")  # ping: la respuesta confirma que el servidor ya recibió los mensajes
    if sala:
        xmpp.register_plugin("xep_0045")

    resultado: asyncio.Future = asyncio.get_running_loop().create_future()

    def _fin(ok: bool, msg: str):
        if not resultado.done():
            resultado.set_result((ok, msg))

    async def _sesion(_evento):
        try:
            if cifrado == "starttls" and not xmpp.transport.get_extra_info("ssl_object"):
                _fin(False, "El servidor XMPP no ofreció STARTTLS: elige «Sin cifrar» si es lo que quieres")
                return
            enviados = 0
            for jid in destinos:
                xmpp.send_message(mto=jid, mbody=texto, mtype="chat")
                enviados += 1
            if sala:
                await xmpp.plugin["xep_0045"].join_muc_wait(slixmpp.JID(sala), "SquidManager", timeout=10)
                xmpp.send_message(mto=sala, mbody=texto, mtype="groupchat")
                enviados += 1
            try:  # ida y vuelta al servidor: el flujo es ordenado, así que al volver ya recibió todo lo anterior
                await xmpp.plugin["xep_0199"].ping(timeout=8)
            except Exception:
                await asyncio.sleep(1)
            _fin(True, f"Mensaje XMPP enviado a {enviados} destino(s)")
        except Exception as e:
            _fin(False, f"Error enviando por XMPP: {e or type(e).__name__}")

    xmpp.add_event_handler("session_start", _sesion)
    xmpp.add_event_handler("failed_auth", lambda _e: _fin(False, "Error de autenticación XMPP: cuenta o contraseña incorrectas"))
    xmpp.add_event_handler("ssl_invalid_chain", lambda _e: _fin(False, (
        "El certificado del servidor XMPP no es de confianza: desmarca «Verificar certificado» si es un certificado propio")))
    xmpp.add_event_handler("connection_failed", lambda _e: _fin(False, (
        "No se pudo conectar al servidor XMPP: revisa host, puerto y cifrado"
        + ("; si el certificado es propio, desmarca «Verificar certificado»" if config.xmpp_verify_cert else ""))))
    xmpp.connect(config.xmpp_host, int(config.xmpp_port))
    try:
        return await asyncio.wait_for(resultado, timeout=25)
    except asyncio.TimeoutError:
        return False, "Tiempo agotado hablando con el servidor XMPP"
    finally:
        try:
            await asyncio.wait_for(xmpp.disconnect(wait=3), timeout=8)
        except Exception:
            pass


def send_xmpp(config, texto: str) -> tuple[bool, str]:
    """Envía un mensaje por XMPP a los destinos configurados (usuarios y/o sala).

    SquidManager sólo actúa de cliente: se conecta a un servidor XMPP que ya existe
    con la cuenta que el admin indicó. slixmpp es asyncio y esto se llama desde código
    síncrono (tareas de fondo, hilos), así que corre en un hilo propio con su bucle de
    eventos y un tiempo máximo: un servidor caído nunca bloquea el panel.
    """
    import asyncio
    import threading

    if not config.xmpp_enabled:
        return False, "Notificaciones por XMPP deshabilitadas"
    if not (config.xmpp_host and config.xmpp_jid and config.xmpp_password):
        return False, "Falta el servidor, la cuenta (JID) o la contraseña de XMPP"
    destinos = xmpp_destinos(config)
    sala = (config.xmpp_room or "").strip() or None
    if not destinos and not sala:
        return False, "Falta al menos un destinatario o una sala de XMPP"

    salida: list = []

    def _hilo():
        try:
            salida.append(asyncio.run(_enviar_xmpp_async(config, texto, destinos, sala)))
        except Exception as e:
            salida.append((False, f"Error enviando por XMPP: {e}"))

    t = threading.Thread(target=_hilo, daemon=True)
    t.start()
    t.join(timeout=45)
    if not salida:
        return False, "Tiempo agotado hablando con el servidor XMPP"
    ok, msg = salida[0]
    if ok:
        logger.info(msg)
    else:
        logger.warning("XMPP: %s", msg)
    return ok, msg


def notify(config, subject: str, message: str, event: str | None = None) -> dict:
    """Envía notificación por email, Telegram y/o XMPP según configuración."""
    results = {"email": False, "telegram": False, "xmpp": False}

    if config.email_enabled:
        from app.services.email_templates import construir_correo
        try:
            cuerpo_html, texto = construir_correo(event, subject, message, getattr(config, "idioma", "es"))
        except Exception as e:  # una plantilla rota no debe perder el aviso: sale en texto plano
            logger.warning("No se pudo construir el correo con formato: %s", e)
            cuerpo_html, texto = None, message
        results["email"] = _por_canal("email", lambda: send_email(config, subject, texto, html_body=cuerpo_html))

    if config.telegram_enabled:
        from app.i18n import traducir_dinamico
        idioma = getattr(config, "idioma", "es")
        import html as _html
        # parse_mode=HTML: el texto va escapado (un nombre de usuario con "<" no debe romper el mensaje).
        full_message = f"<b>{_html.escape(traducir_dinamico(subject, idioma))}</b>\n\n{_html.escape(traducir_dinamico(message, idioma))}"
        results["telegram"] = _por_canal("telegram", lambda: send_telegram(config, full_message))

    if getattr(config, "xmpp_enabled", False):
        from app.i18n import traducir_dinamico
        idioma = getattr(config, "idioma", "es")
        texto_chat = f"{traducir_dinamico(subject, idioma)}\n\n{traducir_dinamico(message, idioma)}"
        results["xmpp"] = _por_canal("xmpp", lambda: send_xmpp(config, texto_chat))

    return results


def _resultado_prueba(canal: str, ok: bool, mensaje: str) -> None:
    """Una prueba manual no cuenta para la pausa, pero si sale bien reactiva el canal y si falla deja su motivo visible."""
    if ok:
        reiniciar_canal(canal)
    else:
        with _estado_lock:
            e = _canal(canal)
            e["ultimo_error"], e["ultimo_error_en"] = (mensaje or "")[:300], time.time()


def test_email(config) -> dict:
    """Prueba el envío de email."""
    from app.services.email_templates import construir_correo
    cuerpo_html, texto = construir_correo(
        "test", "SquidManager: prueba de notificación",
        "Este es un correo de prueba de SquidManager. Si lo recibes, la configuración del correo es correcta.",
        getattr(config, "idioma", "es"),
    )
    ok, message = send_email(config, "SquidManager - Prueba de notificación", texto, html_body=cuerpo_html)
    _resultado_prueba("email", ok, message)
    return {"ok": ok, "message": message}


def test_telegram(config) -> dict:
    """Prueba el envío por Telegram."""
    ok, message = send_telegram(
        config,
        "SquidManager - Prueba de notificación\n\nSi recibes esto, la configuración de Telegram es correcta.",
    )
    _resultado_prueba("telegram", ok, message)
    return {"ok": ok, "message": message}


def test_xmpp(config) -> dict:
    """Prueba el envío por XMPP."""
    ok, message = send_xmpp(
        config,
        "SquidManager - Prueba de notificación\n\nSi recibes esto, la configuración de XMPP es correcta.",
    )
    _resultado_prueba("xmpp", ok, message)
    return {"ok": ok, "message": message}
