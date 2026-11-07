#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/../.."
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-claude-impact}"
export DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://clearpath:clearpath@127.0.0.1:5432/clearpath}"
export CLEARPATH_MODE=synthetic
export SMOKE_PORT="${SMOKE_PORT:-8765}"
export CLEARPATH_API_KEY
CLEARPATH_API_KEY=$(uv run --project backend python -c 'import secrets; print(secrets.token_urlsafe(32))')
python=$(uv run --project backend python -c 'import sys; print(sys.executable)')
smoke_dir=$("$python" -c 'import tempfile; print(tempfile.mkdtemp(prefix="clearpath-smoke-"))')
server_pid=""

cleanup() {
    status=$?
    trap - EXIT
    if [[ -n "$server_pid" ]]; then
        kill "$server_pid" 2>/dev/null || true
        wait "$server_pid" 2>/dev/null || true
        printf '%s\n' 'smoke: API stopped'
    fi
    if [[ "$status" -ne 0 && -f "$smoke_dir/server.log" ]]; then
        "$python" -c 'import pathlib, sys; print(pathlib.Path(sys.argv[1]).read_text(), end="")' "$smoke_dir/server.log" >&2
    fi
    rm -r -- "$smoke_dir"
    exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# Refuse an occupied port before touching the database or starting a process.
"$python" - <<'PY'
import os
import socket
try:
    port = int(os.environ["SMOKE_PORT"])
    if not 1 <= port <= 65535:
        raise ValueError
except ValueError:
    raise SystemExit("smoke: SMOKE_PORT must be an integer from 1 to 65535") from None
try:
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind(("127.0.0.1", port))
except OSError:
    raise SystemExit(f"smoke: 127.0.0.1:{port} is already in use or unavailable") from None
PY

docker compose up -d --wait db
make --no-print-directory backend-migrate seed-demo

# Launch the uv-managed interpreter directly so the trap owns the API PID.
printf 'smoke: starting API on 127.0.0.1:%s\n' "$SMOKE_PORT"
"$python" -m uvicorn --factory clearpath.api.app:create_app --host 127.0.0.1 --port "$SMOKE_PORT" \
    --timeout-graceful-shutdown 2 >"$smoke_dir/server.log" 2>&1 &
server_pid=$!

"$python" - "$server_pid" <<'PY'
import json
import os
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import UUID

base = "http://127.0.0.1:" + os.environ["SMOKE_PORT"]


def request(path, headers=None):
    try:
        response = urlopen(Request(base + path, headers=headers or {}), timeout=3)
    except HTTPError as error:
        response = error
    with response:
        return response.status, json.load(response), response.headers


def request_id(headers):
    value = headers["X-Request-ID"]
    assert UUID(value).version == 4
    return value


deadline = time.monotonic() + 15
while True:
    os.kill(int(sys.argv[1]), 0)
    try:
        status, body, headers = request("/health/live")
        assert status == 200 and body == {"status": "ok"}
        request_id(headers)
        break
    except (URLError, TimeoutError, ConnectionError):
        if time.monotonic() >= deadline:
            raise SystemExit("smoke: API did not become live within 15 seconds") from None
        time.sleep(0.1)
print("smoke: /health/live 200")

status, body, headers = request("/health/ready")
assert status == 200 and body == {
    "status": "ready", "database": True, "schema": True,
    "dataset_available": True, "mode": "synthetic",
}, "synthetic dataset is not ready"
request_id(headers)
print("smoke: /health/ready 200 (dataset_available=true)")

status, body, headers = request("/api/v1/_ping")
assert status == 401 and body["error"] == {
    "code": "missing_api_key", "message": "The X-API-Key header is missing or wrong.", "details": {},
}
assert body["request_id"] == request_id(headers)
print("smoke: /api/v1/_ping without key 401 (missing_api_key)")

status, body, headers = request("/api/v1/_ping", {"X-API-Key": os.environ["CLEARPATH_API_KEY"]})
assert status == 200 and body == {"ok": True}
request_id(headers)
print("smoke: /api/v1/_ping with key 200")
print("smoke: passed")
PY
