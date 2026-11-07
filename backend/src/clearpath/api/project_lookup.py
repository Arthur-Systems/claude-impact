"""Person 5's PermitLookupProvider backed by Person 4's lookup over the active DB releases.

Statuses, citations and milestone templates all come from the pinned release; nothing is
added here. A pathway is offered for activation when its own rule is met; source conflicts
are carried into the project (and its timeline) rather than hidden.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from clearpath.domain.errors import DomainError
from clearpath.locations.schemas import Jurisdiction
from clearpath.permits.predicates import PredicateError, Tri, evaluate_predicate
from clearpath.permits.release import ReleaseData, ReleaseProvider
from clearpath.permits.schemas import LookupInputError, LookupUnavailable
from clearpath.permits.service import lookup_permits
from clearpath.projects.lookup import LookupRequest, LookupResult, ScopeAssessment, location_status

_STATUS = {Tri.TRUE: "applies", Tri.FALSE: "not_applicable", Tri.UNKNOWN: "needs_information"}


def _unavailable() -> DomainError:
    return DomainError("dataset_unavailable", "The rule dataset is unavailable right now.", http_status=503)


class ProjectLookupAdapter:
    def __init__(self, provider: ReleaseProvider, registry: Iterable[Jurisdiction]) -> None:
        self.provider = provider
        self.registry = list(registry)

    @staticmethod
    def _location(req: LookupRequest) -> dict | None:
        loc = req.location or {}
        if not req.jurisdiction:
            return None
        if loc.get("mode") == "selected_area" and loc.get("area_key") in (None, f"{req.jurisdiction}-citywide"):
            return {"selected_area": {"jurisdiction": req.jurisdiction}}
        if loc.get("mode") == "fixture":
            return {"fixture": {"jurisdiction": req.jurisdiction}}
        return None

    def _run(self, req: LookupRequest) -> tuple[dict | None, ReleaseData | None]:
        location = self._location(req)
        if location is None:
            return None, None
        body: dict[str, Any] = {"location": location, "project_type": req.project_type, "facts": dict(req.rule_facts)}
        if req.profile_key:
            body["profile_key"] = req.profile_key
        try:
            result = lookup_permits(body, self.provider, self.registry)
        except LookupInputError as error:
            raise DomainError(error.code, error.message, {"path": error.path} if error.path else {}, http_status=422) from None
        release = None
        if result.get("release"):
            release = self.provider.get_active(req.jurisdiction, req.project_type, result["profile_key"])
        return result, release

    @staticmethod
    def _own_status(release: ReleaseData, rule: Mapping, req: LookupRequest) -> tuple[str, list[str]]:
        schema = {"project_type": "string", **dict(release.fact_schema)}
        facts = {**req.rule_facts, "project_type": req.project_type}
        try:
            result = evaluate_predicate(rule.get("applies_if"), facts, schema)
        except PredicateError:
            return "needs_information", []
        return _STATUS[result.value], list(result.missing_keys)

    def assess_scope(self, req: LookupRequest) -> ScopeAssessment:
        profiles = self.provider.configured_profiles(req.jurisdiction, req.project_type) if req.jurisdiction else ()
        if req.profile_key:
            profiles = tuple(p for p in profiles if p == req.profile_key)
        if not profiles:
            return ScopeAssessment("rule_coverage_unavailable", [], None, [])
        releases = [r for r in (self.provider.get_active(req.jurisdiction, req.project_type, p) for p in profiles) if r]
        if not releases:
            raise _unavailable()
        keys = sorted({k for r in releases for k in r.fact_schema} - {"project_type"})
        missing = [k for k in keys if req.rule_facts.get(k) is None]
        try:
            result, release = self._run(req)
        except LookupUnavailable:
            raise _unavailable() from None
        if result is None:
            return ScopeAssessment("location_unresolved", missing, keys, [])
        if release is None:
            return ScopeAssessment("missing_information", missing, keys, result["warnings"])
        statuses = {self._own_status(release, p, req)[0] for p in release.pathways}
        reason = ("activation_required" if "applies" in statuses
                  else "missing_information" if "needs_information" in statuses else "rule_coverage_unavailable")
        return ScopeAssessment(reason, missing, keys, result["warnings"])

    def lookup(self, req: LookupRequest) -> LookupResult:
        try:
            result, release = self._run(req)
        except LookupUnavailable:
            return LookupResult("dataset_unavailable", location_status(req.location or {}))
        if result is None:
            return LookupResult("location_unresolved", location_status(req.location or {}))
        loc = result["location"]["status"]
        if result["status"] in ("rule_coverage_unavailable", "location_unresolved"):
            return LookupResult(result["status"], loc, missing_fact_keys=result["missing_fact_keys"], warnings=result["warnings"])
        if release is None:
            return LookupResult("missing_information", loc, missing_fact_keys=result["missing_fact_keys"],
                                warnings=result["warnings"])

        def ids(row: Mapping) -> list[str]:
            return [str(pid) for pid in row.get("citations") or []]

        rules = {p["key"]: p for p in release.pathways}
        pathways = []
        for item in result["pathways"]:
            status, missing = self._own_status(release, rules[item["key"]], req)
            pathways.append({"key": item["key"], "title": item["title"], "status": status, "missing_fact_keys": missing,
                             "citation_ids": ids(rules[item["key"]]), "lookup_status": item["status"],
                             "lookup_status_reason": item["status_reason"]})
        rules = {r["key"]: r for r in release.requirements}
        requirements = [{"key": item["key"], "kind": item["kind"], "title": item["title"],
                         "required_for_preparation": item["required_for_preparation"],
                         "citation_ids": ids(rules[item["key"]]), "applicability": item["status"],
                         "missing_fact_keys": item["missing_fact_keys"]} for item in result["requirements"]]

        def clock(m: Mapping, kind: str) -> dict | None:
            value = m.get("published_clock")
            return dict(value) if isinstance(value, Mapping) and value.get("kind") == kind else None

        milestones = [{"key": m["key"], "title": m["title"], "predecessor_keys": list(m.get("predecessors") or []),
                       "requirement_keys": list(m.get("requirements") or []), "actor": m.get("actor"),
                       "assumed_days": dict(m["assumed_days"]) if m.get("assumed_days") else None,
                       "action_titles": None, "city_service_target": clock(m, "city_service_target"),
                       "statutory_clock": clock(m, "statutory_clock"), "citation_ids": ids(m)}
                      for m in release.milestones]
        cited = dict.fromkeys(pid for group in (pathways, requirements, milestones) for row in group
                              for pid in row["citation_ids"])
        citations = []
        for pid in cited:
            passage = release.passages.get(pid)
            source = release.sources.get(passage.get("source_key")) if passage else None
            if passage is None or source is None:
                continue
            citations.append({"id": pid, "snapshot_id": None, "source_key": passage["source_key"],
                              "url": source.get("url"), "title": source.get("title"),
                              "publisher": source.get("publisher"), "authority_type": source.get("authority_type"),
                              "locator": passage.get("locator"), "excerpt": passage.get("excerpt"),
                              "snapshot_sha256": source.get("sha256"),
                              "checked_at": str(source["checked_at"]) if source.get("checked_at") else None,
                              "review_status": passage.get("review_status")})
        published_at = getattr(self.provider, "published_at", {}).get(release.release_id)
        summary = {"id": release.release_id, "jurisdiction": release.jurisdiction, "project_type": release.project_type,
                   "profile_key": release.profile_key, "content_hash": release.content_hash,
                   "dataset_mode": release.dataset_mode, "published_at": published_at}
        conflicts = [{**c, "sources": c["source_keys"]} for c in result["conflicts"]]
        return LookupResult("ok", loc, release=summary, pathways=pathways, requirements=requirements,
                            milestones=milestones, conflicts=conflicts, citations=citations,
                            missing_fact_keys=result["missing_fact_keys"], warnings=result["warnings"])
