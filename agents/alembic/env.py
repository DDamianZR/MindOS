"""Entorno de migraciones Alembic (async + offline) del servicio de agentes (Fase 9).

Comparte la base de Postgres con Memory pero lleva su propia tabla de versión
(`alembic_version_agents`), así las dos cadenas de migraciones no se mezclan.
"""
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from agents.src.config import settings
from agents.src.infrastructure.database.models import Base

config = context.config
# La URL canónica proviene de la configuración del servicio (no del .ini).
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
VERSION_TABLE = "alembic_version_agents"


def run_migrations_offline() -> None:
    """Modo offline: emite el SQL sin conectarse (útil para revisar/validar la migración)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table=VERSION_TABLE,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, version_table=VERSION_TABLE)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Modo online: aplica las migraciones contra la base de datos real (async)."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
