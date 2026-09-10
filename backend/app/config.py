"""Configuración central del backend SquidManager."""

import logging
import secrets

from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

# Valor que traía el código por defecto. Si sigue puesto en producción, la
# clave de firma de los JWT es pública: cualquiera puede fabricarse un token.
INSECURE_SECRET_KEYS = {
    "change-me-in-production",
    "changeme-in-production-please",
    "dev-secret-key-change-in-production-2026",
}


class Settings(BaseSettings):
    """Settings cargados desde variables de entorno."""

    # Database
    #
    # Sin valor por defecto a propósito: los dos despliegues soportados
    # (docker-compose.yml y install-nativo.sh) siempre la fijan con
    # credenciales generadas, así que un valor de ejemplo aquí no protege a
    # nadie y solo invita a que alguien lo copie a un .env real. Si falta, el
    # arranque debe fallar con un error claro, no conectarse en silencio a
    # algo que no existe.
    DATABASE_URL: str

    # Security
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 horas

    # Clave para cifrar en reposo las credenciales de terceros guardadas en
    # la base (bind_password de LDAP, smtp_password, telegram_bot_token, las
    # API keys del asistente de IA, la contraseña del proxy padre, el keytab
    # de Kerberos -ver crypto_service.py). Deliberadamente separada de
    # SECRET_KEY: rotar la firma de los JWT (invalida sesiones) no debería
    # obligar a re-cifrar toda la configuración, y viceversa (auditoría
    # 2026-09-09, hallazgo 05-003). Vacía = sin cifrar -compatibilidad con
    # instalaciones existentes hasta que se configure; ver crypto_service.py
    # para el comportamiento exacto en ese caso.
    DATA_KEY: str = ""

    # Orígenes permitidos por CORS. El frontend se sirve desde el mismo origen
    # a través de nginx, así que por defecto no se permite ninguno externo.
    CORS_ORIGINS: str = ""

    # Coste de bcrypt para las contraseñas de los usuarios del proxy.
    # htpasswd usa 5 por defecto, muy por debajo de lo recomendado.
    BCRYPT_COST: int = 12

    # Contraseña inicial del admin. Si se deja vacía se genera una aleatoria
    # y se escribe en el log del backend una sola vez.
    ADMIN_INITIAL_PASSWORD: str = ""

    # Squid
    SQUID_CONFIG_PATH: str = "/etc/squid/squid.conf"
    SQUID_CONTAINER_NAME: str = "squidmgr-proxy"

    # Como esta desplegado Squid: "docker" (contenedor, por defecto) o
    # "native" (instalado en el sistema y gobernado por systemd). Por defecto
    # docker para que las instalaciones que ya existen no cambien de
    # comportamiento al actualizar.
    DEPLOY_MODE: str = "docker"

    # Nombre de la unidad de systemd, solo en modo nativo.
    NATIVE_SQUID_SERVICE: str = "squid"

    # App
    APP_NAME: str = "SquidManager API"
    # Única fuente de verdad: CHANGELOG.md. Antes esta constante se quedaba
    # atrás (llegó a marcar 0.6.0 mientras el CHANGELOG iba por 0.14.0) porque
    # nada la sincronizaba con las otras dos versiones que declara el
    # proyecto (aquí y en frontend/package.json). Al subir la versión, las
    # tres deben moverse juntas y etiquetarse en git — ver docs/actualizacion.md.
    APP_VERSION: str = "0.24.6"
    DEBUG: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def secret_key_is_insecure(self) -> bool:
        return self.SECRET_KEY in INSECURE_SECRET_KEYS or len(self.SECRET_KEY) < 32


settings = Settings()

if settings.DEPLOY_MODE.strip().lower() not in {"docker", "native"}:
    logger.warning(
        f"DEPLOY_MODE='{settings.DEPLOY_MODE}' no se reconoce; se usara 'docker'. "
        f"Valores validos: docker, native."
    )

if settings.secret_key_is_insecure:
    if settings.DEBUG:
        logger.warning(
            "SECRET_KEY es la de por defecto o demasiado corta. Válido para "
            "desarrollo; en producción genera una con: openssl rand -hex 32"
        )
    else:
        # En producción no se arranca con una clave de firma conocida: se
        # genera una aleatoria, que invalida los tokens en cada reinicio y
        # hace el problema visible en lugar de silencioso.
        settings.SECRET_KEY = secrets.token_hex(32)
        logger.error(
            "SECRET_KEY insegura: se ha generado una temporal. Las sesiones se "
            "cerrarán en cada reinicio hasta que definas SECRET_KEY en el .env "
            "(openssl rand -hex 32)."
        )
