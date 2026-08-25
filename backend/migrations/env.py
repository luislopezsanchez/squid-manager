"""Entorno de Alembic para SquidManager."""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

from app.config import settings
from app.database import Base
from app.models import *  # noqa: F401,F403  importa todos los modelos

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    # disable_existing_loggers=False no es opcional aquí.
    #
    # fileConfig() desactiva por defecto todos los loggers que no aparezcan en
    # el alembic.ini, y ahí solo están root, sqlalchemy y alembic. Como las
    # migraciones se ejecutan durante el arranque del backend, en cuanto
    # terminaban dejaban muda a la aplicación entera: no se veía «Migraciones
    # aplicadas», ni la contraseña del administrador recién creado, ni el
    # «Application startup complete» de uvicorn, ni ningún error posterior en
    # producción. El log se cortaba siempre en la zona de Alembic y parecía que
    # el backend se hubiera colgado, cuando en realidad seguía funcionando.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
