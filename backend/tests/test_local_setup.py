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
