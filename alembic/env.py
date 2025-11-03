# --- START OF FILE: alembic/env.py ---
import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from dotenv import load_dotenv

from alembic import context

# CRITICAL CHANGE: Load the .env file from the project root.
# The alembic.ini file defines the URL, but this action loads the
# variables (like POSTGRES_USER) into the environment so they can be used.
# The path is relative to the project root where you run the 'alembic' command.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
dotenv_path = os.path.join(project_root, '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
else:
    # This will cause a loud failure if the .env file is missing, which is what we want.
    raise FileNotFoundError(f"FATAL: .env file not found at {dotenv_path}")

# CRITICAL CHANGE: Add the project's root directory to the Python path.
# REASON: This is essential for Alembic to find and import your 'cogops' module
# and the database models defined within it.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# CRITICAL CHANGE: Import your SQLAlchemy Base model from your existing db.py file.
# REASON: This is how Alembic discovers the table schemas it is responsible for managing.
from cogops.retriver.db import Base as ApplicationModelsBase

# This is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# CRITICAL CHANGE: Set the target_metadata to your application's Base model.
# REASON: This tells Alembic that any tables defined using your ApplicationModelsBase
# (like 'passages' and the future 'conversation_history' table) should be tracked for changes.
target_metadata = ApplicationModelsBase.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # CRITICAL ADDITION: Manually construct the database URL.
    # REASON: The .ini file parsing is unreliable. We build the URL here
    # using os.getenv to guarantee the correct values are used.
    # This is the final, definitive fix.
    db_url = (
        f"postgresql+psycopg2://{os.getenv('POSTGRES_USER')}:{os.getenv('POSTGRES_PASSWORD')}@"
        f"{os.getenv('POSTGRES_HOST')}:{os.getenv('POSTGRES_PORT')}/{os.getenv('POSTGRES_DB')}"
    )

    # Create a dictionary with the manually constructed URL.
    config_section = config.get_section(config.config_ini_section, {})
    config_section['sqlalchemy.url'] = db_url

    connectable = engine_from_config(
        config_section, # Pass our corrected configuration here
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

# --- END OF FILE: alembic/env.py ---