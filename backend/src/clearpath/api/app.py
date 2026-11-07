"""App factory and small, shared HTTP boundary for the foundation."""

from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException

from clearpath.api.dependencies import (
    SessionDependency,
    SettingsDependency,
    require_api_key,
)
from clearpath.core.config import DataMode, Settings
from clearpath.db.session import create_session_factory, dispose_session_factory
from clearpath.domain.errors import DomainError

SCHEMA_REVISION = "0001_dataset_foundation"


class StatusQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_mode: DataMode | None = None


def error_response(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status_code)


def create_app(settings: Settings | None = None) -> FastAPI:
    configured = settings if settings is not None else Settings()
    factory = create_session_factory(configured)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        dispose_session_factory(factory)

    app = FastAPI(
        title="ClearPath prototype",
        description="Prototype only. Consult a qualified professional before making decisions.",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.settings = configured
    app.state.session_factory = factory

    @app.exception_handler(DomainError)
    async def domain_error(request: Request, error: DomainError):
        return error_response(error.code, error.message, error.status_code)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, error: RequestValidationError):
        # Pydantic's input, ctx, loc and custom messages can contain raw values/secrets.
        return error_response("validation_error", "Request validation failed.", 422)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException):
        codes = {404: "not_found", 405: "method_not_allowed"}
        return error_response(
            codes.get(error.status_code, "http_error"),
            "Request could not be completed.",
            error.status_code,
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, error: Exception):
        return error_response("internal_error", "An unexpected error occurred.", 500)

    @app.get("/health/live", tags=["health"])
    def live(config: SettingsDependency):
        return {"status": "alive", "data_mode": config.data_mode}

    @app.get("/health/ready", tags=["health"])
    def ready(session: SessionDependency, config: SettingsDependency):
        try:
            revision = session.scalar(text("SELECT version_num FROM alembic_version"))
            vector = session.scalar(
                text("SELECT extversion FROM pg_extension WHERE extname='vector'")
            )
            if revision != SCHEMA_REVISION or not vector:
                raise DomainError("not_ready", "Database schema is not ready.", 503)
            classification = "reviewed_public" if config.data_mode == "public" else "synthetic"
            available = session.scalar(
                text(
                    "SELECT EXISTS (SELECT 1 FROM dataset_releases "
                    "WHERE status='active' AND data_classification=:classification)"
                ),
                {"classification": classification},
            )
        except SQLAlchemyError:
            raise DomainError("not_ready", "Database schema is not ready.", 503) from None
        return {
            "status": "ready",
            "data_mode": config.data_mode,
            "dataset_available": bool(available),
        }

    # Teammate routers can be included under this router and inherit authentication.
    application = APIRouter(prefix="/api/v1", dependencies=[Depends(require_api_key)])

    @application.get("/status", tags=["platform"])
    def status(query: Annotated[StatusQuery, Query()], config: SettingsDependency):
        if query.expected_mode is not None and query.expected_mode != config.data_mode:
            raise DomainError("data_mode_mismatch", "The configured data mode does not match.", 409)
        return {"backend": "clearpath", "data_mode": config.data_mode}

    @application.get("/openapi.json", include_in_schema=False)
    def openapi():
        return app.openapi()

    app.include_router(application)
    return app
