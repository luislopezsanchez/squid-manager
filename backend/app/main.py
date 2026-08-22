"""App principal FastAPI - SquidManager Backend."""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base, SessionLocal
from app.models import *  # noqa: importa todos los modelos
from app.routes import auth, proxy_users, acls, access_rules, squid_config, ldap, delay_pools, audit, metrics, admins, backup, logs, notifications

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_db():
    """Crea tablas y datos iniciales."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Crear admin por defecto si no existe
        from app.models.admin import Admin
        from app.services.auth_service import get_password_hash

        admin = db.query(Admin).filter(Admin.username == "admin").first()
        if not admin:
            admin = Admin(
                username="admin",
                password_hash=get_password_hash("admin123"),
                email="admin@local",
                role="superadmin",
            )
            db.add(admin)
            logger.info("Admin por defecto creado: admin / admin123")

        # Configuración inicial de Squid
        from app.models.squid_settings import SquidSetting
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
            "cache_store_log": ("/var/log/squid/store.log", "logging", "Ruta del log de store"),
            "visible_hostname": ("squidmanager", "general", "Nombre visible del proxy"),
            "refresh_pattern": (". 0 20% 4320", "cache", "Patrón de refresco"),
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
    init_db()
    logger.info("Base de datos inicializada")
    yield
    logger.info("Deteniendo SquidManager Backend...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# CORS: permitir frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


@app.get("/")
async def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}