import pytest
from fastapi.testclient import TestClient


def test_health_live():
    from clearpath.api.app import create_app
    from clearpath.core.config import Settings
    with TestClient(create_app(Settings(api_key="test-key"))) as client:
        response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Request-ID"]


def assert_envelope(response, status, code):
    from uuid import UUID
    assert response.status_code == status
    body = response.json()
    assert set(body) == {"error", "request_id"}
    assert set(body["error"]) == {"code", "message", "details"}
    assert body["error"]["code"] == code
    assert UUID(body["request_id"]).version == 4
    assert body["request_id"] == response.headers["X-Request-ID"]


def test_api_key_required(client):
    import json
    from pathlib import Path

    example = json.loads((Path(__file__).resolve().parents[1]
                          / "fixtures/api_examples/error_envelope.json").read_text())
    for headers in ({}, {"X-API-Key": "wrong"}):
        response = client.get("/api/v1/_ping", headers=headers)
        assert_envelope(response, 401, "missing_api_key")
        assert response.json()["error"] == example["response"]["error"]
        assert response.json()["error"]["message"] == "The X-API-Key header is missing or wrong."
    response = client.get("/api/v1/_ping", headers={"X-API-Key": "test-key"})
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert response.headers["X-Request-ID"]


def test_extra_fields_rejected(client):
    response = client.post("/api/v1/_echo", json={"name": "x", "SENTINEL secret": "secretvalue"}, headers={"X-API-Key": "test-key"})
    assert_envelope(response, 422, "validation_error")
    assert "secretvalue" not in response.text
    assert "SENTINEL secret" not in response.text
    assert response.json()["error"]["details"]["fields"] == [{"loc": ["body", "*"], "type": "extra_forbidden"}]
    assert client.post("/api/v1/_echo", json={"name": "x"}, headers={"X-API-Key": "test-key"}).json() == {"name": "x"}


def test_nested_validation_masks_only_input_controlled_locations(settings):
    from clearpath.api.app import create_app
    from clearpath.domain.schemas import StrictModel

    class Child(StrictModel):
        name: str

    class Payload(StrictModel):
        entries: list[Child]
        facts: dict[str, int]
        optional: Child | None = None

    app = create_app(settings)

    @app.post("/nested-probe")
    def nested(body: Payload):
        return body

    with TestClient(app) as client:
        response = client.post("/nested-probe", json={
            "entries": [{"name": 1, "SENTINEL secret": "SENTINEL value"}],
            "facts": {"SENTINEL secret": "SENTINEL value", "name": "SENTINEL value"},
            "optional": {"name": "ok", "SENTINEL secret": True},
        })
    assert_envelope(response, 422, "validation_error")
    assert "SENTINEL" not in response.text
    assert response.json()["error"]["details"]["fields"] == [
        {"loc": ["body", "entries", 0, "name"], "type": "string_type"},
        {"loc": ["body", "entries", 0, "*"], "type": "extra_forbidden"},
        {"loc": ["body", "facts", "*"], "type": "int_parsing"},
        {"loc": ["body", "facts", "*"], "type": "int_parsing"},
        {"loc": ["body", "optional", "*"], "type": "extra_forbidden"},
    ]


def test_query_validation_keeps_declared_dependency_field(settings):
    from fastapi import Depends
    from clearpath.api.app import create_app

    app = create_app(settings)

    def query(limit: int = 1):
        return limit

    @app.get("/query-probe")
    def probe(limit: int = Depends(query)):
        return {"limit": limit}

    with TestClient(app) as client:
        response = client.get("/query-probe", params={"limit": "SENTINEL secret"})
    assert_envelope(response, 422, "validation_error")
    assert "SENTINEL" not in response.text
    assert response.json()["error"]["details"]["fields"] == [
        {"loc": ["query", "limit"], "type": "int_parsing"},
    ]


def test_health_ready_reports_no_dataset(client, settings):
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ready", "database": True, "schema": True,
        "dataset_available": False, "mode": "synthetic",
    }
    assert settings.database_url not in response.text
    assert settings.api_key.get_secret_value() not in response.text
    assert "clearpath" not in response.text


@pytest.mark.parametrize("revision_sql", [
    pytest.param("UPDATE alembic_version SET version_num = 'not_head'", id="stale"),
    pytest.param("DELETE FROM alembic_version", id="empty"),
    pytest.param("DROP TABLE alembic_version", id="missing"),
])
def test_health_ready_requires_applied_head(client, settings, monkeypatch, revision_sql, test_database_name):
    from contextlib import nullcontext
    from types import SimpleNamespace
    from sqlalchemy import text
    import clearpath.api.app as app_module
    from clearpath.db.session import get_engine

    # Reuse a real connection so every revision change is rolled back on close.
    engine = get_engine(settings.database_url)
    assert engine.url.database == test_database_name
    with engine.connect() as connection:
        connection.execute(text(revision_sql))
        monkeypatch.setattr(app_module, "get_engine", lambda _url: SimpleNamespace(
            connect=lambda: nullcontext(connection),
        ))
        response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable", "database": True, "schema": False,
        "dataset_available": False, "mode": "synthetic",
    }


def test_unknown_route_envelope(client):
    assert_envelope(client.get("/missing"), 404, "not_found")


def test_cors_enabled_only_when_configured(settings):
    from clearpath.api.app import create_app
    settings.cors_origins = ["http://localhost:5173"]
    with TestClient(create_app(settings)) as cors_client:
        response = cors_client.get("/health/live", headers={"Origin": "http://localhost:5173"})
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_headers_on_unhandled_error(settings):
    from clearpath.api.app import create_app
    settings.cors_origins = ["http://localhost:5173"]
    app = create_app(settings)

    @app.get("/crash")
    async def crash():
        raise RuntimeError("secretvalue")

    with TestClient(app, raise_server_exceptions=False) as cors_client:
        response = cors_client.get("/crash", headers={"Origin": "http://localhost:5173"})
    assert_envelope(response, 500, "internal_error")
    assert "secretvalue" not in response.text
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "X-Request-ID" in response.headers["access-control-expose-headers"]


def test_cors_preflight_error_envelope(settings):
    from clearpath.api.app import create_app
    settings.cors_origins = ["http://localhost:5173"]
    with TestClient(create_app(settings)) as cors_client:
        response = cors_client.options("/api/v1/_ping", headers={
            "Origin": "http://disallowed.example", "Access-Control-Request-Method": "GET",
        })
    assert_envelope(response, 400, "bad_request")


def test_session_direct_and_dependency(settings):
    from fastapi import Depends
    from sqlalchemy import text
    from sqlalchemy.orm import Session
    from clearpath.api.app import create_app
    from clearpath.core.config import get_settings
    from clearpath.db.session import get_session

    get_settings.cache_clear()
    # A direct caller may also provide Settings explicitly.
    dependency = get_session(settings)
    session = next(dependency)
    assert session.execute(text("SELECT 1")).scalar_one() == 1
    dependency.close()
    app = create_app(settings)

    @app.get("/db-probe")
    def probe(session: Session = Depends(get_session)):
        return {"value": session.execute(text("SELECT 1")).scalar_one()}

    with TestClient(app) as db_client:
        assert db_client.get("/db-probe").json() == {"value": 1}


def test_settings_environment(monkeypatch):
    from clearpath.core.config import Settings
    monkeypatch.setenv("CLEARPATH_API_KEY", "test-key")
    monkeypatch.setenv("CLEARPATH_MODE", "public")
    monkeypatch.setenv("CLEARPATH_CORS_ORIGINS", " http://localhost:5173, http://localhost:3000 ,")
    settings = Settings(_env_file=None)
    assert settings.cors_origins == ["http://localhost:5173", "http://localhost:3000"]
    assert settings.mode == "public"
    monkeypatch.setenv("CLEARPATH_CORS_ORIGINS", "")
    assert Settings(_env_file=None).cors_origins == []
    monkeypatch.delenv("CLEARPATH_API_KEY")
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_settings_validation_error_hides_database_password(monkeypatch):
    import pytest
    from pydantic import ValidationError
    from clearpath.core.config import Settings

    monkeypatch.delenv("CLEARPATH_API_KEY", raising=False)
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:hunter2-secret@db/test")
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)
    assert "hunter2-secret" not in str(exc_info.value)


@pytest.mark.parametrize("database", ["clearpath", "postgres", "not_a_test_db"])
def test_database_fixture_refuses_non_test_databases(database, monkeypatch, request):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://clearpath:clearpath@127.0.0.1:5432/" + database)
    with pytest.raises(ValueError, match="database name starting with clearpath_test"):
        request.getfixturevalue("settings")


@pytest.mark.parametrize("database", ["clearpath_test", "clearpath_test_i2", "clearpath_testcustom"])
def test_database_fixture_accepts_test_prefix(database, monkeypatch, request):
    from sqlalchemy.engine import make_url

    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://clearpath:clearpath@127.0.0.1:5432/" + database)
    settings = request.getfixturevalue("settings")
    assert make_url(settings.database_url).database == database


def test_settings_repr_hides_database_url():
    from clearpath.core.config import Settings

    url = "postgresql+psycopg://user:SENTINEL-password@127.0.0.1/test"
    settings = Settings(_env_file=None, database_url=url, api_key="test-key")
    assert url not in repr(settings)
    assert "SENTINEL-password" not in repr(settings)
    assert "database_url" not in repr(settings)


@pytest.mark.parametrize("url", [
    "sqlite:///SENTINEL-database", "postgresql://user:SENTINEL-password@db/test",
    "postgresql+asyncpg://user:SENTINEL-password@db/test",
])
def test_settings_requires_psycopg_postgres_url(url):
    from pydantic import ValidationError
    from clearpath.core.config import Settings

    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None, database_url=url, api_key="test-key")
    assert "database_url must start with postgresql+psycopg://" in str(error.value)
    assert url not in str(error.value)
    assert "SENTINEL" not in str(error.value)


def test_engine_hides_parameters_and_limits_connection_timeout(settings):
    from uuid import uuid4
    from sqlalchemy import event, text
    from sqlalchemy.engine import make_url
    from clearpath.db.session import get_engine

    url = make_url(settings.database_url).update_query_dict({"application_name": uuid4().hex})
    engine = get_engine(url.render_as_string(hide_password=False))
    parameters = []
    event.listen(engine, "do_connect", lambda _dialect, _record, _args, kwargs: parameters.append(dict(kwargs)))
    try:
        assert engine.hide_parameters is True
        with engine.connect() as connection:
            assert connection.execute(text("SELECT 1")).scalar_one() == 1
        assert parameters[0]["connect_timeout"] == 2
    finally:
        engine.dispose()


def test_health_ready_unreachable_database_is_fast(monkeypatch):
    from time import monotonic
    from clearpath.api.app import create_app
    from clearpath.core.config import Settings

    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://clearpath:clearpath@127.0.0.1:1/clearpath")
    settings = Settings(_env_file=None, api_key="test-key", mode="synthetic")
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        started = monotonic()
        response = client.get("/health/ready")
        elapsed = monotonic() - started
    assert elapsed < 5
    assert response.status_code == 503
    assert response.json() == {
        "status": "unavailable", "database": False, "schema": False,
        "dataset_available": False, "mode": "synthetic",
    }
    assert response.headers["X-Request-ID"]
    assert settings.database_url not in response.text


def test_unhandled_error_envelope(settings):
    from clearpath.api.app import create_app
    app = create_app(settings)

    @app.get("/crash")
    def crash():
        raise RuntimeError("secretvalue")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/crash")
    assert_envelope(response, 500, "internal_error")
    assert "secretvalue" not in response.text
