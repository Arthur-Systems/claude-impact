"""The public boundary must stay alive, authenticate and never echo rejected values."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from clearpath.api.app import create_app
from clearpath.core.config import Settings

KEY = "test-key-" + "a" * 40
URL = "postgresql+psycopg://unused:never-print-this@127.0.0.1:1/absent"


def settings(**overrides):
    return Settings(database_url=URL, api_key=KEY, **overrides)


@pytest.mark.parametrize("mode", ["public", "synthetic"])
def test_liveness_without_database_or_migrations(mode):
    with TestClient(create_app(settings(data_mode=mode))) as client:
        response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive", "data_mode": mode}


def test_unavailable_database_readiness_is_sanitized():
    with TestClient(create_app(settings())) as client:
        response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "not_ready"
    assert "never-print-this" not in response.text
    assert "postgresql" not in response.text


@pytest.mark.parametrize("headers", [{}, {"X-API-Key": "secret-incorrect-value"}])
def test_application_router_requires_shared_key(headers):
    with TestClient(create_app(settings())) as client:
        response = client.get("/api/v1/status", headers=headers)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
    assert "secret-incorrect-value" not in response.text


def test_status_uses_application_settings_and_valid_key():
    with TestClient(create_app(settings(data_mode="synthetic"))) as client:
        response = client.get("/api/v1/status?expected_mode=synthetic", headers={"X-API-Key": KEY})
    assert response.status_code == 200
    assert response.json() == {"backend": "clearpath", "data_mode": "synthetic"}


@pytest.mark.parametrize("query", ["unexpected=secret-value", "expected_mode=secret-value"])
def test_strict_query_contract_rejects_unknown_or_invalid_values_without_echo(query):
    with TestClient(create_app(settings())) as client:
        response = client.get("/api/v1/status?" + query, headers={"X-API-Key": KEY})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert "secret-value" not in response.text
    assert KEY not in response.text


def test_framework_not_found_uses_error_envelope():
    with TestClient(create_app(settings())) as client:
        response = client.get("/not-a-route")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_default_mode_public_and_missing_secrets_have_no_fallback(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("CLEARPATH_DATABASE_URL", raising=False)
    monkeypatch.delenv("CLEARPATH_API_KEY", raising=False)
    monkeypatch.delenv("CLEARPATH_DATA_MODE", raising=False)
    assert settings().data_mode == "public"
    with pytest.raises(ValidationError):
        Settings()
    assert "never-print-this" not in repr(settings())
    assert KEY not in repr(settings())


@pytest.mark.parametrize(
    "override", [{"data_mode": "demo"}, {"api_key": "short"}, {"database_url": "sqlite:///test.db"}]
)
def test_unsafe_or_unsupported_configuration_is_rejected(override):
    values = {"database_url": URL, "api_key": KEY} | override
    with pytest.raises(ValidationError):
        Settings(**values)


def test_status_mode_mismatch_uses_domain_error_envelope():
    with TestClient(create_app(settings())) as client:
        response = client.get("/api/v1/status?expected_mode=synthetic", headers={"X-API-Key": KEY})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "data_mode_mismatch"


def test_openapi_is_protected_and_contains_no_configuration_secrets():
    with TestClient(create_app(settings())) as client:
        assert client.get("/api/v1/openapi.json").status_code == 401
        response = client.get("/api/v1/openapi.json", headers={"X-API-Key": KEY})
        assert response.status_code == 200
        assert "/api/v1/status" in response.json()["paths"]
        assert KEY not in response.text
        assert "never-print-this" not in response.text


def test_unexpected_exception_never_exposes_its_raw_message():
    app = create_app(settings())

    @app.get("/__test_failure")
    def fail():
        raise RuntimeError("private-database-password")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/__test_failure")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "private-database-password" not in response.text


@pytest.mark.parametrize(
    "path,status_code,code",
    [
        ("/api/v1/status", 401, "unauthorized"),
        ("/api/v1/status?expected_mode=private-raw-value", 422, "validation_error"),
        ("/api/v1/status?expected_mode=synthetic", 409, "data_mode_mismatch"),
        ("/missing-route", 404, "not_found"),
        ("/health/ready", 503, "not_ready"),
        ("/__unexpected", 500, "internal_error"),
    ],
)
def test_error_envelope_has_safe_details_and_generated_correlation(path, status_code, code):
    from uuid import UUID

    app = create_app(settings())

    @app.get("/__unexpected")
    def unexpected():
        raise RuntimeError("private-exception-secret")

    headers = {"X-Request-ID": "private-client-request-id"}
    if status_code != 401:
        headers["X-API-Key"] = KEY
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(path, headers=headers)
        second = client.get(path, headers=headers)
    assert response.status_code == status_code
    payload = response.json()
    assert set(payload) == {"error", "request_id"}
    assert set(payload["error"]) == {"code", "message", "details"}
    assert payload["error"]["code"] == code
    assert payload["error"]["details"] == []
    assert UUID(payload["request_id"]).version == 4
    assert response.headers["X-Request-ID"] == payload["request_id"]
    assert second.json()["request_id"] != payload["request_id"]
    for secret in (
        "private-raw-value",
        "private-exception-secret",
        "private-client-request-id",
        KEY,
    ):
        assert secret not in response.text


def test_domain_error_can_provide_only_safe_structured_details():
    from clearpath.domain.errors import DomainError

    app = create_app(settings())

    @app.get("/__safe_domain_error")
    def invalid_domain():
        raise DomainError(
            "unsupported_configuration",
            "Configuration is unsupported.",
            409,
            details=[{"code": "unsupported_mode", "field": "data_mode"}],
        )

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/__safe_domain_error")
    assert response.status_code == 409
    assert response.json()["error"]["details"] == [
        {"code": "unsupported_mode", "field": "data_mode"}
    ]


def test_database_url_environment_precedence_and_explicit_override(monkeypatch):
    canonical = "postgresql+psycopg://canonical:dummy@127.0.0.1:5432/canonical"
    legacy = "postgresql+psycopg://legacy:dummy@127.0.0.1:5432/legacy"
    monkeypatch.setenv("DATABASE_URL", canonical)
    monkeypatch.setenv("CLEARPATH_DATABASE_URL", legacy)
    assert Settings(api_key=KEY).database_url.get_secret_value() == canonical
    assert Settings(database_url=URL, api_key=KEY).database_url.get_secret_value() == URL
    monkeypatch.delenv("DATABASE_URL")
    assert Settings(api_key=KEY).database_url.get_secret_value() == legacy
