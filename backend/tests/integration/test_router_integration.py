"""Teammates' routers mounted on the platform app: shared auth, sessions and error envelope."""
from uuid import uuid4

KEY = {"X-API-Key": "test-key"}


def test_projects_routes_require_the_platform_api_key(client):
    for headers in ({}, {"X-API-Key": "wrong"}):
        response = client.get("/api/v1/projects", headers=headers)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "unauthorized"
        assert response.headers["X-Request-ID"] == response.json()["request_id"]


def test_projects_domain_conflicts_use_the_platform_error_envelope(client):
    project_id = str(uuid4())
    response = client.get(f"/api/v1/projects/{project_id}", headers=KEY)
    assert response.status_code == 404
    body = response.json()
    assert body["error"] == {
        "code": "project_not_found", "message": "No project with that id.", "details": {"project_id": project_id},
    }
    assert body["request_id"] == response.headers["X-Request-ID"]


def test_projects_echo_the_configured_dataset_mode(client, settings):
    response = client.get("/api/v1/projects", headers=KEY)
    assert response.status_code == 200
    assert response.json()["dataset_mode"] == settings.mode


def test_projects_validation_errors_use_safe_platform_fields(client):
    response = client.post("/api/v1/projects", json={"SENTINEL secret": "value"}, headers=KEY)
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert "SENTINEL" not in response.text
