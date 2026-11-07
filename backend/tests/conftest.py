"""Shared source bootstrap and owned disposable PostgreSQL test resources."""

import os
import secrets
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from sqlalchemy import create_engine

BACKEND = Path(__file__).resolve().parents[1]
_SRC = BACKEND / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
DB_IMAGE = (
    "pgvector/pgvector:0.8.7-pg17-trixie@"
    "sha256:01215e09bd4bd582d20230e025b6c971deeeffee49ceef1aae167e839cb62a7e"
)


@pytest.fixture(scope="session")
def postgres(tmp_path_factory):
    name = "clearpath-foundation-test-" + uuid4().hex[:12]
    password = secrets.token_hex(24)
    env_file = tmp_path_factory.mktemp("postgres") / "db.env"
    env_file.write_text(f"POSTGRES_PASSWORD={password}\n")
    env_file.chmod(0o600)
    result = subprocess.run(
        [
            "docker",
            "run",
            "--detach",
            "--rm",
            "--name",
            name,
            "--env-file",
            str(env_file),
            "--publish",
            "127.0.0.1::5432",
            "--tmpfs",
            "/var/lib/postgresql/data",
            DB_IMAGE,
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, "Cannot start disposable PostgreSQL (Docker required)"
    try:
        port_result = subprocess.run(
            ["docker", "port", name, "5432/tcp"], capture_output=True, text=True, check=True
        )
        port = int(port_result.stdout.strip().rsplit(":", 1)[1])
        dsn = f"postgresql://postgres:{password}@127.0.0.1:{port}/postgres"
        for _ in range(100):
            try:
                with psycopg.connect(dsn, connect_timeout=1):
                    break
            except psycopg.OperationalError:
                time.sleep(0.1)
        else:
            pytest.fail("Disposable PostgreSQL did not become ready")
        yield dsn
    finally:
        subprocess.run(["docker", "rm", "--force", name], capture_output=True, check=False)
        env_file.unlink(missing_ok=True)


@pytest.fixture
def database(postgres):
    name = "test_" + uuid4().hex
    with psycopg.connect(postgres, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
    url = postgres.rsplit("/", 1)[0].replace("postgresql://", "postgresql+psycopg://") + "/" + name
    engine = create_engine(url)
    try:
        yield engine
    finally:
        engine.dispose()
        with psycopg.connect(postgres, autocommit=True) as connection:
            connection.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name))
            )


def migrate(engine, revision="head"):
    environment = os.environ | {
        "DATABASE_URL": engine.url.render_as_string(hide_password=False),
        "CLEARPATH_DATABASE_URL": engine.url.render_as_string(hide_password=False),
        "CLEARPATH_API_KEY": "test-only-" + "a" * 40,
    }
    result = subprocess.run(
        [
            str(BACKEND / ".venv/bin/alembic"),
            "-c",
            str(BACKEND / "alembic.ini"),
            "upgrade",
            revision,
        ],
        env=environment,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, "Migration command failed (details suppressed to protect DSN)"


@pytest.fixture
def migrated(database):
    migrate(database)
    return database
