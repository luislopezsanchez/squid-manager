"""Sincronización automática de categorías de dominios desde una URL externa.

Pensado para blocklists públicas de terceros (hoy, HaGeZi dns-blocklists) que
un admin puede querer usar como punto de partida para una categoría, en vez
de armarla a mano dominio por dominio. Dos piezas:

- `cargar_preset_hagezi()`: crea (o reconecta) un subconjunto curado de listas
  de HaGeZi como categorías propias, con nombres con prefijo `hagezi_` para
  que se note a simple vista de dónde vienen.
- El hilo de fondo (`start_category_sync`, mismo patrón que
  `update_service.start_update_checker`): una vez al día, refresca CUALQUIER
  categoría que tenga `sync_url` cargado -no solo las de HaGeZi-, por si a
  futuro se conecta otra fuente.

Decisión de diseño importante, no accidental: la sincronización SIEMPRE usa
modo "agregar" (nunca "reemplazar"). Si el admin sumó sus propios dominios
encima de una lista externa, un refresco en modo "reemplazar" se los
borraría cada vez que corre. La contra, documentada a propósito: si la
fuente externa saca un dominio de su lista (corrige un falso positivo), acá
queda pegado igual -solo se suma, nunca se resta-. Es un trade-off
consciente, no un descuido.

Apagado por defecto para toda categoría existente: `sync_url` nace en NULL
(migración 0026), así que nada empieza a sincronizar solo sin que el admin
lo conecte a propósito -mismo criterio que LDAP/Kerberos/el asistente de IA.
"""

import logging
import threading
import time

import httpx

from app.database import SessionLocal
from app.utils import utcnow

logger = logging.getLogger(__name__)

# El archivo más grande de los presets curados hoy (gambling.mini) pesa
# unos 2.5 MB, seguido de tif.mini con ~3.4 MB; 50 MB da margen generoso sin
# dejar que una URL mal configurada o una fuente que empiece a devolver
# basura consuma memoria sin límite.
MAX_SYNC_BYTES = 50 * 1024 * 1024
SYNC_TIMEOUT_SEGUNDOS = 60

HAGEZI_BASE_URL = "https://raw.githubusercontent.com/hagezi/dns-blocklists/main/wildcard/"
HAGEZI_LICENCIA = "GPL-3.0"

# Subconjunto curado, no el catálogo completo de HaGeZi (42 listas en total
# a la fecha, verificado en vivo el 2026-09-18 -varias son paquetes
# combinados que mezclan ads/tracking/malware sin distinguir categoría, o
# rastreadores de telemetría por fabricante de hardware, pensados para un
# filtro DNS personal tipo Pi-hole, no para política de navegación de una
# organización -no encajan con el propósito de "categorías con nombre
# claro" que se busca acá).
#
# "gambling" usa la variante ".mini" (134.000 dominios, 2.5 MB) en vez de la
# lista completa (517.000, 8.8 MB) -un volumen más razonable para un valor
# por defecto. "tif" (Threat Intelligence Feeds, malware/phishing) usa
# ".mini" por el mismo motivo: la versión completa son 2.5 MILLONES de
# dominios. El resto no tiene variante más chica en HaGeZi, se usan tal
# cual. Cifras exactas verificadas en vivo antes de fijarlas acá.
#
# "evasion_proxy" (doh-vpn-proxy-bypass) no es una categoría de contenido
# como las demás: bloquea DNS cifrado, VPN, Tor y proxies -formas de saltarse
# el proxy mismo-, no un tipo de sitio. Se incluye igual porque sin esto
# cualquier otra categoría de acá se puede evadir con un clic.
#
# "acortadores" (urlshortener) bloquea TODOS los acortadores de URL
# conocidos, no solo los usados para evadir un bloqueo -alto riesgo de falso
# positivo con links legítimos compartidos así. Incluido a pedido explícito,
# con esta advertencia documentada para quien lo active.
HAGEZI_PRESETS = [
    {"slug": "gambling", "archivo_remoto": "gambling.mini-onlydomains.txt", "etiqueta": "Apuestas y juego online"},
    {"slug": "nsfw", "archivo_remoto": "nsfw-onlydomains.txt", "etiqueta": "Contenido para adultos"},
    {"slug": "pirateria", "archivo_remoto": "anti.piracy-onlydomains.txt", "etiqueta": "Sitios de piratería"},
    {"slug": "social", "archivo_remoto": "social-onlydomains.txt", "etiqueta": "Redes sociales"},
    {"slug": "fraudes", "archivo_remoto": "fake-onlydomains.txt", "etiqueta": "Tiendas y sitios falsos, estafas"},
    {"slug": "evasion_proxy", "archivo_remoto": "doh-vpn-proxy-bypass-onlydomains.txt", "etiqueta": "Evasión del proxy (DNS cifrado, VPN, Tor)"},
    {"slug": "popupads", "archivo_remoto": "popupads-onlydomains.txt", "etiqueta": "Pop-ups publicitarios maliciosos"},
    {"slug": "amenazas", "archivo_remoto": "tif.mini-onlydomains.txt", "etiqueta": "Amenazas de seguridad (malware, phishing)"},
    {"slug": "acortadores", "archivo_remoto": "urlshortener-onlydomains.txt", "etiqueta": "Acortadores de URL (bloquea todos, no solo los usados para evadir bloqueos)"},
]


def _nombre_categoria(slug: str) -> str:
    return f"hagezi_{slug}"


def _descripcion_preset(etiqueta: str) -> str:
    return f"{etiqueta} — HaGeZi dns-blocklists ({HAGEZI_LICENCIA}), se actualiza sola una vez al día."


def _fetch_domain_list(url: str) -> list[str]:
    """Descarga una URL y devuelve solo las líneas que parecen un dominio
    válido. Reutiliza validar_lista_dominios, que ya ignora líneas vacías y
    comentarios ('#') -el formato exacto en el que HaGeZi (y la mayoría de
    las blocklists públicas) ponen su cabecera de metadatos."""
    from app.services.squid_names import validar_lista_dominios

    total = 0
    partes: list[bytes] = []
    with httpx.stream("GET", url, timeout=SYNC_TIMEOUT_SEGUNDOS, follow_redirects=True) as r:
        r.raise_for_status()
        for chunk in r.iter_bytes():
            total += len(chunk)
            if total > MAX_SYNC_BYTES:
                raise ValueError(f"la respuesta supera el límite de {MAX_SYNC_BYTES // (1024 * 1024)} MB")
            partes.append(chunk)

    texto = b"".join(partes).decode("utf-8", errors="replace")
    dominios, _rechazados = validar_lista_dominios(texto.splitlines())
    return dominios


def sync_one(db, acl) -> dict:
    """Sincroniza UNA categoría desde `acl.sync_url`. Nunca falla de forma
    ruidosa: cualquier error de red o de la fuente queda en
    `last_sync_status` para que el admin lo vea en el panel, sin tumbar el
    hilo de fondo ni afectar a las demás categorías de la misma vuelta."""
    from app.services.squid_service import aplicar_lista_dominios

    try:
        dominios = _fetch_domain_list(acl.sync_url)
        if not dominios:
            acl.last_sync_status = "La fuente no devolvió ningún dominio válido"
            db.commit()
            return {"ok": False, "detalle": acl.last_sync_status}

        _acl, info = aplicar_lista_dominios(
            db, acl.name, acl.type, dominios, "agregar",
            description=None, is_category=True,
            admin_id=None, admin_username="Sincronización automática",
        )
        acl.last_synced_at = utcnow()
        acl.last_sync_status = f"ok, {info['combinados']} dominios"
        db.commit()
        return {"ok": True, "combinados": info["combinados"], "sin_cambios": info["sin_cambios"]}
    except Exception as e:
        db.rollback()
        acl.last_sync_status = f"Error: {e}"[:255]
        db.commit()
        logger.error("Sincronización de categoría '%s' falló: %s", acl.name, e)
        return {"ok": False, "detalle": str(e)}


def cargar_preset_hagezi(db) -> list[dict]:
    """Crea (o reconecta) las categorías predefinidas de HaGeZi y dispara la
    primera sincronización de cada una en el momento -no hace falta esperar
    al refresco diario para ver el resultado."""
    from app.models.acl import Acl

    resultados = []
    for preset in HAGEZI_PRESETS:
        nombre = _nombre_categoria(preset["slug"])
        url = HAGEZI_BASE_URL + preset["archivo_remoto"]
        descripcion = _descripcion_preset(preset["etiqueta"])

        acl = db.query(Acl).filter(Acl.name == nombre).first()
        if not acl:
            acl = Acl(
                name=nombre, type="dstdomain", value="", source="inline",
                is_category=True, enabled=True, description=descripcion,
                display_name=preset["etiqueta"],
            )
            db.add(acl)
            db.flush()
        acl.sync_url = url
        acl.is_category = True
        if not acl.description:
            acl.description = descripcion
        # No se pisa si el admin ya le puso un nombre propio -solo se
        # completa la primera vez que se crea (arriba) o si por algún
        # motivo quedó vacío.
        if not acl.display_name:
            acl.display_name = preset["etiqueta"]
        db.commit()

        resultado = sync_one(db, acl)
        resultados.append({"categoria": nombre, **resultado})

    return resultados


# Primera vuelta a los 5 minutos de arrancar -no compite con el resto de
# tareas de arranque del backend por salir a internet en el primer segundo.
_PRIMERA_ESPERA = 5 * 60
_INTERVALO_SYNC = 24 * 60 * 60


def _sync_loop():
    time.sleep(_PRIMERA_ESPERA)
    while True:
        try:
            db = SessionLocal()
            try:
                from app.models.acl import Acl

                categorias = db.query(Acl).filter(Acl.sync_url.isnot(None)).all()
                for acl in categorias:
                    sync_one(db, acl)
            finally:
                db.close()
        except Exception as e:
            logger.error("Error en el ciclo de sincronización de categorías: %s", e)

        time.sleep(_INTERVALO_SYNC)


def start_category_sync():
    """Arranca el hilo de fondo una sola vez, al iniciar el backend. Mismo
    patrón que update_service.start_update_checker(): hilo daemon, el propio
    bucle relee en cada vuelta qué categorías tienen sync_url -funciona
    igual en Docker y en nativo, no depende de systemd ni de cron."""
    thread = threading.Thread(target=_sync_loop, name="category-sync", daemon=True)
    thread.start()
