from alembic import context
from sqlalchemy import create_engine, pool

from clearpath.core.config import get_settings
from clearpath.db.base import Base

# Task 2 imports clearpath.db.models here to register the model metadata.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=get_settings().database_url, target_metadata=target_metadata,
        literal_binds=True, dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(get_settings().database_url, poolclass=pool.NullPool)
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
