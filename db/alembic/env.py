"""Alembic env.py for TelegramOllama SQLite DB."""
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Add parent directory to sys.path for api imports
# In Docker: /app/db/alembic/env.py → /app (where api/ is located)
parent_dir = Path(__file__).resolve().parents[2]  # Go up from db/alembic/env.py to /app
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
import models  # CI: PYTHONPATH includes api/, Docker: models.py in /app
target_metadata = models.Base.metadata

# Allow override via ALEMBIC_URL env var
db_url = os.getenv("ALEMBIC_URL") or config.get_main_option("sqlalchemy.url")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    context.configure(
        url=db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        {"sqlalchemy.url": db_url},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

