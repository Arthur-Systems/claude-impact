"""Synchronous sessions. The caller owns commit/rollback; closing never commits."""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from clearpath.core.config import Settings, get_settings


def create_session_factory(settings: Settings) -> sessionmaker[Session]:
    engine = create_engine(
        settings.database_url.get_secret_value(),
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={"connect_timeout": 2},
    )
    return sessionmaker(bind=engine, expire_on_commit=False)


@lru_cache
def default_session_factory() -> sessionmaker[Session]:
    return create_session_factory(get_settings())


def get_session() -> Iterator[Session]:
    """CLI/service dependency using cached environment settings, without auto-commit."""
    with default_session_factory()() as session:
        yield session


def dispose_session_factory(factory: sessionmaker[Session]) -> None:
    engine = factory.kw["bind"]
    if isinstance(engine, Engine):
        engine.dispose()
