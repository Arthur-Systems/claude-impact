"""Person 4's permit lookup behind Person 5's ``PermitLookupProvider`` Protocol.

Replaces ``projects.lookup.FixtureLookupStub``. Person 5 changes one line in
``projects/routes.py``::

    def get_lookup_provider() -> PermitLookupProvider:
        return ReleaseLookupProvider(provider, registry)

where ``provider`` is a ``ReleaseProvider`` (e.g. ``dev_server.load_real_provider()`` or
``load_synthetic_provider()``, later Person 3's database) and ``registry`` is
``locations.service.load_registry()``. Build both once at startup, not per request.

Everything comes from the release: no number, title, URL, clock or citation is made up.
Fields the release does not have are ``None``. No network, no database.

Output, beyond the stub's fields:
* pathways: ``status_reason`` and ``rule_status``. ``rule_status`` is the pathway's rule alone
  (applies / not_applicable / needs_information), without source conflicts. A conflicted
  pathway has ``status`` needs_information and ``status_reason`` source_conflict even when
  its rule is met (SPEC.md section 7: a conflicted rule is not a definite answer).
* requirements: ``status_reason``.
* milestones: ``published_clock``, copied from the manifest. ``city_service_target`` and
  ``statutory_clock`` are filled only from manifest fields of exactly those names, because a
  published clock can mix a city target with state guidance.
* citations: ``excerpt``.
* conflicts: ``sources`` as well as ``source_keys`` (projects/service.py reads ``sources``).
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from clearpath.locations.schemas import Jurisdiction
from clearpath.locations.service import resolve_location
from clearpath.permits.predicates import PredicateError, Tri, evaluate_predicate, to_status
from clearpath.permits.release import ReleaseData, ReleaseProvider
from clearpath.permits.schemas import LookupInputError, LookupUnavailable
from clearpath.permits.service import lookup_permits
from clearpath.projects.lookup import LookupRequest, LookupResult, ScopeAssessment

AREA_SUFFIX = "-citywide"
"""Person 5's area keys look like 'irvine-ca-citywide'. A bare city slug is accepted too."""


def _warning(code: str, message: str, **extra: Any) -> dict:
    return {"code": code, "message": message, **extra}


class ReleaseLookupProvider:
    """Implements ``assess_scope`` and ``lookup`` on top of ``lookup_permits``."""

    def __init__(self, provider: ReleaseProvider, registry: Iterable[Jurisdiction] | Mapping[str, Jurisdiction]):
        self.provider = provider
        cities = registry.values() if isinstance(registry, Mapping) else registry
        self.cities = {j.slug: j for j in cities}

    # ---------------------------------------------------------------- location

    def _mode(self) -> str:
        return "synthetic" if self.provider.demo_mode else "reviewed_public"

    def _area_jurisdiction(self, area_key: Any) -> str | None:
        if not isinstance(area_key, str):
            return None
        if area_key in self.cities:
            return area_key
        if area_key.endswith(AREA_SUFFIX) and area_key[: -len(AREA_SUFFIX)] in self.cities:
            return area_key[: -len(AREA_SUFFIX)]
        return None

    def _location_input(self, req: LookupRequest) -> tuple[dict | None, str | None]:
        """Person 5's declared_location -> (my location input or None, jurisdiction slug)."""
        loc = req.location or {}
        mode = loc.get("mode")
        if mode == "selected_area":
            slug = self._area_jurisdiction(loc.get("area_key"))
            if slug is None or (req.jurisdiction and req.jurisdiction != slug):
                return None, req.jurisdiction
            return {"selected_area": {"jurisdiction": slug}}, slug
        if mode == "fixture":
            if not req.jurisdiction:
                return None, None
            name = loc.get("fixture_id")
            return {"fixture": {"jurisdiction": req.jurisdiction, "name": name if isinstance(name, str) else None}}, req.jurisdiction
        if mode == "point":
            return {"point": {"longitude": loc.get("longitude"), "latitude": loc.get("latitude")}}, req.jurisdiction
        if mode == "address":
            return {"address": dict(loc.get("address") or {})}, req.jurisdiction
        return None, req.jurisdiction

    def _location_status(self, location_input: dict | None) -> str:
        if location_input is None:
            return "unresolved"
        res = resolve_location(location_input, self.cities, self.provider.coverage(), dataset_mode=self._mode())
        if res.status == "confirmed" and res.mode == "fixture":
            return "synthetic_fixture"
        return res.status  # selected_area | confirmed | unresolved | ambiguous | outside_supported_area

    # ---------------------------------------------------------------- release helpers

    @staticmethod
    def _resolvable(release: ReleaseData, ids: Any) -> list[str]:
        out = []
        for pid in ids if isinstance(ids, list) else []:
            passage = release.passages.get(str(pid))
            if passage is not None and passage.get("source_key") in release.sources:
                out.append(str(pid))
        return out

    @staticmethod
    def _citation(release: ReleaseData, pid: str) -> dict:
        p = release.passages[pid]
        s = release.sources[p["source_key"]]
        return {
            "id": pid,
            "snapshot_id": None,  # set once Person 3's DB stores snapshots
            "source_key": p["source_key"],
            "url": s.get("url"),
            "title": s.get("title"),
            "publisher": s.get("publisher"),
            "authority_type": s.get("authority_type"),
            "locator": p.get("locator"),
            "snapshot_sha256": s.get("sha256"),
            "checked_at": str(s["checked_at"]) if s.get("checked_at") is not None else None,
            "excerpt": p.get("excerpt"),
            "review_status": p.get("review_status"),
        }

    @staticmethod
    def _release_summary(release: ReleaseData) -> dict:
        return {
            "id": release.release_id,
            "jurisdiction": release.jurisdiction,
            "project_type": release.project_type,
            "profile_key": release.profile_key,
            "content_hash": release.content_hash,
            "schema_version": release.schema_version,
            "dataset_mode": release.dataset_mode,
            "published_at": None,  # not recorded until Person 3's DB publishes releases
        }

    @staticmethod
    def _rule_status(release: ReleaseData, predicate: Any, facts: dict) -> str:
        schema = dict(release.fact_schema)
        schema.setdefault("project_type", "string")
        try:
            return to_status(evaluate_predicate(predicate, facts, schema))
        except PredicateError:
            return "needs_information"

    # ---------------------------------------------------------------- Protocol

    def lookup(self, req: LookupRequest) -> LookupResult:
        location_input, _ = self._location_input(req)
        loc_status = self._location_status(location_input)
        if location_input is None:
            return LookupResult("location_unresolved", loc_status)

        body: dict[str, Any] = {"location": location_input, "project_type": req.project_type,
                                "facts": dict(req.rule_facts or {})}
        if req.profile_key:
            body["profile_key"] = req.profile_key
        try:
            out = lookup_permits(body, self.provider, self.cities)
        except LookupUnavailable:
            return LookupResult("dataset_unavailable", loc_status)
        except LookupInputError as error:
            if error.code == "invalid_location_input":
                return LookupResult("location_unresolved", loc_status)
            return LookupResult("missing_information", loc_status, warnings=[_warning(
                "invalid_rule_facts",
                "Some project facts don't match the values this rule dataset allows. Correct them before activating.",
                fact_error_code=error.code,
            )])

        if out["status"] == "location_unresolved":
            return LookupResult("location_unresolved", loc_status, warnings=out["warnings"])
        if out["status"] == "rule_coverage_unavailable":
            return LookupResult("rule_coverage_unavailable", loc_status, warnings=out["warnings"])
        if out["release"] is None:  # several profiles and no profile_key
            return LookupResult("missing_information", loc_status, missing_fact_keys=out["missing_fact_keys"],
                                warnings=out["warnings"])

        slug = out["location"]["jurisdiction"]["slug"]
        release = self.provider.get_active(slug, req.project_type, out["profile_key"])
        if release is None:  # disappeared between calls
            return LookupResult("dataset_unavailable", loc_status)

        facts = {**out["facts_used"], "project_type": req.project_type}
        pathway_rows = {p.get("key"): p for p in release.pathways}
        requirement_rows = {r.get("key"): r for r in release.requirements}

        pathways = []
        for pw in out["pathways"]:
            row = pathway_rows[pw["key"]]
            pathways.append({
                "key": pw["key"], "title": pw["title"], "status": pw["status"],
                "status_reason": pw["status_reason"],
                "rule_status": self._rule_status(release, row.get("applies_if"), facts),
                "missing_fact_keys": pw["missing_fact_keys"],
                "citation_ids": self._resolvable(release, row.get("citations")),
            })

        rule_statuses = [p["rule_status"] for p in pathways]
        if not pathways or all(s == "not_applicable" for s in rule_statuses):
            return LookupResult("rule_coverage_unavailable", loc_status, missing_fact_keys=out["missing_fact_keys"],
                                warnings=out["warnings"])
        if "applies" not in rule_statuses:
            missing = sorted({k for p in pathways for k in p["missing_fact_keys"]})
            return LookupResult("missing_information", loc_status, missing_fact_keys=missing, warnings=out["warnings"])

        requirements = [
            {
                "key": r["key"], "kind": r["kind"], "title": r["title"],
                "required_for_preparation": r["required_for_preparation"],
                "applicability": r["status"], "status_reason": r["status_reason"],
                "missing_fact_keys": r["missing_fact_keys"],
                "citation_ids": self._resolvable(release, requirement_rows[r["key"]].get("citations")),
            }
            for r in out["requirements"]
        ]

        milestones = []
        for m in release.milestones:
            clock = m.get("published_clock")
            milestones.append({
                "key": m.get("key"),
                "title": m.get("title"),
                "predecessor_keys": list(m.get("predecessors") or []),
                "requirement_keys": list(m.get("requirements") or []),
                "actor": m.get("actor"),
                "assumed_days": m.get("assumed_days"),
                "action_titles": m.get("action_titles"),
                "city_service_target": m.get("city_service_target"),
                "statutory_clock": m.get("statutory_clock"),
                "published_clock": dict(clock) if isinstance(clock, Mapping) else clock,
                "citation_ids": self._resolvable(release, m.get("citations")),
            })

        cited: dict[str, None] = {}
        for item in pathways + requirements + milestones:
            for pid in item["citation_ids"]:
                cited.setdefault(pid, None)
        for m in milestones:
            if isinstance(m["published_clock"], Mapping):
                for pid in self._resolvable(release, m["published_clock"].get("citations")):
                    cited.setdefault(pid, None)

        return LookupResult(
            status="ok",
            location_status=loc_status,
            release=self._release_summary(release),
            pathways=pathways,
            requirements=requirements,
            milestones=milestones,
            conflicts=[{**c, "sources": list(c["source_keys"])} for c in out["conflicts"]],
            citations=[self._citation(release, pid) for pid in cited],
            missing_fact_keys=out["missing_fact_keys"],
            warnings=out["warnings"],
        )

    def assess_scope(self, req: LookupRequest) -> ScopeAssessment:
        """Local coverage check for drafts. No network, no writes."""
        _, area_slug = self._location_input(req)
        slug = req.jurisdiction or area_slug
        profiles = self.provider.configured_profiles(slug, req.project_type) if slug else ()
        if not profiles or (req.profile_key and req.profile_key not in profiles):
            return ScopeAssessment("rule_coverage_unavailable", [], None, [])

        candidates = [req.profile_key] if req.profile_key else list(profiles)
        releases = [r for r in (self.provider.get_active(slug, req.project_type, p) for p in candidates) if r]
        if not releases:
            return ScopeAssessment("rule_coverage_unavailable", [], None, [_warning(
                "dataset_unavailable", "The rule dataset for this profile is not available right now.")])
        accepted = sorted({k for r in releases for k in r.fact_schema if k != "project_type"})

        result = self.lookup(req)
        reason = {
            "ok": "activation_required",
            "missing_information": "missing_information",
            "location_unresolved": "location_unresolved",
            "rule_coverage_unavailable": "rule_coverage_unavailable",
            "dataset_unavailable": "rule_coverage_unavailable",
        }[result.status]
        return ScopeAssessment(reason, list(result.missing_fact_keys), accepted, list(result.warnings))
