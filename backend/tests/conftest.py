import os

import pytest
from fastapi.testclient import TestClient

from clearpath.api.app import create_app
from clearpath.core.config import Settings


def require_test_database(database_url: str) -> str:
    """Refuse the dev database before any integration fixture connects."""
    from sqlalchemy.engine import make_url

    name = make_url(database_url).database
    if not name or not name.startswith("clearpath_test"):
        raise ValueError("Tests require a database name starting with clearpath_test.")
    return name


@pytest.fixture
def settings():
    settings = Settings(
        _env_file=None,
        database_url=os.environ.get("DATABASE_URL", "postgresql+psycopg://clearpath:clearpath@127.0.0.1:5432/clearpath_test"),
        api_key="test-key",
        mode="synthetic",
        cors_origins=[],
    )
    require_test_database(settings.database_url)
    return settings


@pytest.fixture
def test_database_name(settings):
    return require_test_database(settings.database_url)


@pytest.fixture
def db_session(settings, test_database_name):
    """Rollback-only session for tests that need real PostgreSQL constraints."""
    from sqlalchemy.engine import make_url
    from sqlalchemy.orm import Session
    from clearpath.db.session import get_engine

    url = make_url(settings.database_url)
    assert url.database == test_database_name
    with get_engine(settings.database_url).connect() as connection:
        transaction = connection.begin()
        try:
            with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
                yield session
        finally:
            transaction.rollback()


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        yield client
