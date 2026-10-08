"""Canal XMPP de Notificaciones: validación, envío por el hilo propio y reparto en notify().

El envío real contra un servidor XMPP se probó con Prosody (STARTTLS, SSL, sin cifrar, sala MUC);
aquí se protege lo que no depende de la red: que los datos se validen, que un servidor roto
nunca bloquee ni propague excepciones, y que notify() use el canal sólo si está activo.
"""

from types import SimpleNamespace as N

import pytest

from app.routes import notifications as rutas
from app.services import notification_service as ns


def _cfg(**kw):
    base = dict(xmpp_enabled=True, xmpp_host="xmpp.local", xmpp_port=5222, xmpp_jid="squid@empresa.local",
                xmpp_password="x", xmpp_encryption="starttls", xmpp_verify_cert=True,
                xmpp_recipients="a@empresa.local, b@empresa.local", xmpp_room=None)
    base.update(kw)
    return N(**base)


@pytest.mark.parametrize("args,esperado", [
    (("xmpp.local", "squid@empresa.local", "a@x.local, b@x.local", "avisos@conference.x.local"), None),
    (("10.0.0.5", "squid@empresa.local", None, None), None),
    (("xmpp local", None, None, None), "host"),
    ((None, "sin-arroba", None, None), "JID"),
    ((None, None, "bueno@x.local, malo", None), "malo"),
    ((None, None, None, "sala sin forma"), "sala"),
    ((None, "a b@x.local", None, None), "JID"),
])
def test_validacion(args, esperado):
    r = rutas._validar_xmpp(*args)
    if esperado is None:
        assert r is None
    else:
        assert esperado.lower() in r.lower()


@pytest.mark.parametrize("kw,fragmento", [
    (dict(xmpp_enabled=False), "deshabilitadas"),
    (dict(xmpp_host=""), "Falta el servidor"),
    (dict(xmpp_password=None), "Falta el servidor"),
    (dict(xmpp_recipients="", xmpp_room=None), "al menos un destinatario"),
])
def test_send_xmpp_rechaza_config_incompleta(kw, fragmento):
    ok, msg = ns.send_xmpp(_cfg(**kw), "hola")
    assert not ok and fragmento in msg


def test_send_xmpp_un_fallo_interno_no_propaga(monkeypatch):
    async def roto(*a, **k):
        raise RuntimeError("boom")
    monkeypatch.setattr(ns, "_enviar_xmpp_async", roto)
    ok, msg = ns.send_xmpp(_cfg(), "hola")
    assert not ok and "boom" in msg


def test_send_xmpp_pasa_destinos_y_sala(monkeypatch):
    visto = {}

    async def falso(config, texto, destinos, sala):
        visto.update(texto=texto, destinos=destinos, sala=sala)
        return True, "ok"
    monkeypatch.setattr(ns, "_enviar_xmpp_async", falso)
    assert ns.send_xmpp(_cfg(xmpp_room=" avisos@conference.x.local "), "hola") == (True, "ok")
    assert visto == {"texto": "hola", "destinos": ["a@empresa.local", "b@empresa.local"],
                     "sala": "avisos@conference.x.local"}


def test_envio_real_contra_servidor_inexistente_falla_rapido_y_sin_excepcion():
    # Puerto cerrado en localhost: debe devolver (False, ...) sin colgarse ni lanzar.
    ok, msg = ns.send_xmpp(_cfg(xmpp_host="127.0.0.1", xmpp_port=1), "hola")
    assert not ok and "conectar" in msg


def test_notify_usa_xmpp_solo_si_esta_activo(monkeypatch):
    enviados = []
    monkeypatch.setattr(ns, "send_xmpp", lambda c, t: (enviados.append(t) or (True, "ok")))
    monkeypatch.setattr(ns, "send_email", lambda *a, **k: (True, "ok"))
    conf = N(email_enabled=False, telegram_enabled=False, xmpp_enabled=True, idioma="es")
    r = ns.notify(conf, "Asunto", "Cuerpo", "apply")
    assert r == {"email": False, "telegram": False, "xmpp": True}
    assert enviados == ["Asunto\n\nCuerpo"]
    conf.xmpp_enabled = False
    assert ns.notify(conf, "A", "B", "apply")["xmpp"] is False
    assert len(enviados) == 1


def test_notify_con_snapshot_antiguo_sin_campos_xmpp(monkeypatch):
    monkeypatch.setattr(ns, "send_xmpp", lambda c, t: pytest.fail("no debe enviar"))
    conf = N(email_enabled=False, telegram_enabled=False, idioma="es")
    assert ns.notify(conf, "A", "B")["xmpp"] is False


def test_la_clave_xmpp_viaja_cifrada_en_el_backup():
    from app.services.backup_v2_service import ENTIDADES
    ent = next(e for e in ENTIDADES if e.nombre == "notification_config")
    assert "xmpp_password" in ent.secretas and "telegram_bot_token" in ent.secretas


def test_la_clave_xmpp_es_columna_cifrada():
    from app.crypto_service import EncryptedString
    from app.models.notification_config import NotificationConfig
    assert isinstance(NotificationConfig.__table__.c.xmpp_password.type, EncryptedString)


def test_migracion_encadenada():
    import importlib.util
    import pathlib
    ruta = pathlib.Path(__file__).parent.parent / "migrations" / "versions" / "0047_notificaciones_xmpp.py"
    spec = importlib.util.spec_from_file_location("m0047", ruta)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    assert (m.revision, m.down_revision) == ("0047", "0046")
