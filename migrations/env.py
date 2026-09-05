import os
from logging.config import fileConfig
from urllib.parse import quote_plus

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# No ORM models in this project (load.py uses raw SQL, not SQLAlchemy) - so
# there's nothing to autogenerate migrations FROM. Every migration here is
# written by hand. That also means `alembic revision --autogenerate` won't
# find any changes; use `alembic revision -m "..."` and write the
# upgrade()/downgrade() functions yourself.
target_metadata = None


def _database_url() -> str:
    """Build the connection URL from the same env vars load.py uses
    (DB_HOST, DB_PORT, POSTGRES_*), so this file - not alembic.ini - is the
    one place that needs to agree with the rest of the app on how to find
    the database."""
    load_dotenv()
    user = quote_plus(os.getenv("POSTGRES_USER") or "")
    password = quote_plus(os.getenv("POSTGRES_PASSWORD") or "")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    dbname = os.getenv("POSTGRES_DB") or ""
    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}"
    # ConfigParser interpolates %; quote_plus emits %XX so escape for Alembic.
    return url.replace("%", "%%")


config.set_main_option("sqlalchemy.url", _database_url())

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
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
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
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