"""HTTP routes for location resolve and permit lookup (SPEC.md section 9).

Person 3 mounts these in ``api/app.py`` with one line::

    app.include_router(build_lookup_router(provider, registry), prefix="/api/v1",
                       dependencies=[Depends(require_api_key)])

The router has no prefix of its own and does not import Person 3's modules. Every
route uses ``EnvelopeRoute``, so errors come back in the shared envelope
``{"error": {"code", "message", "details"}, "request_id"}`` with an ``X-Request-ID``
header, whether the router runs inside Person 3's app or the dev server. Errors raised
by an API-key dependency are enveloped too: any exception with ``code``, ``message`` and
``http_status`` attributes (Person 3's ``DomainError``, or ``ApiError`` here).

Routes (under /api/v1):
    GET  /jurisdictions          city registry + curated coverage (registry is not coverage)
    POST /locations/resolve      one location mode -> resolution
    POST /permit-lookups         location + project type + facts -> cited checklist
    GET  /sources/{source_key}   public provenance for one source in the active releases
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable, Literal, Mapping, Sequence

from fastapi import APIRouter, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from clearpath.locations.schemas import CoverageEntry, Jurisdiction, LocationInputError
from clearpath.locations.service import resolve_location
from clearpath.permits.release import ReleaseData, ReleaseProvider
from clearpath.permits.schemas import PROJECT_TYPES, PermitLookupError
from clearpath.permits.service import lookup_permits

log = logging.getLogger(__name__)

_SOURCE_KEY = re.compile(r"^[A-Z0-9][A-Z0-9_-]{0,79}$")


# --------------------------------------------------------------------------------------
# Error envelope (the one place it is built)
# --------------------------------------------------------------------------------------


class ApiError(Exception):
    """An error with an HTTP status, rendered in the envelope. Mirrors Person 3's DomainError."""

    def __init__(self, code: str, message: str, http_status: int = 400, details: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.details = details or {}


def request_id_for(request: Request) -> str:
    """Use request.state.request_id if the app set one, else make one and store it."""
    rid = getattr(request.state, "request_id", None)
    if not rid:
        rid = str(uuid.uuid4())
        request.state.request_id = rid
    return rid


def error_response(request: Request, status: int, code: str, message: str, details: dict | None = None) -> JSONResponse:
    rid = request_id_for(request)
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "details": details or {}}, "request_id": rid},
        headers={"X-Request-ID": rid},
    )


def _mapped_error(exc: Exception) -> tuple[int, str, str, dict] | None:
    if isinstance(exc, RequestValidationError):
        fields = [{"loc": list(e["loc"]), "type": e["type"]} for e in exc.errors()]
        return 422, "validation_error", "Request validation failed.", {"fields": fields}
    if isinstance(exc, LocationInputError):
        return 422, exc.code, exc.message, {}
    if isinstance(exc, PermitLookupError):
        return exc.http_status, exc.code, exc.message, ({"path": exc.path} if exc.path else {})
    # ApiError and Person 3's DomainError (duck-typed so we don't import it).
    code, message, status = (getattr(exc, a, None) for a in ("code", "message", "http_status"))
    if isinstance(code, str) and isinstance(message, str) and isinstance(status, int):
        details = getattr(exc, "details", None)
        return status, code, message, details if isinstance(details, dict) else {}
    return None


class EnvelopeRoute(APIRoute):
    """Route class that renders every error from these routes in the shared envelope."""

    def get_route_handler(self):
        original = super().get_route_handler()

        async def handler(request: Request):
            rid = request_id_for(request)
            try:
                response = await original(request)
            except StarletteHTTPException:
                raise  # the app's own handler formats these
            except Exception as exc:  # noqa: BLE001 - every error becomes an envelope
                mapped = _mapped_error(exc)
                if mapped is None:
                    log.exception("unhandled error in lookup route")  # server log only, never the response
                    return error_response(request, 500, "internal_error", "An internal error occurred.")
                return error_response(request, *mapped)
            response.headers["X-Request-ID"] = rid
            return response

        return handler


# --------------------------------------------------------------------------------------
# Request bodies (unknown fields rejected, no type coercion)
# --------------------------------------------------------------------------------------


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class AreaBody(_Strict):
    jurisdiction: str


class FixtureBody(_Strict):
    jurisdiction: str
    name: str | None = None


class LocationBody(_Strict):
    """Exactly one of these must be given; that check returns 422 invalid_location_input."""

    selected_area: AreaBody | None = None
    area: AreaBody | None = None
    point: dict[str, Any] | None = None
    address: dict[str, Any] | None = None
    fixture: FixtureBody | None = None


class PermitLookupBody(_Strict):
    location: LocationBody
    project_type: Literal[PROJECT_TYPES]  # type: ignore[valid-type]
    profile_key: str | None = None
    facts: dict[str, Any] = Field(default_factory=dict)


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------


def _warning(code: str, message: str, **extra: Any) -> dict:
    return {"code": code, "message": message, **extra}


def _mode(provider: ReleaseProvider) -> str:
    return "synthetic" if provider.demo_mode else "reviewed_public"


def _active_releases(provider: ReleaseProvider) -> list[tuple[CoverageEntry, ReleaseData]]:
    entries = sorted(provider.coverage(), key=lambda e: (e.jurisdiction, e.project_type, e.profile_key or ""))
    found = []
    for entry in entries:
        release = provider.get_active(entry.jurisdiction, entry.project_type, entry.profile_key)
        if release is not None:
            found.append((entry, release))
    return found


def _dataset_warnings(provider: ReleaseProvider, releases: Iterable[ReleaseData]) -> list[dict]:
    warnings = []
    if provider.demo_mode:
        warnings.append(_warning("synthetic_dataset",
                                 "This checklist comes from a synthetic test dataset, not the reviewed city sources."))
    if any(r.test_only_unreviewed for r in releases):
        warnings.append(_warning("test_only_unreviewed_release",
                                 "TEST ONLY: unreviewed draft data was loaded as reviewed public data. "
                                 "Do not rely on this result."))
    return warnings


def _checked_at(value: Any) -> str | None:
    return str(value) if value is not None else None


# --------------------------------------------------------------------------------------
# Router
# --------------------------------------------------------------------------------------


def build_lookup_router(
    provider: ReleaseProvider,
    registry: Iterable[Jurisdiction] | Mapping[str, Jurisdiction],
    *,
    dependencies: Sequence[Any] = (),
) -> APIRouter:
    """Build the lookup router. The caller adds the /api/v1 prefix and the API-key dependency."""
    cities = list(registry.values()) if isinstance(registry, Mapping) else list(registry)
    router = APIRouter(route_class=EnvelopeRoute, dependencies=list(dependencies))

    @router.get("/jurisdictions")
    def get_jurisdictions(request: Request) -> dict:
        active = _active_releases(provider)
        by_city: dict[str, list[dict]] = {}
        for entry in sorted(provider.coverage(), key=lambda e: (e.jurisdiction, e.project_type, e.profile_key or "")):
            release = next((r for e, r in active if e == entry), None)
            by_city.setdefault(entry.jurisdiction, []).append(
                {
                    "project_type": entry.project_type,
                    "profile_key": entry.profile_key,
                    "release": (
                        {"id": release.release_id, "content_hash": release.content_hash,
                         "dataset_mode": release.dataset_mode, "published_at": None}
                        if release else None
                    ),
                    "sources": (
                        [{"source_key": k, "title": s.get("title"), "checked_at": _checked_at(s.get("checked_at"))}
                         for k, s in release.sources.items()]
                        if release else []
                    ),
                }
            )
        warnings = _dataset_warnings(provider, (r for _, r in active))
        warnings.append(_warning(
            "registry_not_coverage",
            "A city in this list has rule coverage only if its coverage list is non-empty. "
            "Empty coverage means no curated rules yet.",
        ))
        return {
            "dataset_mode": _mode(provider),
            "request_id": request_id_for(request),
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "jurisdictions": [
                {
                    "slug": c.slug,
                    "name": c.name,
                    "state": c.state,
                    "timezone": c.timezone,
                    "permit_page_url": c.permit_page_url,
                    "coverage": by_city.get(c.slug, []),
                }
                for c in cities
            ],
            "warnings": warnings,
        }

    @router.post("/locations/resolve")
    def post_locations_resolve(body: LocationBody, request: Request) -> dict:
        resolution = resolve_location(
            body.model_dump(exclude_unset=True), cities, provider.coverage(), dataset_mode=_mode(provider)
        )
        return {
            "dataset_mode": _mode(provider),
            "request_id": request_id_for(request),
            "location": resolution.to_dict(),
            "warnings": [dict(w) for w in resolution.warnings],
        }

    @router.post("/permit-lookups")
    def post_permit_lookups(body: PermitLookupBody, request: Request) -> dict:
        result = lookup_permits(body.model_dump(exclude_unset=True), provider, cities)
        return {"dataset_mode": result.pop("dataset_mode"), "request_id": request_id_for(request), **result}

    @router.get("/sources/{source_key}")
    def get_source(source_key: str, request: Request) -> dict:
        matches = (
            [(e, r) for e, r in _active_releases(provider) if source_key in r.sources]
            if _SOURCE_KEY.match(source_key)
            else []
        )
        if not matches:
            raise ApiError("source_not_found", "No source with that key is in the active rule data.", http_status=404)

        descriptor = matches[0][1].sources[source_key]
        passages, seen = [], set()
        for _, release in matches:
            for pid, p in release.passages.items():
                if p.get("source_key") == source_key and pid not in seen:
                    seen.add(pid)
                    passages.append({"id": pid, "locator": p.get("locator"), "excerpt": p.get("excerpt"),
                                     "review_status": p.get("review_status")})

        warnings = _dataset_warnings(provider, (r for _, r in matches))
        if any(p["review_status"] != "reviewed" for p in passages):
            warnings.append(_warning("unreviewed_extraction",
                                     "Some text from this source has not been checked by a person yet.",
                                     source_keys=[source_key]))
        if any(dict(r.sources[source_key]) != dict(descriptor) for _, r in matches[1:]):
            warnings.append(_warning("source_differs_across_releases",
                                     "Active releases describe this source differently. The first one is shown."))
        return {
            "dataset_mode": _mode(provider),
            "request_id": request_id_for(request),
            "source": {
                "key": source_key,
                "url": descriptor.get("url"),
                "title": descriptor.get("title"),
                "publisher": descriptor.get("publisher"),
                "authority_type": descriptor.get("authority_type"),
                "checked_at": _checked_at(descriptor.get("checked_at")),
                "sha256": descriptor.get("sha256"),
                "verification_depth": descriptor.get("verification_depth"),
                "terms_note": descriptor.get("terms_note"),
                "passages": passages,
                "releases": [{"id": r.release_id, "profile_key": r.profile_key, "dataset_mode": r.dataset_mode}
                             for _, r in matches],
            },
            "warnings": warnings,
        }

    return router
