"""Cuotas de navegación: mide el consumo de cada usuario (local o LDAP)
leyendo el access.log y aplica la acción configurada (cortar la
navegación o limitar la velocidad) al agotarse, reseteando sola al
empezar el siguiente periodo (diario/semanal/mensual).

La cuota vive por nombre de usuario en su propia tabla (NavigationQuota,
ver ese modelo), no como columnas de ProxyUser: un usuario LDAP no tiene
fila en esa tabla, así que atar la cuota ahí lo dejaba afuera. Al
aplicar/revertir una acción, este módulo resuelve contra cuál de las dos
tablas (ProxyUser o LdapUser) corresponde actuar -son mecanismos de
deshabilitado distintos (htpasswd local vs. allow-list de LDAP), ver
_resolver_identidad().

Mismo patrón que syslog_service.py para leer el log: un hilo de fondo que
lo sigue como `tail -f` (ver log_service.read_new_lines), siempre activo
-no hace nada mientras no haya ninguna cuota configurada, igual que el
resto de mecanismos "apagados hasta que el admin los activa a
propósito". Usa su propio archivo de offset porque avanza a su propio
ritmo, independiente del de syslog.
"""

import calendar
import json
import logging
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

from app.database import SessionLocal
from app.models.navigation_quota import NavigationQuota
from app.models.proxy_user import ProxyUser
from app.models.ldap_user import LdapUser
from app.models.acl import Acl
from app.models.delay_pool import DelayPool
from app.models.audit_log import AuditLog
from app.services.log_service import read_new_lines, parse_line
from app.services.config_state import mark_dirty
from app.utils import utcnow

logger = logging.getLogger(__name__)

# Ni en /tmp: en instalación nativa el servicio corre con PrivateTmp=yes
# (systemd), así que /tmp se recrea vacío en cada arranque -perder el
# offset ahí hace que el próximo tick relea el access.log ENTERO desde el
# principio como si fuera todo tráfico nuevo, e infle quota_bytes_used con
# meses de consumo histórico de golpe (confirmado en vivo: una cuota recién
# creada mostró >50MB de "consumo" tras un simple reinicio del backend).
# Mismo criterio que metrics_service.py con .network_state.json -ver
# también la auditoría de seguridad de septiembre (hallazgo 05-004): una
# ruta fija y adivinable en /tmp, compartido con el resto del sistema en
# instalación nativa, es además un vector de symlink.
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_STATE_FILE = str(_BACKEND_DIR / ".quota_offset_state.json")
_POLL_SECONDS = 15.0
_SISTEMA = "Cuota de navegación"

PERIODOS_VALIDOS = ("daily", "weekly", "monthly")
ACCIONES_VALIDAS = ("cut", "throttle")

# A partir de que porcentaje del limite se avisa en el dashboard que un
# usuario esta por agotar su cuota -umbral orientativo, no configurable
# todavia: "cerca de" antes de que la accion ya se haya aplicado, no
# despues (eso ya se ve en la propia fila del usuario en Gestion > Usuarios).
UMBRAL_RIESGO = 0.8


def contar_cuotas_en_riesgo(db) -> int:
    """Cuantos usuarios con cuota activa ya consumieron 80% o mas de su
    limite, sin que la accion se haya aplicado todavia -para el dashboard."""
    if db is None:
        return 0
    en_riesgo = 0
    for q in db.query(NavigationQuota).all():
        if q.quota_action_applied or not q.quota_bytes:
            continue
        if (q.quota_bytes_used or 0) / q.quota_bytes >= UMBRAL_RIESGO:
            en_riesgo += 1
    return en_riesgo


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


def siguiente_inicio_periodo(inicio: datetime, period: str) -> datetime:
    """Cuándo arranca el próximo periodo. 'monthly' respeta meses de
    distinta longitud (el 31 de enero + 1 mes cae el 28 o 29 de febrero,
    no un 3 de marzo inventado por sumar 30 días a lo bruto)."""
    if period == "weekly":
        return inicio + timedelta(days=7)
    if period == "monthly":
        mes = inicio.month + 1
        anio = inicio.year + (mes - 1) // 12
        mes = ((mes - 1) % 12) + 1
        dia = min(inicio.day, calendar.monthrange(anio, mes)[1])
        return inicio.replace(year=anio, month=mes, day=dia)
    return inicio + timedelta(days=1)  # 'daily' (y cualquier valor inesperado, por seguridad)


def _resolver_identidad(db, username: str):
    """(tipo, fila) del dueño real de este nombre de usuario, o (None,
    None) si no corresponde a ningún usuario existente (ej. se borró
    después de configurarle la cuota). Si por algún motivo el mismo
    nombre existe como local Y como LDAP, gana el local -es la cuenta que
    de verdad se autentica contra Squid, la de LDAP en ese caso sería una
    coincidencia de nombre, no la misma identidad."""
    local = db.query(ProxyUser).filter(ProxyUser.username == username).first()
    if local:
        return "local", local
    ldap = db.query(LdapUser).filter(LdapUser.username == username).first()
    if ldap:
        return "ldap", ldap
    return None, None


def _acl_name_cuota(quota: NavigationQuota) -> str:
    """Nombre de ACL exclusivo de este mecanismo, por id de la cuota y no
    por nombre de usuario: los nombres de usuario admiten '.', las ACLs de
    Squid no (ver squid_names.NAME_PATTERN)."""
    return f"cuota_usuario_{quota.id}"


def _asegurar_acl_usuario(db, quota: NavigationQuota) -> str:
    """Crea (o reutiliza) la ACL proxy_auth que apunta a este usuario,
    para poder aplicarle un delay pool. No usa la lógica de creación de
    ACLs de la interfaz -esto corre en un hilo de fondo, sin admin ni
    request HTTP detrás."""
    nombre = _acl_name_cuota(quota)
    acl = db.query(Acl).filter(Acl.name == nombre).first()
    if not acl:
        acl = Acl(
            name=nombre, type="proxy_auth", value=quota.username,
            description=f"Cuota de navegación: {quota.username}", enabled=True,
        )
        db.add(acl)
        db.flush()
    elif acl.value != quota.username:
        acl.value = quota.username
    return nombre


def _cortar(db, quota: NavigationQuota) -> None:
    tipo, cuenta = _resolver_identidad(db, quota.username)
    if tipo is None:
        logger.warning(
            f"Cuota agotada para '{quota.username}', pero ese usuario ya no existe -no hay a quién cortar."
        )
        return

    if tipo == "local":
        from app.services.squid_service import write_passwd_file, write_digest_file, realm_actual, purge_credentials
        cuenta.enabled = False
        db.add(AuditLog(
            admin_id=None, admin_username=_SISTEMA,
            action="toggle", entity="proxy_user", entity_id=cuenta.id,
            old_value=f"Cuota de navegación agotada (periodo {quota.quota_period})",
            new_value="False",
        ))
        db.flush()
        write_passwd_file(db)
        write_digest_file(db, realm_actual(db))
        db.commit()
        # Igual que el interruptor manual: sin esto, un usuario ya
        # autenticado sigue navegando hasta que Squid re-valide sus
        # credenciales por su cuenta (credentialsttl, hasta 2 horas).
        purge_credentials()
    else:
        from app.services.squid_service import write_ldap_aux_files, reload_squid, purge_credentials
        from app.models.ldap_config import LdapConfig
        cuenta.enabled = False
        db.add(AuditLog(
            admin_id=None, admin_username=_SISTEMA,
            action="toggle", entity="ldap_user", entity_id=cuenta.id,
            old_value=f"Cuota de navegación agotada (periodo {quota.quota_period})",
            new_value="False",
        ))
        db.commit()
        config = db.query(LdapConfig).first()
        permitidos = [u.username for u in db.query(LdapUser).filter(LdapUser.enabled == True).all()]  # noqa: E712
        write_ldap_aux_files(config, permitidos)
        reload_squid()
        purge_credentials()

    logger.info(f"Cuota agotada: usuario '{quota.username}' ({tipo}) deshabilitado")


def _limitar(db, quota: NavigationQuota) -> None:
    from app.services.squid_service import apply_squid_config

    nombre_acl = _asegurar_acl_usuario(db, quota)
    velocidad = quota.quota_throttle_bytes_per_sec or 51200
    pool = db.query(DelayPool).filter(DelayPool.quota_id == quota.id).first()
    es_nuevo = pool is None
    if es_nuevo:
        pool = DelayPool(quota_id=quota.id, pool_class=1)
        db.add(pool)
    pool.acl_name = nombre_acl
    pool.pool_class = 1
    pool.parameters = f"{velocidad}/{velocidad}"
    pool.description = f"Cuota de navegación agotada: {quota.username}"
    pool.enabled = True
    db.flush()
    db.add(AuditLog(
        admin_id=None, admin_username=_SISTEMA,
        action="create" if es_nuevo else "update", entity="delay_pool", entity_id=pool.id,
        new_value=f"{quota.username} limitado a {velocidad} B/s por cuota agotada",
    ))
    db.commit()
    mark_dirty()
    resultado = apply_squid_config(db)
    if resultado["status"] != "ok":
        logger.error(
            f"No se pudo aplicar el límite de cuota para '{quota.username}': {resultado.get('message')}"
        )
    else:
        logger.info(f"Cuota agotada: usuario '{quota.username}' limitado a {velocidad} B/s")


def revertir_accion(db, quota: NavigationQuota) -> None:
    """Deshace lo que haya aplicado la cuota (cortar o limitar) -se llama
    tanto al empezar un periodo nuevo como cuando el admin quita o
    amplía la cuota a mano desde la API. Si el admin ya había reactivado
    al usuario por su cuenta mientras tanto, la parte de "cortar" es un
    no-op (enabled ya es True)."""
    tipo, cuenta = _resolver_identidad(db, quota.username)
    if tipo == "local" and quota.quota_action == "cut" and cuenta and not cuenta.enabled:
        from app.services.squid_service import write_passwd_file, write_digest_file, realm_actual
        cuenta.enabled = True
        db.add(AuditLog(
            admin_id=None, admin_username=_SISTEMA,
            action="toggle", entity="proxy_user", entity_id=cuenta.id,
            old_value="Nuevo periodo de cuota", new_value="True",
        ))
        db.flush()
        write_passwd_file(db)
        write_digest_file(db, realm_actual(db))
        db.commit()
    elif tipo == "ldap" and quota.quota_action == "cut" and cuenta and not cuenta.enabled:
        from app.services.squid_service import write_ldap_aux_files, reload_squid
        from app.models.ldap_config import LdapConfig
        cuenta.enabled = True
        db.add(AuditLog(
            admin_id=None, admin_username=_SISTEMA,
            action="toggle", entity="ldap_user", entity_id=cuenta.id,
            old_value="Nuevo periodo de cuota", new_value="True",
        ))
        db.commit()
        config = db.query(LdapConfig).first()
        permitidos = [u.username for u in db.query(LdapUser).filter(LdapUser.enabled == True).all()]  # noqa: E712
        write_ldap_aux_files(config, permitidos)
        reload_squid()

    pool = db.query(DelayPool).filter(DelayPool.quota_id == quota.id).first()
    if pool:
        from app.services.squid_service import apply_squid_config
        db.delete(pool)
        db.commit()
        mark_dirty()
        apply_squid_config(db)


def _procesar_cuota(db, quota: NavigationQuota, ahora: datetime) -> None:
    if not quota.quota_period_started_at:
        quota.quota_period_started_at = ahora
        db.commit()
        return

    siguiente = siguiente_inicio_periodo(quota.quota_period_started_at, quota.quota_period)
    if ahora >= siguiente:
        if quota.quota_action_applied:
            revertir_accion(db, quota)
        quota.quota_bytes_used = 0
        quota.quota_period_started_at = ahora
        quota.quota_action_applied = False
        db.commit()
        return

    if not quota.quota_action_applied and quota.quota_bytes_used >= quota.quota_bytes:
        if quota.quota_action == "throttle":
            _limitar(db, quota)
        else:
            _cortar(db, quota)
        quota.quota_action_applied = True
        db.commit()


def _acumular_consumo(db, lines: list[str]) -> None:
    if not lines:
        return
    consumo: dict[str, int] = {}
    for linea in lines:
        entrada = parse_line(linea)
        if entrada and entrada.get("user") and entrada.get("bytes"):
            consumo[entrada["user"]] = consumo.get(entrada["user"], 0) + entrada["bytes"]
    if not consumo:
        return

    cuotas = (
        db.query(NavigationQuota)
        .filter(NavigationQuota.username.in_(consumo.keys()))
        .all()
    )
    for quota in cuotas:
        quota.quota_bytes_used = (quota.quota_bytes_used or 0) + consumo[quota.username]
    db.commit()


def _tick() -> None:
    db = SessionLocal()
    try:
        offset = _load_offset()
        lines, new_offset = read_new_lines(offset)
        _acumular_consumo(db, lines)
        _save_offset(new_offset)

        ahora = utcnow()
        for quota in db.query(NavigationQuota).all():
            try:
                _procesar_cuota(db, quota, ahora)
            except Exception as e:
                db.rollback()
                logger.error(f"Error procesando la cuota de '{quota.username}': {e}")
    finally:
        db.close()


def _loop() -> None:
    logger.info("Seguidor de cuotas de navegación iniciado")
    while True:
        try:
            _tick()
        except Exception as e:
            logger.error(f"Error en el seguidor de cuotas de navegación: {e}")
        time.sleep(_POLL_SECONDS)


def start_quota_tracker() -> None:
    """Arranca el hilo de fondo una sola vez, al iniciar el backend."""
    thread = threading.Thread(target=_loop, name="quota-tracker", daemon=True)
    thread.start()
