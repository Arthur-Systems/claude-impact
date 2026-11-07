from alembic import context
from sqlalchemy import create_engine, pool

from clearpath.core.config import Settings
from clearpath.db.base import Base
from clearpath.db import models  # noqa: F401 -- register every table in metadata
from clearpath.projects.tables import include_p5_object  # Person 5's migration owns those columns

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=Settings().database_url, target_metadata=target_metadata,
        include_object=include_p5_object, literal_binds=True, dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(Settings().database_url, poolclass=pool.NullPool)
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection, target_metadata=target_metadata, include_object=include_p5_object,
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
