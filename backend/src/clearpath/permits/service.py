"""Permit lookup: which pathways and requirements apply, and why (SPEC.md section 7).

Every title, URL, excerpt and rule comes from the release. This module adds no numbers,
fees, statutes, forms or links of its own. The output matches
backend/tests/fixtures/api_examples/permit_lookup_*.json, minus the ``example`` and
``request_id`` fields, which the route adds.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping

from clearpath.locations.schemas import Jurisdiction
from clearpath.locations.service import resolve_location
from clearpath.permits.predicates import (
    PredicateError,
    PredicateResult,
    Tri,
    evaluate_predicate,
    to_status,
    validate_facts,
)
from clearpath.permits.release import ReleaseData, ReleaseProvider
from clearpath.permits.schemas import (
    LookupInputError,
    LookupUnavailable,
    PermitLookupRequest,
    notice_for,
    parse_permit_lookup_request,
)

_REASON = {Tri.TRUE: "facts_met", Tri.FALSE: "facts_not_met", Tri.UNKNOWN: "missing_facts"}


def _warning(code: str, message: str, **extra: Any) -> dict:
    return {"code": code, "message": message, **extra}


# --------------------------------------------------------------------------------------
# Three-valued combinators over already-evaluated results
# --------------------------------------------------------------------------------------


def _combine(results: list[PredicateResult], decisive: Tri, otherwise: Tri) -> PredicateResult:
    if any(r.value is decisive for r in results):
        return PredicateResult(decisive, ())
    unknown = [r for r in results if r.value is Tri.UNKNOWN]
    if unknown:
        return PredicateResult(Tri.UNKNOWN, tuple(sorted({k for r in unknown for k in r.missing_keys})))
    return PredicateResult(otherwise, ())


def _all(results: list[PredicateResult]) -> PredicateResult:
    return _combine(results, Tri.FALSE, Tri.TRUE)


def _any(results: list[PredicateResult]) -> PredicateResult:
    return _combine(results, Tri.TRUE, Tri.FALSE)


# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------


class _Evidence:
    """Collects citation problems across one lookup, for the warnings list."""

    def __init__(self, release: ReleaseData) -> None:
        self.release = release
        self.unreviewed_sources: set[str] = set()
        self.unresolved = False

    def citations(self, passage_ids: Any) -> list[dict]:
        out = []
        for pid in passage_ids if isinstance(passage_ids, list) else []:
            passage = self.release.passages.get(str(pid))
            source = self.release.sources.get(passage.get("source_key")) if passage else None
            if passage is None or source is None:
                self.unresolved = True
                continue
            if not self.release.is_reviewed(str(pid)):
                self.unreviewed_sources.add(passage["source_key"])
            out.append(
                {
                    "source_key": passage["source_key"],
                    "source_snapshot_id": None,  # set once Person 3's DB stores snapshots
                    "url": source.get("url"),
                    "title": source.get("title"),
                    "locator": passage.get("locator"),
                    "snapshot_sha256": source.get("sha256"),
                    "checked_at": str(source["checked_at"]) if source.get("checked_at") is not None else None,
                    "excerpt": passage.get("excerpt"),
                }
            )
        return out


def _evaluate(predicate: Any, facts: Mapping[str, Any], schema: Mapping[str, Any], path: str) -> PredicateResult | None:
    """None means the rule itself is invalid (bad data in the release)."""
    try:
        return evaluate_predicate(predicate, facts, schema, path)
    except PredicateError:
        return None


def _status_fields(result: PredicateResult | None, citations: list, conflict_ids: list) -> dict:
    if result is None:
        return {"status": "needs_information", "status_reason": "rule_invalid", "missing_fact_keys": []}
    missing = list(result.missing_keys)
    if conflict_ids:
        return {"status": "needs_information", "status_reason": "source_conflict", "missing_fact_keys": missing}
    if not citations:
        return {"status": "needs_information", "status_reason": "insufficient_evidence", "missing_fact_keys": missing}
    return {"status": to_status(result), "status_reason": _REASON[result.value], "missing_fact_keys": missing}


def _base_result(dataset_mode: str, location, warnings: list[dict]) -> dict:
    city = location.jurisdiction.name if location.jurisdiction else None
    return {
        "dataset_mode": dataset_mode,
        "status": None,
        "notice": notice_for(city),
        "location": location.to_dict(),
        "release": None,
        "profile_key": None,
        "facts_used": {},
        "pathways": [],
        "requirements": [],
        "missing_fact_keys": [],
        "conflicts": [],
        "warnings": warnings,
    }


# --------------------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------------------


def lookup_permits(
    request: PermitLookupRequest | Mapping[str, Any],
    provider: ReleaseProvider,
    registry: Iterable[Jurisdiction] | Mapping[str, Jurisdiction],
) -> dict:
    """Stateless permit lookup. Raises LookupInputError (422) or LookupUnavailable (503)."""
    req = request if isinstance(request, PermitLookupRequest) else parse_permit_lookup_request(request)
    mode = "synthetic" if provider.demo_mode else "reviewed_public"
    location = resolve_location(req.location, registry, provider.coverage(), dataset_mode=mode)

    warnings: list[dict] = []
    if mode == "synthetic":
        warnings.append(_warning("synthetic_dataset",
                                 "This checklist comes from a synthetic test dataset, not the reviewed city sources."))
    warnings.extend(dict(w) for w in location.warnings)
    result = _base_result(mode, location, warnings)

    # 1. Only a selected area or a confirmed point gets a checklist.
    if not location.allows_checklist:
        result["status"] = (
            "rule_coverage_unavailable" if location.status == "outside_supported_area" else "location_unresolved"
        )
        return result

    city = location.jurisdiction

    def coverage_unavailable() -> dict:
        result["status"] = "rule_coverage_unavailable"
        warnings.append(_warning(
            "rule_coverage_unavailable",
            f"ClearPath has no curated rules for this project type in {city.name} yet. No checklist is shown, "
            "and rules for other housing types are never used instead.",
        ))
        return result

    # 2. Pick the rule profile. Never fall back to another project type.
    profiles = provider.configured_profiles(city.slug, req.project_type)
    if req.profile_key is not None:
        if req.profile_key not in profiles:
            return coverage_unavailable()
        chosen = req.profile_key
    elif not profiles:
        return coverage_unavailable()
    elif len(profiles) > 1:
        result["status"] = "needs_information"
        result["missing_fact_keys"] = ["profile_key"]
        warnings.append(_warning(
            "profile_key_required",
            "More than one rule profile matches. Choose one to see a checklist.",
            profile_keys=[p for p in profiles if p is not None],
        ))
        return result
    else:
        chosen = profiles[0]

    release = provider.get_active(city.slug, req.project_type, chosen)
    if release is None:
        raise LookupUnavailable("dataset_unavailable", "the rule dataset for this profile is not available right now")

    # 3. Facts: project_type comes from the request scope, never from a client fact.
    schema = dict(release.fact_schema)
    schema.setdefault("project_type", "string")
    client_facts = dict(req.facts)
    if "project_type" in client_facts:
        if client_facts["project_type"] != req.project_type:
            raise LookupInputError("project_type_conflict", "facts.project_type contradicts project_type", "facts")
        del client_facts["project_type"]
    facts = {**client_facts, "project_type": req.project_type}
    try:
        validate_facts(facts, schema)
    except PredicateError as error:
        raise LookupInputError(error.code, error.message, error.path) from None

    # 4. Conflicts: only pathway/requirement keys change a status; others pass through.
    rule_keys = {p.get("key") for p in release.pathways} | {r.get("key") for r in release.requirements}
    conflict_ids: dict[str, list[str]] = defaultdict(list)
    for c in release.conflicts:
        for key in c.rule_keys:
            if key in rule_keys:
                conflict_ids[key].append(c.id)

    evidence = _Evidence(release)
    invalid_rules: list[str] = []

    # 5. Pathways.
    pathway_results: dict[str, PredicateResult | None] = {}
    for i, pw in enumerate(release.pathways):
        key = pw.get("key")
        res = _evaluate(pw.get("applies_if"), facts, schema, f"pathways[{i}].applies_if")
        pathway_results[key] = res
        if res is None:
            invalid_rules.append(key)
        cites = evidence.citations(pw.get("citations"))
        result["pathways"].append(
            {"key": key, "title": pw.get("title"), **_status_fields(res, cites, conflict_ids.get(key, [])), "citations": cites}
        )

    # 6. Requirements: own rule AND (any of its pathways).
    for i, rq in enumerate(release.requirements):
        key = rq.get("key")
        own = _evaluate(rq.get("applies_if"), facts, schema, f"requirements[{i}].applies_if")
        linked = [pathway_results[k] for k in rq.get("pathways") or [] if k in pathway_results]
        if own is None or any(r is None for r in linked):
            res = None
            invalid_rules.append(key)
        else:
            res = _all([own, _any(linked)]) if linked else own
        cites = evidence.citations(rq.get("citations"))
        ids = conflict_ids.get(key, [])
        result["requirements"].append(
            {
                "key": key,
                "kind": rq.get("kind"),
                "title": rq.get("title"),
                "description": rq.get("description"),
                **_status_fields(res, cites, ids),
                "conflict_ids": list(ids),
                "required_for_preparation": bool(rq.get("required_for_preparation")),
                "citations": cites,
            }
        )

    # 7. Conflicts, passed through with stable ids.
    for c in release.conflicts:
        affects = any(k in rule_keys for k in c.rule_keys)
        result["conflicts"].append(
            {
                "id": c.id,
                "rule_keys": list(c.rule_keys),
                "source_keys": list(c.source_keys),
                "summary": c.summary,
                "effect": (
                    "Not a definitive answer until a person resolves the conflict."
                    if affects
                    else "Does not change any checklist item; shown for review."
                ),
            }
        )

    # 8. Warnings about the evidence itself.
    if release.test_only_unreviewed:
        warnings.append(_warning(
            "test_only_unreviewed_release",
            "TEST ONLY: unreviewed draft data was loaded as reviewed public data. Do not rely on this result.",
        ))
    if release.draft_gaps:
        warnings.append(_warning(
            "draft_manifest_defaults",
            "This rule dataset is a draft. Missing parts were filled with defaults "
            "(default ADU fact types, profile unknown).",
            gaps=list(release.draft_gaps),
        ))
    if evidence.unreviewed_sources:
        warnings.append(_warning(
            "unreviewed_extraction",
            "Some cited text has not been checked by a person yet. Items citing it may change.",
            source_keys=sorted(evidence.unreviewed_sources),
        ))
    if evidence.unresolved:
        warnings.append(_warning(
            "citation_unresolved",
            "Some citations could not be matched to a source passage. Those items are not shown as definite.",
        ))
    if invalid_rules:
        warnings.append(_warning(
            "rule_invalid",
            "Some rules in this dataset could not be read. Those items are shown as needing information.",
            rule_keys=sorted(k for k in invalid_rules if isinstance(k, str)),
        ))
    if release.milestones:
        warnings.append(_warning(
            "statutory_clock_unverified",
            "State completeness and decision time limits have not been checked against the statute text. "
            "No legal due date is calculated.",
        ))

    items = result["pathways"] + result["requirements"]
    result["status"] = "needs_information" if any(i["status"] == "needs_information" for i in items) else "checklist_ready"
    result["missing_fact_keys"] = sorted({k for i in items for k in i["missing_fact_keys"]})
    result["dataset_mode"] = release.dataset_mode
    result["release"] = {"id": release.release_id, "content_hash": release.content_hash, "dataset_mode": release.dataset_mode}
    result["profile_key"] = release.profile_key
    result["facts_used"] = client_facts
    return result
