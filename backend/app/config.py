"""Configuración central del backend SquidManager."""

import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Settings cargados desde variables de entorno."""

    # Database
    DATABASE_URL: str = "postgresql+psycopg://squid:squidpass123@db:5432/squidmanager"

    # Security
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 horas

    # Squid
    SQUID_CONFIG_PATH: str = "/etc/squid/squid.conf"
    SQUID_CONTAINER_NAME: str = "squidmgr-proxy"

    # App
    APP_NAME: str = "SquidManager API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    class Config:
        env_file = ".env"


settings = Settings()