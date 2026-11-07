import secrets
from typing import Annotated

from fastapi import Depends, Header

from clearpath.core.config import Settings, get_settings
from clearpath.domain.errors import DomainError


def require_api_key(
    settings: Annotated[Settings, Depends(get_settings)],
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> None:
    if x_api_key is None or not secrets.compare_digest(
        x_api_key.encode("utf-8"), settings.api_key.get_secret_value().encode("utf-8")
    ):
        raise DomainError(
            "missing_api_key", "The X-API-Key header is missing or wrong.", http_status=401,
        )
