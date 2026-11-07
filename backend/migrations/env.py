"""Alembic shares the explicit PostgreSQL settings and ORM metadata."""

from alembic import context
from sqlalchemy import create_engine

from clearpath.core.config import Settings
from clearpath.db.models import Base


def run_migrations():
    url = Settings().database_url.get_secret_value()
    if context.is_offline_mode():
        context.configure(
            url=url,
            target_metadata=Base.metadata,
            literal_binds=True,
            dialect_opts={"paramstyle": "named"},
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
        return
    engine = create_engine(url, hide_parameters=True)
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection, target_metadata=Base.metadata, compare_type=True
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


run_migrations()
