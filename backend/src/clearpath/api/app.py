from functools import lru_cache
from http import HTTPStatus
from pathlib import Path
from uuid import uuid4

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi import APIRouter, Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.exceptions import ExceptionMiddleware

from clearpath.api.dependencies import require_api_key
from clearpath.core.config import Settings, get_settings
from clearpath.db.session import get_engine
from clearpath.domain.errors import DomainError
from clearpath.domain.schemas import StrictModel


@lru_cache
def get_alembic_head() -> str | None:
    config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
    return ScriptDirectory.from_config(config).get_current_head()


class EchoBody(StrictModel):
    name: str


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI()
    app.dependency_overrides[get_settings] = lambda: settings

    def error_response(request, status, code, message, details=None):
        return JSONResponse(
            status_code=status,
            content={"error": {"code": code, "message": message, "details": details or {}},
                     "request_id": request.state.request_id},
            headers={"X-Request-ID": request.state.request_id},
        )

    @app.exception_handler(DomainError)
    async def domain_error(request, exc):
        return error_response(request, exc.http_status, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        fields = [{"loc": list(err["loc"]), "type": err["type"]} for err in exc.errors()]
        return error_response(request, 422, "validation_error", "Request validation failed.", {"fields": fields})

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request, exc):
        try:
            phrase = HTTPStatus(exc.status_code).phrase
        except ValueError:
            phrase = "HTTP error"
        response = error_response(request, exc.status_code, phrase.lower().replace(" ", "_"), phrase)
        for key, value in (exc.headers or {}).items():
            if key.lower() != "x-request-id":
                response.headers[key] = value
        return response

    @app.exception_handler(Exception)
    async def internal_error(request, exc):
        return error_response(request, 500, "internal_error", "An internal error occurred.")

    # Convert unhandled route errors before CORS adds its response headers.
    app.add_middleware(ExceptionMiddleware, handlers={Exception: internal_error})
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["X-API-Key", "Content-Type"],
            expose_headers=["X-Request-ID"],
        )

    @app.middleware("http")
    async def request_id(request, call_next):
        request.state.request_id = str(uuid4())
        response = await call_next(request)
        # Starlette emits plain-text preflight failures outside exception handlers.
        if (settings.cors_origins and request.method == "OPTIONS"
                and "access-control-request-method" in request.headers
                and response.status_code >= 400):
            cors_headers = {key: value for key, value in response.headers.items()
                            if key.startswith("access-control-") or key == "vary"}
            response = error_response(request, response.status_code, "bad_request", "CORS preflight rejected.")
            response.headers.update(cors_headers)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @app.get("/health/live")
    def live():
        return {"status": "ok"}

    @app.get("/health/ready")
    def ready():
        database = schema = dataset_available = False
        try:
            with get_engine(settings.database_url).connect() as connection:
                database = connection.execute(text("SELECT 1")).scalar_one() == 1
                if connection.execute(text("SELECT to_regclass('public.alembic_version')")).scalar():
                    applied_revisions = connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
                    schema = applied_revisions == [get_alembic_head()]
                if connection.execute(text("SELECT to_regclass('public.dataset_releases')")).scalar():
                    kind = "synthetic" if settings.mode == "synthetic" else "reviewed_public"
                    dataset_available = bool(connection.execute(text(
                        "SELECT EXISTS (SELECT 1 FROM dataset_releases WHERE status = 'active' AND kind = :kind)"
                    ), {"kind": kind}).scalar())
        except SQLAlchemyError:
            database = schema = dataset_available = False
        available = database and schema
        return JSONResponse(status_code=200 if available else 503, content={
            "status": "ready" if available else "unavailable", "database": database,
            "schema": schema, "dataset_available": dataset_available, "mode": settings.mode,
        })

    router = APIRouter(prefix="/api/v1", dependencies=[Depends(require_api_key)])

    # remove once real routes exist
    @router.get("/_ping")
    def ping():
        return {"ok": True}

    # remove once real routes exist
    @router.post("/_echo")
    def echo(body: EchoBody):
        return body

    app.include_router(router)
    return app
