"""CLI failures use stable diagnostics and real PostgreSQL transactions."""
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from typer.testing import CliRunner

from clearpath.cli import app
from clearpath.db.models import DatasetRelease, Jurisdiction

BACKEND = Path(__file__).resolve().parents[2]


def assert_clean_failure(result, message):
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == message + "\n"
    assert "Traceback" not in result.output
    assert "SENTINEL" not in result.output


def test_malformed_release_uuid_is_clean_before_database_access(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://clearpath:clearpath@127.0.0.1:1/clearpath_test_i2")
    result = CliRunner().invoke(app, ["data", "publish", "--release", "SENTINEL secret", "--reviewed"])
    assert_clean_failure(result, "schema_invalid: release")


def test_nonexistent_release_id_is_clean(settings, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", settings.database_url)
    monkeypatch.setenv("CLEARPATH_MODE", "synthetic")
    result = CliRunner().invoke(app, ["data", "publish", "--release", str(uuid4()), "--reviewed"])
    assert_clean_failure(result, "release_not_found: release")


@pytest.mark.parametrize("dry_run", [False, True])
def test_missing_manifest_file_is_clean(dry_run):
    missing = BACKEND / "tests/fixtures" / ("SENTINEL-" + uuid4().hex + ".json")
    command = ["data", "import", "--manifest", str(missing)]
    result = CliRunner().invoke(app, command + (["--dry-run"] if dry_run else []))
    assert_clean_failure(result, "schema_invalid: $")


def test_manifest_outside_allowed_roots_is_clean(tmp_path):
    outside = tmp_path / "SENTINEL secret.json"
    outside.write_text("{}")
    result = CliRunner().invoke(app, ["data", "import", "--manifest", str(outside)])
    assert_clean_failure(result, "path_outside_bundle: $")
    assert str(tmp_path) not in result.output


def test_debug_preserves_underlying_exception():
    from clearpath.ingestion.validation import BundleValidationError

    result = CliRunner().invoke(app, ["--debug", "data", "publish", "--release", "invalid"])
    assert result.exit_code == 1
    assert isinstance(result.exception, BundleValidationError)


def test_test_backend_target_uses_selected_database():
    import subprocess

    result = subprocess.run(
        ["make", "-n", "test-backend", "TEST_DB=clearpath_test_i2"],
        cwd=BACKEND.parent, capture_output=True, text=True, check=True,
    )
    assert "datname='clearpath_test_i2'" in result.stdout
    assert "createdb -U clearpath clearpath_test_i2" in result.stdout
    assert result.stdout.count("/clearpath_test_i2 CLEARPATH_API_KEY=test-key") == 2
    # Person 5's schema-wiping suite gets its own database, never the shared one.
    assert "createdb -U clearpath clearpath_test_i2_p5\n" in result.stdout
    assert "CLEARPATH_P5_TEST_DATABASE_URL=postgresql+psycopg://clearpath:clearpath@127.0.0.1:5432/clearpath_test_i2_p5 uv run pytest" in result.stdout


def test_test_backend_target_refuses_dev_database_before_docker(tmp_path):
    import os
    import subprocess

    marker = tmp_path / "docker-was-called"
    command = tmp_path / "docker"
    command.write_text("#!/usr/bin/env bash\ntouch '" + str(marker) + "'\nexit 97\n")
    command.chmod(0o700)
    result = subprocess.run(
        ["make", "test-backend", "TEST_DB=clearpath"], cwd=BACKEND.parent,
        env={**os.environ, "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"], "PYTHONOPTIMIZE": "1"},
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode != 0
    assert "TEST_DB must start with clearpath_test" in result.stderr
    assert not marker.exists()


def test_smoke_uses_selected_port_and_stops_api_on_readiness_failure(tmp_path):
    import os
    import signal
    import socket
    import subprocess

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name in ("make", "docker"):
        command = bin_dir / name
        command.write_text("#!/usr/bin/env bash\nprintf '%s\\n' 'failure-only test: DB setup not invoked'\n")
        command.chmod(0o700)
    env = {
        **os.environ, "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
        "DATABASE_URL": "postgresql+psycopg://clearpath:clearpath@127.0.0.1:1/clearpath",
        "SMOKE_PORT": str(port), "COMPOSE_PROJECT_NAME": "claude-impact",
    }
    process = subprocess.Popen(
        ["bash", str(BACKEND / "scripts/smoke.sh")], cwd=BACKEND.parent,
        env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=30)
    finally:
        # The isolated group contains only this test's script and owned API.
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
    assert process.returncode != 0
    assert f"smoke: starting API on 127.0.0.1:{port}" in stdout
    assert "smoke: /health/live 200" in stdout
    assert "synthetic dataset is not ready" in stderr
    assert "smoke: API stopped" in stdout
    with socket.socket() as check:
        assert check.connect_ex(("127.0.0.1", port)) != 0


@pytest.mark.parametrize("flush_in_service", [False, True])
@pytest.mark.parametrize("status,expected", [
    ("active", "publish_conflict: release"), ("invalid", "database_error: $"),
])
def test_publish_database_failures_are_sanitized(db_session, monkeypatch, flush_in_service, status, expected):
    import clearpath.cli as cli

    jurisdiction = Jurisdiction(slug="synthetic-" + uuid4().hex, name="SYNTHETIC", state="CA")
    db_session.add(jurisdiction)
    db_session.flush()
    active = DatasetRelease(
        jurisdiction_id=jurisdiction.id, project_type="adu", profile_key="synthetic-cli-conflict",
        kind="synthetic", status="active", schema_version=1, content_hash=uuid4().hex,
        fact_schema={}, conflicts=[], curator_label="SYNTHETIC",
    )
    db_session.add(active)
    db_session.flush()
    connection = db_session.connection()
    monkeypatch.setattr(cli, "SessionLocal", lambda _settings: Session(
        bind=connection, join_transaction_mode="create_savepoint",
    ))

    def conflicting_publish(session, _release_id, **_kwargs):
        # Real PostgreSQL constraint failures at both flush and commit boundaries.
        session.add(DatasetRelease(
            jurisdiction_id=jurisdiction.id, project_type="adu", profile_key=active.profile_key,
            kind="synthetic", status=status, schema_version=1, content_hash=uuid4().hex,
            fact_schema={}, conflicts=[], curator_label="SYNTHETIC duplicate",
        ))
        if flush_in_service:
            session.flush()

    monkeypatch.setattr(cli, "publish_release", conflicting_publish)
    result = CliRunner().invoke(app, ["data", "publish", "--release", str(uuid4()), "--reviewed"])
    assert_clean_failure(result, expected)
    assert db_session.scalars(select(DatasetRelease).where(
        DatasetRelease.jurisdiction_id == jurisdiction.id,
    )).all() == [active]
