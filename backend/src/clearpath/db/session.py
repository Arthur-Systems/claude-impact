from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from clearpath.core.config import Settings, get_settings


@lru_cache
def _engine_for_url(database_url: str) -> Engine:
    return create_engine(
        database_url, pool_pre_ping=True, hide_parameters=True, connect_args={"connect_timeout": 2},
    )


def get_engine(database_url: str | None = None) -> Engine:
    """Create engines lazily, keyed by URL so test/prod settings stay isolated."""
    return _engine_for_url(database_url or get_settings().database_url)


def SessionLocal(settings: Settings | None = None) -> Session:
    """Open a session; callers own its transaction and must close it."""
    settings = settings or get_settings()
    return Session(bind=get_engine(settings.database_url))


def get_session(settings: Annotated[Settings | None, Depends(get_settings)] = None) -> Iterator[Session]:
    """Routes/CLI commit; services never commit. Always close on dependency exit."""
    with SessionLocal(settings) as session:
        yield session
