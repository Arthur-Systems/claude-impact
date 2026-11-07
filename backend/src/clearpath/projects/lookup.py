"""The lookup boundary between projects (Person 5) and permit lookup (Person 4).

Projects never trust a client's applicability or boundary result. They call a
``PermitLookupProvider``. Until Person 4's service is wired in, the default is
``FixtureLookupStub``, which reads a SYNTHETIC fixture and does no network I/O.

To swap in the real service, implement this Protocol (an adapter around
``permits.service.lookup_permits`` plus the pinned release's milestone templates)
and override the ``get_lookup_provider`` dependency in ``projects.routes``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

FIXTURE = Path(__file__).parent / "fixtures" / "lookup_stub_irvine_adu.json"
ACCEPTED_LOCATION_STATES = ("confirmed", "selected_area", "synthetic_fixture")


@dataclass(frozen=True)
class LookupRequest:
    project_type: str
    subtype: str | None
    jurisdiction: str | None
    location: dict  # declared_location as stored on the project
    rule_facts: dict
    profile_key: str | None = None


@dataclass(frozen=True)
class ScopeAssessment:
    """Local (no network) coverage check used for drafts."""

    coverage_reason: str  # activation_required | missing_information | location_unresolved | rule_coverage_unavailable
    missing_fact_keys: list[str]
    accepted_fact_keys: list[str] | None  # None = no matching profile, so rule facts must be empty
    warnings: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class LookupResult:
    """Server-side lookup output needed to activate a project.

    ``requirements[*].applicability`` is applies / needs_information / not_applicable.
    ``milestones`` are the pinned release's templates, in template order.
    """

    status: str  # ok | rule_coverage_unavailable | missing_information | location_unresolved | dataset_unavailable
    location_status: str
    release: dict | None = None
    pathways: list[dict] = field(default_factory=list)  # {key, title, status, citation_ids, missing_fact_keys}
    requirements: list[dict] = field(default_factory=list)
    milestones: list[dict] = field(default_factory=list)
    conflicts: list[dict] = field(default_factory=list)
    citations: list[dict] = field(default_factory=list)
    missing_fact_keys: list[str] = field(default_factory=list)
    warnings: list[dict] = field(default_factory=list)


class PermitLookupProvider(Protocol):
    def assess_scope(self, request: LookupRequest) -> ScopeAssessment: ...

    def lookup(self, request: LookupRequest) -> LookupResult: ...


SYNTHETIC_WARNING = {
    "code": "synthetic_dataset",
    "message": "Demo release uses synthetic, unreviewed data. Do not rely on it for a real permit.",
}
SELECTED_AREA_WARNING = {
    "code": "property_not_verified",
    "message": "Location is a selected area (City of Irvine). No specific property was checked.",
}


def location_status(location: dict) -> str:
    mode = location.get("mode")
    if mode == "selected_area":
        return "selected_area"
    if mode == "fixture":
        return "synthetic_fixture"
    return location.get("resolution_status") or "unresolved"


class FixtureLookupStub:
    """SYNTHETIC stand-in for Person 4's lookup. Deterministic, offline."""

    def __init__(self, fixture: dict | None = None):
        self.data = fixture if fixture is not None else _load_fixture()

    def _profile(self, req: LookupRequest) -> dict | None:
        for p in self.data["profiles"]:
            if req.profile_key and req.profile_key != p["profile_key"]:
                continue
            if (p["project_type"], p["subtype"], p["jurisdiction"]) == (req.project_type, req.subtype, req.jurisdiction):
                return p
        return None

    def _warnings(self, req: LookupRequest) -> list[dict]:
        out = []
        if self.data.get("dataset_mode") == "synthetic":
            out.append(SYNTHETIC_WARNING)
        if location_status(req.location) == "selected_area":
            out.append(SELECTED_AREA_WARNING)
        return out

    def _location_ok(self, p: dict, req: LookupRequest) -> bool:
        st = location_status(req.location)
        if st == "selected_area":
            return req.location.get("area_key") in p["area_keys"]
        return st in ACCEPTED_LOCATION_STATES

    def _scope(self, p: dict, req: LookupRequest) -> tuple[list[str], bool]:
        """Return (missing scope/declared fact keys, scope_contradicted)."""
        missing = [k for k in p["fact_keys"] if req.rule_facts.get(k) is None]
        contradicted = any(
            req.rule_facts.get(k) is not None and req.rule_facts.get(k) != v for k, v in p["scope"].items()
        )
        return missing, contradicted

    def assess_scope(self, req: LookupRequest) -> ScopeAssessment:
        p = self._profile(req)
        if p is None:
            return ScopeAssessment("rule_coverage_unavailable", [], None, [])
        missing, contradicted = self._scope(p, req)
        warnings = self._warnings(req)
        if contradicted:
            return ScopeAssessment("rule_coverage_unavailable", missing, p["fact_keys"], warnings)
        if not self._location_ok(p, req):
            return ScopeAssessment("location_unresolved", missing, p["fact_keys"], warnings)
        if any(k in missing for k in p["scope"]):
            return ScopeAssessment("missing_information", missing, p["fact_keys"], warnings)
        return ScopeAssessment("activation_required", missing, p["fact_keys"], warnings)

    def lookup(self, req: LookupRequest) -> LookupResult:
        loc = location_status(req.location)
        p = self._profile(req)
        if p is None:
            return LookupResult("rule_coverage_unavailable", loc)
        missing, contradicted = self._scope(p, req)
        if contradicted:
            return LookupResult("rule_coverage_unavailable", loc, missing_fact_keys=missing)
        if not self._location_ok(p, req):
            return LookupResult("location_unresolved", loc)
        pathways = []
        for pw in p["pathways"]:
            pw_missing = [k for k in pw.get("requires_facts", []) if req.rule_facts.get(k) is None]
            pathways.append({
                "key": pw["key"], "title": pw["title"], "citation_ids": pw["citation_ids"],
                "status": "needs_information" if pw_missing else "applies", "missing_fact_keys": pw_missing,
            })
        requirements = []
        for r in p["requirements"]:
            r_missing = [k for k in r.get("unknown_without", []) if req.rule_facts.get(k) is None]
            requirements.append({
                "key": r["key"], "kind": r["kind"], "title": r["title"],
                "required_for_preparation": r["required_for_preparation"], "citation_ids": r["citation_ids"],
                "applicability": "needs_information" if r_missing else "applies", "missing_fact_keys": r_missing,
            })
        return LookupResult(
            status="ok", location_status=loc, release=p["release"], pathways=pathways, requirements=requirements,
            milestones=p["milestones"], conflicts=p["conflicts"], citations=p["citations"],
            missing_fact_keys=missing, warnings=self._warnings(req),
        )


@lru_cache(maxsize=1)
def _load_fixture() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text())
