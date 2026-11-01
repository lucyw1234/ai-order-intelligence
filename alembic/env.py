import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from sqlalchemy.engine import make_url
from alembic import context
from db_models import Base
from dotenv import load_dotenv

config = context.config
load_dotenv()

# Configure DATABASE_URL from environment
database_url = make_url(os.getenv("DATABASE_URL", "sqlite:///./orders.db"))
if database_url.drivername == "postgresql+asyncpg":
    database_url = database_url.set(drivername="postgresql+psycopg2")
elif database_url.drivername == "sqlite+aiosqlite":
    database_url = database_url.set(drivername="sqlite")
DATABASE_URL = database_url.render_as_string(hide_password=False)

config.set_main_option('sqlalchemy.url', DATABASE_URL)


class SilenceLogger:
    def debug(self, *args, **kwargs): pass
    def info(self, *args, **kwargs): pass
    def warning(self, *args, **kwargs): pass
    def error(self, *args, **kwargs): pass
    def critical(self, *args, **kwargs): pass


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
        connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=Base.metadata,
            include_schemas=True,
            process_revision_directives=lambda context, rev, gen: gen,
            compare_type=True,
            render_as_batch=True
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    raise NotImplementedError("Offline mode not supported for async databases")
else:
    run_migrations_online()