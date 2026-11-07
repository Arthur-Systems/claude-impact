"""Shared dependencies for future application routers."""

from collections.abc import Iterator
from secrets import compare_digest
from typing import Annotated

from fastapi import Depends, Request, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.orm import Session

from clearpath.core.config import Settings
from clearpath.domain.errors import DomainError

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_session(request: Request) -> Iterator[Session]:
    """App-scoped session; the service explicitly commits or rolls back its transaction."""
    with request.app.state.session_factory() as session:
        yield session


def require_api_key(
    settings: Annotated[Settings, Depends(get_settings)],
    supplied: Annotated[str | None, Security(api_key_header)],
) -> None:
    # Bytes also allow malformed non-ASCII supplied header values to fail closed.
    expected = settings.api_key.get_secret_value().encode("utf-8")
    if supplied is None or not compare_digest(supplied.encode("utf-8"), expected):
        raise DomainError("unauthorized", "A valid API key is required.", 401)


SessionDependency = Annotated[Session, Depends(get_session)]
SettingsDependency = Annotated[Settings, Depends(get_settings)]
