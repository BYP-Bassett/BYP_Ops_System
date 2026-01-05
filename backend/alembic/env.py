from __future__ import annotations

import os
import sys
from pathlib import Path
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Alembic Config object (read from alembic.ini)
config = context.config

# Configure Python logging from the config file
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# --- Make sure our backend package is importable ---
# This file lives at: <backend>\alembic\env.py
# So the backend root is the parent of this file's parent.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# --- Import SQLAlchemy metadata for autogenerate ---
# NOTE: We import the Base *and* import model modules so their tables are registered.
try:
    from app.models.base import Base  # type: ignore
except Exception:  # pragma: no cover
    # Fallback if your Base is exposed differently
    from app.models import Base  # type: ignore

# Import models so Alembic "sees" them for autogenerate
try:
    import importlib
    for mod in ("app.models.orders", "app.models.sp_master", "app.models.audit_log"):
        try:
            importlib.import_module(mod)
        except Exception:
            pass
except Exception:
    pass

target_metadata = Base.metadata


def _get_database_url() -> str:
    # Prefer DATABASE_URL if set (useful later for Postgres), otherwise alembic.ini.
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        return env_url
    return config.get_main_option("sqlalchemy.url")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = _get_database_url()
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
    # Override sqlalchemy.url from env var if provided
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _get_database_url()

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
