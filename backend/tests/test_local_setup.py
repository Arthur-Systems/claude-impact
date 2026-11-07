"""Local bootstrap must keep isolated secrets off the terminal and out of git."""

import os
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/local_env.py"


def test_credentials_bootstrap_is_private_repeatable_and_isolated(tmp_path):
    paths = [tmp_path / "public.env", tmp_path / "demo.env"]
    contents = []
    for path, mode in zip(paths, ["public", "synthetic"], strict=True):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(path), "--mode", mode], text=True, capture_output=True
        )
        assert result.returncode == 0, "Bootstrap must succeed with no existing env file"
        assert result.stdout == ""
        assert result.stderr == ""
        first = path.read_text()
        assert os.stat(path).st_mode & 0o777 == 0o600
        assert f"CLEARPATH_DATA_MODE={mode}\n" in first
        again = subprocess.run(
            [sys.executable, str(SCRIPT), str(path), "--mode", mode], text=True, capture_output=True
        )
        assert again.returncode == 0
        assert again.stdout == ""
        assert again.stderr == ""
        assert path.read_text() == first
        values = dict(line.split("=", 1) for line in first.splitlines())
        assert len(values["CLEARPATH_API_KEY"]) >= 32
        assert len(values["POSTGRES_PASSWORD"]) >= 32
        contents.append(values)
    assert contents[0]["CLEARPATH_API_KEY"] != contents[1]["CLEARPATH_API_KEY"]
    assert contents[0]["POSTGRES_PASSWORD"] != contents[1]["POSTGRES_PASSWORD"]


def test_make_compose_uses_selected_environment_despite_conflicting_ambient_values(tmp_path):
    import json

    root = SCRIPT.parents[2]
    runtime = tmp_path / ".runtime"
    runtime.mkdir()
    selected = {
        "DATABASE_URL": "postgresql+psycopg://selected:dummy@db:5432/selected",
        "CLEARPATH_DATABASE_URL": "postgresql+psycopg://legacy:dummy@other.invalid:5432/legacy",
        "CLEARPATH_API_KEY": "selected-dummy-key-" + "a" * 32,
        "POSTGRES_USER": "selected",
        "POSTGRES_PASSWORD": "selected-dummy-password",
        "POSTGRES_DB": "selected",
        "CLEARPATH_DATA_MODE": "synthetic",
        "BACKEND_API_PORT": "8001",
        "BACKEND_DB_PORT": "55433",
    }
    (runtime / "demo.env").write_text(
        "\n".join(f"{key}={value}" for key, value in selected.items())
    )
    probe = tmp_path / "probe.mk"
    probe.write_text("foundation-config:\n\t@$(COMPOSE) config --format json\n")
    ambient = os.environ | {key: "ambient-dummy-value" for key in selected}
    ambient.update(
        {
            "DATABASE_URL": "postgresql+psycopg://ambient:dummy@public.invalid:5432/public",
            "CLEARPATH_DATABASE_URL": "postgresql+psycopg://ambient:dummy@public.invalid:5432/public",
            "BACKEND_API_PORT": "18000",
            "BACKEND_DB_PORT": "15432",
            "COMPOSE_FILE": str(root / "compose.yaml"),
        }
    )
    result = subprocess.run(
        [
            "make",
            "--no-print-directory",
            "-f",
            str(root / "Makefile"),
            "-f",
            str(probe),
            "BACKEND_ENV=demo",
            "foundation-config",
        ],
        cwd=tmp_path,
        env=ambient,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, "Read-only effective Compose configuration must succeed"
    services = json.loads(result.stdout)["services"]
    api = services["api"]["environment"]
    assert api.get("DATABASE_URL", api.get("CLEARPATH_DATABASE_URL")) == selected["DATABASE_URL"]
    assert api["CLEARPATH_API_KEY"] == selected["CLEARPATH_API_KEY"]
    assert api["CLEARPATH_DATA_MODE"] == "synthetic"
    for key in ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"):
        assert services["db"]["environment"][key] == selected[key]
    assert services["api"]["ports"][0]["published"] == "8001"
    assert services["db"]["ports"][0]["published"] == "55433"
