import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# --- target_metadata wiring (IMPORTANT) ---
try:
    from app.models.base import Base
except Exception:
    # Fallback if base was moved/renamed
    from app.models import Base  # type: ignore

target_metadata = Base.metadata

# Import models so Alembic autogenerate can see tables
from app.models import orders  # noqa: F401
from app.models import sp_master  # noqa: F401
from app.models import audit_log  # noqa: F401
from app.models import users  # noqa: F401
from app.models import clients  # noqa: F401


def get_url():
    # Mirror runtime DATABASE_URL logic:
    # Prefer env var, otherwise rely on alembic.ini's sqlalchemy.url
    url = os.getenv("DATABASE_URL")
    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = get_url() or config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    configuration = config.get_section(config.config_ini_section) or {}

    env_url = get_url()
    if env_url:
        configuration["sqlalchemy.url"] = env_url

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
