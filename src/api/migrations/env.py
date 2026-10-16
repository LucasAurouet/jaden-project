"""
Environnement Alembic : migrations écrites en SQL brut (pas d'ORM, donc pas d'autogenerate).
Exécuté par la CLI (`alembic upgrade head`) ou par init_db au démarrage du serveur.
"""
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection, make_url
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from config import DATABASE_URL

config = context.config

# Au démarrage du serveur, init_db passe embedded=True : on ne touche pas à la
# configuration des logs d'uvicorn.
if config.config_file_name is not None and not config.attributes.get("embedded"):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Même base que l'application, via le même pilote asyncpg.
URL = make_url(DATABASE_URL).set(drivername="postgresql+asyncpg")


def run_migrations_offline() -> None:
    """`alembic upgrade head --sql` : affiche le SQL sans se connecter."""
    context.configure(url=URL, target_metadata=None, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    # transaction_per_migration : une migration qui échoue n'annule pas les précédentes.
    context.configure(connection=connection, target_metadata=None, transaction_per_migration=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(URL, poolclass=pool.NullPool)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
