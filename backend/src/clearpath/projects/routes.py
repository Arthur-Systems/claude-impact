"""HTTP routes for projects and timelines (spec §9). Mounted under /api/v1.

Integration seams (Person 3 overrides these with ``app.dependency_overrides``):
- ``get_session``: yields a SQLAlchemy Session (the route commits on success).
- ``require_api_key``: X-API-Key check (no-op placeholder here).
- ``get_lookup_provider``: Person 4's lookup adapter (defaults to the SYNTHETIC stub).
- ``get_now``: the only wall-clock read; tests override it.
- ``get_dataset_mode``: the deployment's dataset mode (``synthetic`` | ``public``), echoed as a
  top-level ``dataset_mode`` on project and timeline responses. Person 3 overrides it with
  ``settings.mode``; the default is ``synthetic`` because the default lookup is the synthetic stub.
"""

from __future__ import annotations

import os
import uuid
from functools import lru_cache
from datetime import date, datetime, timezone
from typing import Iterator

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from clearpath.timelines.model import DomainConflict

from . import service
from .lookup import FixtureLookupStub, PermitLookupProvider
from typing import Literal

from .schemas import (
    MilestoneEventInput,
    ProjectActivationInput,
    ProjectCreateInput,
    ProjectUpdateInput,
    RequirementUpdateInput,
)


def get_session() -> Iterator[Session]:  # pragma: no cover - replaced by Person 3's dependency
    raise RuntimeError("get_session must be overridden with the platform session dependency")
    yield  # noqa: unreachable


def require_api_key() -> None:
    """Placeholder. Person 3 overrides with the shared X-API-Key check."""


def _configured_mode() -> str:
    """Same switch as Person 3's settings: CLEARPATH_MODE = public (default) | synthetic."""
    return "synthetic" if os.environ.get("CLEARPATH_MODE", "public") == "synthetic" else "public"


@lru_cache(maxsize=2)
def _build_lookup_provider(mode: str) -> PermitLookupProvider:
    """Person 4's lookup over a release, built once per mode and reused for every request.

    public: Person 2's reviewed Irvine data (fails loudly if it doesn't pass the reviewed checks).
    synthetic: the labeled demo dataset. Failures are not cached, so a fixed file is picked up.
    """
    from clearpath.locations.service import load_registry
    from clearpath.permits.dev_server import load_real_provider, load_synthetic_provider
    from clearpath.permits.project_adapter import ReleaseLookupProvider

    releases = load_synthetic_provider() if mode == "synthetic" else load_real_provider()
    return ReleaseLookupProvider(releases, load_registry())


def warm_lookup_provider() -> None:
    """Call once at app startup so the dataset loads before the first request."""
    _build_lookup_provider(_configured_mode())


def get_lookup_provider() -> PermitLookupProvider:
    try:
        return _build_lookup_provider(_configured_mode())
    except Exception as exc:  # the dataset file is missing or fails its checks
        raise DomainConflict("dataset_unavailable", "The rule dataset is unavailable right now.",
                             {"reason": str(exc)[:300]}, 503) from exc


def get_now() -> datetime:
    return datetime.now(timezone.utc)


def get_dataset_mode() -> str:
    return _configured_mode()


def _out(body: dict, mode: str) -> dict:
    """Add the top-level dataset_mode. Wrapper responses ({event, project}) also echo the project's warnings."""
    out = {"dataset_mode": mode, **body}
    if "project" in body and "warnings" not in body:
        out["warnings"] = body["project"]["warnings"]
    return out


router = APIRouter(prefix="/api/v1/projects", tags=["projects"], dependencies=[Depends(require_api_key)])


@router.post("", status_code=201)
def create_project(body: ProjectCreateInput, session: Session = Depends(get_session),
                   provider: PermitLookupProvider = Depends(get_lookup_provider), now: datetime = Depends(get_now),
                   mode: str = Depends(get_dataset_mode)) -> dict:
    out = service.create_draft(session, body, provider, now)
    session.commit()
    return _out(out, mode)


@router.get("")
def list_projects(jurisdiction: str | None = Query(None, max_length=80),
                  project_type: Literal["adu", "duplex", "multifamily", "other_housing"] | None = None,
                  state: Literal["draft", "active"] | None = None,
                  coverage_status: Literal["configured", "unconfigured"] | None = None,
                  cursor: str | None = Query(None, max_length=300),
                  limit: int = Query(service.EVENTS_DEFAULT_LIMIT, ge=1, le=service.EVENTS_MAX_LIMIT),
                  session: Session = Depends(get_session), mode: str = Depends(get_dataset_mode)) -> dict:
    return _out(service.list_projects(session, jurisdiction=jurisdiction, project_type=project_type, state=state,
                                      coverage_status=coverage_status, cursor=cursor, limit=limit), mode)


@router.patch("/{project_id}")
def update_project(project_id: uuid.UUID, body: ProjectUpdateInput, session: Session = Depends(get_session),
                   provider: PermitLookupProvider = Depends(get_lookup_provider), now: datetime = Depends(get_now),
                   mode: str = Depends(get_dataset_mode)) -> dict:
    out = service.update_draft(session, project_id, body, provider, now)
    session.commit()
    return _out(out, mode)


@router.get("/{project_id}")
def read_project(project_id: uuid.UUID, session: Session = Depends(get_session), mode: str = Depends(get_dataset_mode)) -> dict:
    return _out(service.get_project(session, project_id), mode)


@router.post("/{project_id}/activate")
def activate_project(project_id: uuid.UUID, body: ProjectActivationInput, session: Session = Depends(get_session),
                     provider: PermitLookupProvider = Depends(get_lookup_provider), now: datetime = Depends(get_now),
                     mode: str = Depends(get_dataset_mode)) -> dict:
    out = service.activate_project(session, project_id, body, provider, now)
    session.commit()
    return _out(out, mode)


@router.patch("/{project_id}/requirements/{key}")
def update_requirement(project_id: uuid.UUID, key: str, body: RequirementUpdateInput,
                       session: Session = Depends(get_session), now: datetime = Depends(get_now),
                       mode: str = Depends(get_dataset_mode)) -> dict:
    out = service.set_requirement_status(session, project_id, key, body, now)
    session.commit()
    return _out(out, mode)


@router.post("/{project_id}/milestone-events")
def milestone_event(project_id: uuid.UUID, body: MilestoneEventInput,
                    session: Session = Depends(get_session), now: datetime = Depends(get_now),
                    mode: str = Depends(get_dataset_mode)) -> dict:
    out = service.record_milestone_event(session, project_id, body, now)
    session.commit()
    return _out(out, mode)


@router.get("/{project_id}/timeline")
def timeline(project_id: uuid.UUID, as_of: date = Query(..., description="Civil date (America/Los_Angeles), YYYY-MM-DD"),
             session: Session = Depends(get_session), mode: str = Depends(get_dataset_mode)) -> dict:
    return _out(service.get_timeline(session, project_id, as_of), mode)


@router.get("/{project_id}/events")
def events(project_id: uuid.UUID, cursor: str | None = Query(None, max_length=200),
           limit: int = Query(service.EVENTS_DEFAULT_LIMIT, ge=1, le=service.EVENTS_MAX_LIMIT),
           session: Session = Depends(get_session)) -> dict:
    return service.list_events(session, project_id, cursor, limit)
