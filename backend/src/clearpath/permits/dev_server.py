"""DEV ONLY: a small stand-in API server for the lookup routes.

Use this until Person 3's FastAPI app (origin/p3-platform) is merged. It serves only
the lookup router, /health/live, an X-API-Key check and an optional CORS allowlist.
It listens on 127.0.0.1 only. It is not a production server.

Run from the repo root::

    export CLEARPATH_API_KEY='<any throwaway dev key>'
    export CLEARPATH_CORS_ORIGINS='http://localhost:5173'   # optional, comma-separated
    PYTHONPATH=backend/src .venv/bin/python -m clearpath.permits.dev_server [--port 8000] [--real]

Data:
* default: the SYNTHETIC manifest at backend/tests/fixtures/lookup_synthetic/manifest.json
  (demo mode; every response carries ``synthetic_dataset``).
* ``--real``: Person 2's reviewed Irvine ADU manifest at
  backend/data/irvine_adu/manifest.json, read-only, as ``reviewed_public`` through the
  normal loader. There is no override: if the file fails any public check (kind,
  profile_key, fact_schema, every passage reviewed), the server refuses to start.

The server refuses to start without CLEARPATH_API_KEY and never prints the key.
Results are still a prototype, not legal advice; every lookup carries the notice.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import uuid
from hashlib import sha256
from pathlib import Path
from typing import Mapping, Sequence

from fastapi import Depends, FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from clearpath.locations.service import load_registry
from clearpath.permits.release import InMemoryReleaseProvider, ReleaseData, ReleaseLoadError
from clearpath.permits.routes import ApiError, build_lookup_router, error_response, request_id_for

BACKEND_DIR = Path(__file__).resolve().parents[3]
SYNTHETIC_MANIFEST = BACKEND_DIR / "tests" / "fixtures" / "lookup_synthetic" / "manifest.json"
REAL_MANIFEST = BACKEND_DIR / "data" / "irvine_adu" / "manifest.json"
HOST = "127.0.0.1"
_RELEASE_NAMESPACE = uuid.UUID("0b9c6a52-3c1d-4e5f-8a7b-9c0d1e2f3a4b")


class DevServerConfigError(RuntimeError):
    """The dev server cannot start with this configuration."""


# --------------------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------------------


def _release_from_file(path: Path, dataset_mode: str) -> ReleaseData:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    content_hash = sha256(canonical.encode("utf-8")).hexdigest()
    release_id = str(uuid.uuid5(_RELEASE_NAMESPACE, content_hash))
    return ReleaseData.from_manifest(data, release_id, content_hash, dataset_mode)


def load_synthetic_provider(path: Path = SYNTHETIC_MANIFEST) -> InMemoryReleaseProvider:
    """The default dev data: SYNTHETIC, demo mode."""
    return InMemoryReleaseProvider([_release_from_file(path, "synthetic")], demo_mode=True)


def load_real_provider(path: Path | None = None) -> InMemoryReleaseProvider:
    """Person 2's reviewed Irvine data as reviewed_public, read-only. No override.

    Raises DevServerConfigError if the file is missing, unreadable, or fails any
    reviewed_public check.
    """
    path = Path(path or REAL_MANIFEST)
    try:
        release = _release_from_file(path, "reviewed_public")
    except OSError:
        raise DevServerConfigError("the Irvine manifest file could not be read") from None
    except ValueError as error:  # ReleaseLoadError, or invalid JSON
        reason = str(error) if isinstance(error, ReleaseLoadError) else "the file is not valid JSON"
        raise DevServerConfigError(f"the Irvine manifest is not loadable as reviewed_public: {reason}") from None
    return InMemoryReleaseProvider([release], demo_mode=False)


# --------------------------------------------------------------------------------------
# App
# --------------------------------------------------------------------------------------


def create_dev_app(provider, registry, *, api_key: str, cors_origins: Sequence[str]) -> FastAPI:
    if not api_key or not api_key.strip():
        raise DevServerConfigError("CLEARPATH_API_KEY is not set")
    expected = api_key.encode("utf-8")

    app = FastAPI(title="ClearPath lookup DEV server (dev only)")

    def require_dev_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
        if x_api_key is None or not secrets.compare_digest(x_api_key.encode("utf-8"), expected):
            raise ApiError("unauthorized", "A valid API key is required.", http_status=401)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        return error_response(request, exc.status_code, code, "Request failed.")

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        fields = [{"loc": list(e["loc"]), "type": e["type"]} for e in exc.errors()]
        return error_response(request, 422, "validation_error", "Request validation failed.", {"fields": fields})

    @app.exception_handler(Exception)
    async def internal_error(request: Request, exc: Exception):
        return error_response(request, 500, "internal_error", "An internal error occurred.")

    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(cors_origins),
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["X-API-Key", "Content-Type"],
            expose_headers=["X-Request-ID"],
        )

    @app.middleware("http")
    async def request_id(request: Request, call_next):
        request.state.request_id = str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id_for(request)
        return response

    @app.get("/health/live")
    def live() -> dict:
        return {"status": "ok"}

    app.include_router(build_lookup_router(provider, registry), prefix="/api/v1",
                       dependencies=[Depends(require_dev_key)])
    return app


def _parse_origins(value: str | None) -> list[str]:
    return [o.strip() for o in (value or "").split(",") if o.strip()]


def build_from_env(
    argv: Sequence[str], environ: Mapping[str, str], *, real_manifest: Path | None = None
) -> tuple[FastAPI, str]:
    """Build the app and a startup banner from CLI args and environment. Never includes the key."""
    parser = argparse.ArgumentParser(prog="python -m clearpath.permits.dev_server",
                                     description="ClearPath lookup DEV server (dev only).")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--real", action="store_true",
                        help="serve Person 2's reviewed Irvine ADU data (refuses to start if it fails public checks)")
    args = parser.parse_args(list(argv))

    api_key = environ.get("CLEARPATH_API_KEY", "")
    if not api_key.strip():
        raise DevServerConfigError("CLEARPATH_API_KEY is not set. Set a throwaway dev key and try again.")
    origins = _parse_origins(environ.get("CLEARPATH_CORS_ORIGINS"))

    if args.real:
        provider = load_real_provider(real_manifest)
        data_lines = [
            "DATA: REVIEWED PUBLIC Irvine ADU data (Person 2), read-only. Passed every public check.",
            "      Still a prototype, not legal advice: confirm with the City of Irvine or a professional.",
        ]
    else:
        provider = load_synthetic_provider()
        data_lines = ["DATA: SYNTHETIC test data (not real Irvine rules, forms, fees or deadlines)."]

    app = create_dev_app(provider, load_registry(), api_key=api_key, cors_origins=origins)
    app.state.dev_port = args.port
    banner = "\n".join([
        "ClearPath lookup DEV SERVER - dev only, a stand-in until Person 3's app is merged.",
        *data_lines,
        "API key: set (hidden)",
        f"CORS origins: {', '.join(origins) if origins else 'none'}",
        f"Listening on http://{HOST}:{args.port}  (health: /health/live, API: /api/v1/...)",
    ])
    return app, banner


def main(argv: Sequence[str] | None = None) -> int:
    try:
        app, banner = build_from_env(sys.argv[1:] if argv is None else argv, os.environ)
    except DevServerConfigError as error:
        print(f"error: refusing to start: {error}", file=sys.stderr)
        return 2
    print(banner, flush=True)
    import uvicorn

    uvicorn.run(app, host=HOST, port=app.state.dev_port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
