"""App principal FastAPI - SquidManager Backend."""

import logging
import secrets
import string
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect
from sqlalchemy.exc import OperationalError

from fastapi import Request
from fastapi.exception_handlers import http_exception_handler
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.i18n import idioma_de_cabecera, traducir
from app.database import engine, SessionLocal
from app.models import *  # noqa: importa todos los modelos
from app.routes import auth, proxy_users, acls, access_rules, squid_config, ldap, delay_pools, audit, metrics, admins, backup, logs, notifications, user_groups, syslog, parent_proxy
from app.middleware import rate_limit_middleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _explicar_fallo_de_conexion(error: Exception) -> None:
    """Traduce un fallo de conexión con la base a algo accionable.

    Sin esto, el arranque muere con un volcado de más de cien líneas de
    SQLAlchemy donde la causa real aparece enterrada en la penúltima. La más
    habitual, además, no se adivina leyendo el error: el volumen de datos de
    PostgreSQL viene de una instalación anterior y conserva su contraseña,
    porque POSTGRES_PASSWORD solo se aplica al crear la base por primera vez.
    """
    detalle = str(error)

    if "password authentication failed" in detalle:
        logger.error(
            "\n"
            "  No se pudo entrar en la base de datos: contraseña rechazada.\n"
            "\n"
            "  Lo más probable es que el volumen de PostgreSQL venga de una\n"
            "  instalación anterior. La contraseña de una base ya creada no se\n"
            "  cambia poniendo otra en el .env: POSTGRES_PASSWORD solo surte\n"
            "  efecto la primera vez, cuando la base se crea vacía.\n"
            "\n"
            "  Dos salidas:\n"
            "\n"
            "  1) Empezar de cero. BORRA TODOS LOS DATOS (usuarios del proxy,\n"
            "     reglas, historial):\n"
            "         docker compose down -v && docker compose up -d\n"
            "\n"
            "  2) Conservar los datos: recupera la DB_PASS con la que se creó\n"
            "     la base y ponla en el .env, luego:\n"
            "         docker compose up -d\n"
        )
    elif "could not translate host name" in detalle or "Connection refused" in detalle:
        logger.error(
            "\n"
            "  No se pudo contactar con la base de datos.\n"
            "\n"
            "  Comprueba que el contenedor está en marcha y sano:\n"
            "      docker compose ps db\n"
            "      docker compose logs db\n"
        )
    else:
        logger.error(f"No se pudo conectar a la base de datos: {detalle}")


def run_migrations():
    """Pone el esquema al día con Alembic.

    Si la base ya tiene tablas pero no historial de Alembic (instalaciones
    anteriores, creadas con create_all), se marca la revisión baseline y a
    partir de ahí se aplican las migraciones nuevas con normalidad.
    """
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))

    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
    except OperationalError as e:
        _explicar_fallo_de_conexion(e)
        raise

    if "alembic_version" not in tables and "admins" in tables:
        logger.info("Base de datos preexistente sin historial de Alembic: marcando baseline 0001")
        command.stamp(cfg, "0001")

    command.upgrade(cfg, "head")

    # Alembic reconfigura el logging al migrar y deja el nivel raíz en el que
    # declara su alembic.ini (WARN), por debajo del que usa la aplicación. Sin
    # devolverlo a su sitio, todo lo que el backend registre con logger.info()
    # a partir de aquí se descarta en silencio: el arranque parecía cortarse a
    # mitad y en producción se perdían los avisos informativos.
    logging.getLogger().setLevel(logging.INFO)

    logger.info("Migraciones aplicadas")


def seed_data():
    """Crea el administrador inicial y la configuración por defecto de Squid."""
    from app.models.admin import Admin
    from app.models.squid_settings import SquidSetting
    from app.services.auth_service import get_password_hash

    db = SessionLocal()
    try:
        admin = db.query(Admin).filter(Admin.username == "admin").first()
        if not admin:
            # Sin contraseña fija en el código: o la define el operador por
            # entorno, o se genera aleatoria y se muestra una única vez.
            password = settings.ADMIN_INITIAL_PASSWORD
            generated = False
            if not password:
                alphabet = string.ascii_letters + string.digits
                password = "".join(secrets.choice(alphabet) for _ in range(16))
                generated = True

            admin = Admin(
                username="admin",
                password_hash=get_password_hash(password),
                email="admin@local",
                role="superadmin",
                must_change_password=True,
            )
            db.add(admin)
            if generated:
                logger.warning(
                    "Administrador inicial creado.\n"
                    "    Usuario:    admin\n"
                    f"    Contraseña: {password}\n"
                    "    Se pedirá cambiarla en el primer inicio de sesión. "
                    "Esta contraseña no se vuelve a mostrar."
                )
            else:
                logger.info("Administrador inicial creado con ADMIN_INITIAL_PASSWORD")

        defaults = {
            "http_port": ("3128", "network", "Puerto de escucha del proxy"),
            "cache_mem": ("128 MB", "cache", "Memoria RAM para caché"),
            "cache_dir": ("ufs /var/spool/squid 100 16 256", "cache", "Directorio de caché en disco"),
            "maximum_object_size": ("4 MB", "cache", "Tamaño máximo de objeto cacheable"),
            "auth_children": ("5", "security", "Procesos helper de autenticación"),
            "auth_realm": ("SquidManager Proxy", "security", "Realm de autenticación"),
            "credentialsttl": ("2 hours", "security", "TTL de credenciales"),
            "access_log": ("/var/log/squid/access.log", "logging", "Ruta del log de acceso"),
            "cache_log": ("/var/log/squid/cache.log", "logging", "Ruta del log de caché"),
            # Con un sufijo único por instalación, no por capricho: Squid
            # rechaza como bucle de reenvío cualquier petición cuya cabecera
            # Via ya lleve su propio nombre. Dos SquidManager encadenados con
            # el mismo nombre se cortan entre sí, y el error que devuelven
            # ("403 Acceso Denegado") no menciona el motivo.
            "visible_hostname": (
                f"squidmanager-{secrets.token_hex(3)}", "general",
                "Nombre con el que el proxy se identifica. Debe ser distinto "
                "en cada proxy de una cadena: Squid corta como bucle lo que "
                "ya lleve su nombre en la cabecera Via.",
            ),
            "refresh_pattern": (". 0 20% 4320", "cache", "Patrón de refresco"),
            "error_language": ("es", "general", "Idioma de las páginas de error"),
            "ssl_bump_exclude": (
                "", "security",
                "Dominios que NO se descifran (uno por línea o separados por espacios)",
            ),
        }
        for key, (value, category, description) in defaults.items():
            if not db.query(SquidSetting).filter(SquidSetting.key == key).first():
                db.add(SquidSetting(key=key, value=value, category=category, description=description))
        logger.info("Configuración inicial de Squid cargada")

        db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Iniciando SquidManager Backend...")
    run_migrations()
    seed_data()
    logger.info("Base de datos inicializada")

    from app.services.syslog_service import start_syslog_forwarder
    start_syslog_forwarder()

    yield
    logger.info("Deteniendo SquidManager Backend...")


# La documentación interactiva queda expuesta solo en modo depuración: sin
# autenticación delante, es un mapa completo de la API para cualquiera.
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
)

# CORS: lista explícita de orígenes. Con "*" y allow_credentials=True Starlette
# refleja el origen de quien pregunte, que equivale a no tener CORS.
if settings.cors_origin_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

# Traduccion de los mensajes de error.
#
# Se hace en un solo sitio, y no en los 60 puntos donde se lanzan, porque la
# clave de cada mensaje es el propio texto en espanol: no hay que tocar ninguna
# ruta, y un mensaje que todavia no este traducido sale en espanol en lugar de
# como un codigo interno. Sin esto, traducir solo el panel deja una aplicacion
# que esta en ingles hasta que algo falla y entonces contesta en espanol.
@app.exception_handler(StarletteHTTPException)
async def traducir_errores(request: Request, exc: StarletteHTTPException):
    if isinstance(exc.detail, str):
        idioma = idioma_de_cabecera(request.headers.get("accept-language"))
        exc = StarletteHTTPException(
            status_code=exc.status_code,
            detail=traducir(exc.detail, idioma),
            headers=getattr(exc, "headers", None),
        )
    return await http_exception_handler(request, exc)


# Rate limiting (anti fuerza bruta)
app.middleware("http")(rate_limit_middleware)

# Registrar rutas
app.include_router(auth.router, prefix="/api/auth", tags=["Autenticación"])
app.include_router(proxy_users.router, prefix="/api/proxy-users", tags=["Usuarios del Proxy"])
app.include_router(acls.router, prefix="/api/acls", tags=["ACLs"])
app.include_router(access_rules.router, prefix="/api/access-rules", tags=["Reglas de Acceso"])
app.include_router(squid_config.router, prefix="/api/squid", tags=["Configuración Squid"])
app.include_router(ldap.router, prefix="/api/ldap", tags=["LDAP"])
app.include_router(delay_pools.router, prefix="/api/delay-pools", tags=["Delay Pools"])
app.include_router(audit.router, prefix="/api/audit", tags=["Auditoría"])
app.include_router(metrics.router, prefix="/api/metrics", tags=["Métricas"])
app.include_router(admins.router, prefix="/api/admins", tags=["Administradores"])
app.include_router(backup.router, prefix="/api/backup", tags=["Backup/Restore/Import"])
app.include_router(logs.router, prefix="/api/logs", tags=["Logs"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["Notificaciones"])
app.include_router(user_groups.router, prefix="/api/groups", tags=["Grupos de usuarios"])
app.include_router(syslog.router, prefix="/api/syslog", tags=["Syslog externo"])
app.include_router(parent_proxy.router, prefix="/api/parent-proxy", tags=["Proxy padre"])


@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


@app.get("/health")
async def health():
    return {"status": "ok"}
