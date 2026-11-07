"""Person 5's standalone app: for tests and a fallback until Person 3's app shell lands.

NOT the product app. Person 3's ``create_app`` should instead:
    app.include_router(clearpath.projects.routes.router)
    app.dependency_overrides[routes.get_session] = <platform get_session>
    app.dependency_overrides[routes.require_api_key] = <platform require_api_key>
and map ``clearpath.timelines.model.DomainConflict`` (code, message, details,
http_status) to the shared error envelope. ``domain_conflict_handler`` below
shows the expected mapping.

Run locally:  DATABASE_URL=postgresql+psycopg://... uvicorn --factory clearpath.projects.standalone:app_from_env
"""

from __future__ import annotations

import os
import uuid
from typing import Iterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from clearpath.timelines.model import DomainConflict

from . import routes


def _request_id() -> str:
    return str(uuid.uuid4())  # same format as Person 3's request ids


async def domain_conflict_handler(request: Request, exc: DomainConflict) -> JSONResponse:
    return JSONResponse(
        status_code=exc.http_status,
        content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}, "request_id": _request_id()},
    )


async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [{"loc": list(e.get("loc", [])), "type": e.get("type"), "msg": e.get("msg")} for e in exc.errors()]
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "validation_error", "message": "The request is not valid.", "details": {"errors": errors}},
                 "request_id": _request_id()},
    )


def create_standalone_app(database_url: str) -> FastAPI:
    engine = create_engine(database_url, pool_pre_ping=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def session_dep() -> Iterator[Session]:
        with factory() as session:
            yield session  # uncommitted work is rolled back on close

    app = FastAPI(title="ClearPath projects (P5 standalone)")
    app.include_router(routes.router)
    app.dependency_overrides[routes.get_session] = session_dep
    app.add_exception_handler(DomainConflict, domain_conflict_handler)
    app.add_exception_handler(RequestValidationError, validation_handler)
    app.state.engine = engine

    @app.get("/health/live")
    def live() -> dict:
        return {"status": "ok"}

    return app


def app_from_env() -> FastAPI:
    return create_standalone_app(os.environ["DATABASE_URL"])
