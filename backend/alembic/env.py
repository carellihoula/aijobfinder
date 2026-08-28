import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

from app.config import settings
from app.db.session import Base

# Import all models so Alembic can detect them
import app.users.models   # noqa: F401
import app.cv.models      # noqa: F401
import app.analysis.models  # noqa: F401
import app.applications.models  # noqa: F401
import app.notifications.models  # noqa: F401
import app.cover_letter.models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Inject the URL from app settings — single source of truth
# % must be escaped as %% to avoid ConfigParser interpolation errors (e.g. %40 in passwords)
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL.replace("%", "%%"))

# Tables managed by a separate engine (CORTEX_DATABASE_URL) — exclude from autogenerate
_CORTEX_TABLES = {"cortex_jobs"}


def include_object(obj, name, type_, reflected, compare_to):
    if type_ == "table" and name in _CORTEX_TABLES:
        return False
    return True


target_metadata = Base.metadata


def run_migrations_offline() -> None:
    # Offline mode uses the sync URL to render SQL without a live connection
    url = settings.DATABASE_URL.replace("+aiosqlite", "")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, include_object=include_object)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()