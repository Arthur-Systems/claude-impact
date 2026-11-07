"""Plain domain types for milestone graphs and project state.

Pure Python: no database, no web framework, no wall clock. Services build these
from persisted rows and pass explicit ``now``/``as_of`` values in.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Literal

MilestoneStateName = Literal["not_started", "in_progress", "completed"]
RequirementStatus = Literal["not_started", "in_progress", "ready"]
Applicability = Literal["applies", "needs_information", "not_applicable"]
EventKind = Literal["start", "complete", "reopen"]

MILESTONE_STATES = ("not_started", "in_progress", "completed")
REQUIREMENT_STATUSES = ("not_started", "in_progress", "ready")
EVENT_KINDS = ("start", "complete", "reopen")
CORRECTION_CODES = ("city_correction", "applicant_revision")


@dataclass(frozen=True)
class AssumedDays:
    """Team estimate in calendar days. Always an ASSUMPTION, never a due date."""

    min_days: int | None = None
    max_days: int | None = None
    rationale: str | None = None

    @property
    def known(self) -> bool:
        return self.min_days is not None and self.max_days is not None


@dataclass(frozen=True)
class MilestoneDef:
    key: str
    title: str
    position: int
    predecessors: tuple[str, ...] = ()
    requirement_keys: tuple[str, ...] = ()
    actor: str | None = None  # "city" | "applicant" | None (unknown)
    assumed: AssumedDays = field(default_factory=AssumedDays)
    citation_ids: tuple[str, ...] = ()
    action_titles: dict | None = None  # optional {"start": str, "complete": str}
    city_service_target: dict | None = None
    statutory_clock: dict | None = None


@dataclass(frozen=True)
class MilestoneState:
    key: str
    state: MilestoneStateName = "not_started"
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def with_(self, **kw) -> "MilestoneState":
        return replace(self, **kw)


@dataclass(frozen=True)
class RequirementState:
    key: str
    applicability: Applicability
    status: RequirementStatus = "not_started"
    required_for_preparation: bool = True
    missing_fact_keys: tuple[str, ...] = ()
    title: str = ""
    kind: str = "document"


@dataclass(frozen=True)
class SourceConflict:
    rule_keys: tuple[str, ...]
    sources: tuple[str, ...]
    summary: str


class DomainConflict(Exception):
    """A rule violation the API maps to an HTTP status (409 by default)."""

    def __init__(self, code: str, message: str, details: dict | None = None, http_status: int = 409):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.http_status = http_status
