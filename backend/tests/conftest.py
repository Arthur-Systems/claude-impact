import os

import pytest
from fastapi.testclient import TestClient

from clearpath.api.app import create_app
from clearpath.core.config import Settings


@pytest.fixture
def settings():
    return Settings(
        _env_file=None,
        database_url=os.environ.get("DATABASE_URL", "postgresql+psycopg://clearpath:clearpath@127.0.0.1:5432/clearpath_test"),
        api_key="test-key",
        mode="synthetic",
        cors_origins=[],
    )


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        yield client
