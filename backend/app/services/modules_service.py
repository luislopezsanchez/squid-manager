"""Módulos opcionales del panel: qué secciones se muestran.

Un módulo apagado se oculta del menú y de las rutas del panel. NO detiene la
recolección de datos (los agregados de actividad siguen calculándose, para que
al encenderlo no falte historia) ni el rol de «nodo monitorizado» de este
servidor (ver /api/central/dashboard, que responde siempre a un padre con
credenciales válidas).
"""
from datetime import datetime, timezone

from sqlalchemy import text

# clave -> (activo por defecto, título, descripción)
MODULOS = {
    "analisis": (True, "Análisis",
                 "Actividad de red, estado del caché, latencia y errores, tendencias y panorama."),
    "panel_central": (False, "Panel central (monitoreo de varios proxies)",
                      "Para quien administra varios Squid: muestra el estado de todos en un solo panel. "
                      "Apagado por defecto."),
    "asistente": (True, "Asistente de IA",
                  "Responde preguntas sobre el uso de la plataforma. Además de mostrarlo, necesita configurar un proveedor."),
}


def _filas(db) -> dict[str, bool]:
    return {k: bool(v) for k, v in db.execute(text("SELECT key, enabled FROM app_modules")).fetchall()}


def get_all(db) -> dict[str, bool]:
    guardado = _filas(db)
    return {k: guardado.get(k, d[0]) for k, d in MODULOS.items()}


def is_enabled(db, clave: str) -> bool:
    return get_all(db).get(clave, True)


def set_enabled(db, clave: str, enabled: bool) -> None:
    if clave not in MODULOS:
        raise KeyError(clave)
    ahora = datetime.now(timezone.utc).replace(tzinfo=None)
    db.execute(
        text("INSERT INTO app_modules (key, enabled, updated_at) VALUES (:k, :e, :t) "
             "ON CONFLICT (key) DO UPDATE SET enabled = EXCLUDED.enabled, updated_at = EXCLUDED.updated_at"),
        {"k": clave, "e": enabled, "t": ahora},
    )
