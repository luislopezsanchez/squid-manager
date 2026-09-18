"""Sincronización automática de categorías de dominios desde una URL externa
(hoy, HaGeZi dns-blocklists) — ver app/services/category_sync_service.py."""

from app.services import category_sync_service as css
from app.services.squid_names import NAME_PATTERN


# --- Presets curados ---------------------------------------------------------

def test_presets_hagezi_tienen_nombre_valido_para_squid():
    """Un nombre de ACL de Squid no admite puntos ni mayúsculas
    (^[A-Za-z][A-Za-z0-9_-]{0,63}$, ver squid_names.NAME_PATTERN). Si algún
    día se agrega un preset con un slug mal formado, esto tiene que
    fallar acá, no recién al intentar crear la categoría de verdad."""
    for preset in css.HAGEZI_PRESETS:
        nombre = css._nombre_categoria(preset["slug"])
        assert NAME_PATTERN.match(nombre), f"nombre inválido: {nombre}"
        assert not nombre.startswith("sni_")


def test_presets_hagezi_tienen_url_https_bien_formada():
    for preset in css.HAGEZI_PRESETS:
        url = css.HAGEZI_BASE_URL + preset["archivo_remoto"]
        assert url.startswith("https://raw.githubusercontent.com/hagezi/dns-blocklists/")
        assert url.endswith("-onlydomains.txt")


def test_descripcion_preset_incluye_atribucion_y_licencia():
    descripcion = css._descripcion_preset("Apuestas y juego online")
    assert "Apuestas y juego online" in descripcion
    assert "HaGeZi" in descripcion
    assert "GPL-3.0" in descripcion


# --- sync_one: nunca debe tumbar el hilo de fondo, pase lo que pase --------

class FakeAcl:
    def __init__(self, name="hagezi_gambling", acl_type="dstdomain", sync_url="https://ejemplo.com/lista.txt"):
        self.name = name
        self.type = acl_type
        self.sync_url = sync_url
        self.last_synced_at = None
        self.last_sync_status = None


class FakeSession:
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def test_sync_one_error_de_red_no_propaga_y_queda_registrado(monkeypatch):
    def _falla(url):
        raise ConnectionError("no se pudo conectar")

    monkeypatch.setattr(css, "_fetch_domain_list", _falla)

    db = FakeSession()
    acl = FakeAcl()
    resultado = css.sync_one(db, acl)

    assert resultado["ok"] is False
    assert acl.last_sync_status.startswith("Error:")
    assert "no se pudo conectar" in acl.last_sync_status
    assert db.rollbacks == 1
    assert db.commits == 1  # el commit que guarda el estado de error


def test_sync_one_fuente_sin_dominios_validos(monkeypatch):
    monkeypatch.setattr(css, "_fetch_domain_list", lambda url: [])

    db = FakeSession()
    acl = FakeAcl()
    resultado = css.sync_one(db, acl)

    assert resultado["ok"] is False
    assert "ningún dominio válido" in acl.last_sync_status


def test_sync_one_exito_actualiza_estado_y_marca_la_hora(monkeypatch):
    monkeypatch.setattr(css, "_fetch_domain_list", lambda url: ["ejemplo1.com", "ejemplo2.com"])

    def _fake_aplicar(db, name, acl_type, dominios, modo, description, is_category, admin_id, admin_username):
        assert modo == "agregar"  # nunca "reemplazar": no debe pisar lo que el admin sumó a mano
        assert is_category is True
        assert admin_username == "Sincronización automática"
        return acl_fake_devuelta, {"combinados": len(dominios), "source": "inline", "sin_cambios": False}

    acl_fake_devuelta = FakeAcl()
    monkeypatch.setattr(
        "app.services.squid_service.aplicar_lista_dominios", _fake_aplicar,
    )

    db = FakeSession()
    acl = FakeAcl()
    resultado = css.sync_one(db, acl)

    assert resultado["ok"] is True
    assert resultado["combinados"] == 2
    assert acl.last_sync_status == "ok, 2 dominios"
    assert acl.last_synced_at is not None
