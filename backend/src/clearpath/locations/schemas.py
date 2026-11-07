"""Location data shapes (SPEC.md section 7). Matches backend/tests/fixtures/api_examples/."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, NamedTuple

# Request keys (exactly one per request) -> response `mode` value.
INPUT_MODES = {
    "selected_area": "selected_area",
    "area": "selected_area",  # alias
    "point": "point",
    "address": "address",
    "fixture": "fixture",
}

STATUSES = ("confirmed", "selected_area", "ambiguous", "unresolved", "outside_supported_area")
CHECKLIST_STATUSES = frozenset({"confirmed", "selected_area"})
"""Only these location states may receive a checklist."""


class CoverageEntry(NamedTuple):
    """One curated rule profile with a published release: (jurisdiction, project_type, profile_key)."""

    jurisdiction: str
    project_type: str
    profile_key: str | None


@dataclass(frozen=True)
class Jurisdiction:
    """A city in the reference registry. Being listed does NOT mean rules exist for it."""

    slug: str
    name: str
    state: str = "CA"
    timezone: str = "America/Los_Angeles"
    permit_page_url: str | None = None


class LocationInputError(ValueError):
    """Malformed location input. The route maps this to 422."""

    http_status = 422

    def __init__(self, message: str, code: str = "invalid_location_input") -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@dataclass(frozen=True)
class LocationInput:
    mode: str  # selected_area | point | address | fixture
    payload: Any


@dataclass(frozen=True)
class LocationResolution:
    mode: str
    status: str
    status_reason: str | None = None
    jurisdiction: Jurisdiction | None = None
    property_verified: bool = False
    candidates: tuple = ()
    boundary_evidence: dict | None = None
    warnings: tuple[dict, ...] = field(default_factory=tuple)

    @property
    def allows_checklist(self) -> bool:
        return self.status in CHECKLIST_STATUSES

    def to_dict(self) -> dict:
        """The `location` object exactly as in the api_examples files."""
        return {
            "mode": self.mode,
            "status": self.status,
            "status_reason": self.status_reason,
            "property_verified": self.property_verified,
            "jurisdiction": (
                {"slug": self.jurisdiction.slug, "name": self.jurisdiction.name} if self.jurisdiction else None
            ),
            "candidates": [dict(c) for c in self.candidates],
            "boundary_evidence": dict(self.boundary_evidence) if self.boundary_evidence else None,
        }
