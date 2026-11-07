"""Permit lookup service (SPEC.md section 7). No network, no database.

Manifests built in this file are SYNTHETIC test data, not real Irvine rules. Numbers such
as 500 and 1200 are arbitrary test values. The one test that reads the real manifest from
backend/data/irvine_adu/manifest.json only reads it and never changes it.
"""

import copy
import json
from pathlib import Path

import pytest

from clearpath.locations.schemas import CoverageEntry, Jurisdiction
from clearpath.permits.predicates import Tri, evaluate_predicate
from clearpath.permits.release import (
    InMemoryReleaseProvider,
    ReleaseData,
    ReleaseLoadError,
    derive_draft_manifest_fallbacks,
)
from clearpath.permits.schemas import NOTICE, LookupInputError, LookupUnavailable
from clearpath.permits.service import lookup_permits

REPO = Path(__file__).resolve().parents[3]
EXAMPLES = REPO / "backend" / "tests" / "fixtures" / "api_examples"
REAL_MANIFEST = REPO / "backend" / "data" / "irvine_adu" / "manifest.json"

PROFILE = "irvine-adu-detached-existing-dwelling"
REGISTRY = [Jurisdiction("irvine-ca", "Irvine"), Jurisdiction("anaheim-ca", "Anaheim")]
P = {f"p{i}": f"7f9c2b1e-0000-4000-8000-00000000000{i}" for i in range(1, 7)}


# --------------------------------------------------------------------------------------
# SYNTHETIC manifest in Person 3's contract shape
# --------------------------------------------------------------------------------------


def synthetic_manifest(**overrides):
    m = {
        "schema_version": 1,
        "kind": "synthetic",
        "jurisdiction": "irvine-ca",
        "project_type": "adu",
        "profile_key": PROFILE,
        "curator_label": "SYNTHETIC TEST DATA, not real Irvine rules",
        "fact_schema": {
            "adu_form": {"type": "enum", "values": ["detached", "attached", "conversion", "jadu"]},
            "existing_dwelling": {"type": "bool"},
            "floor_area_sqft": {"type": "number"},
        },
        "sources": [
            {
                "key": "SYN-SOURCE",
                "title": "SYNTHETIC TEST SOURCE",
                "url": "https://example.org/synthetic",
                "publisher": "synthetic",
                "authority_type": "synthetic",
                "checked_at": "2026-11-07",
                "sha256": None,
                "verification_depth": "title_only",
                "terms_note": None,
            },
            {
                "key": "SYN-OTHER",
                "title": "SYNTHETIC OTHER SOURCE",
                "url": "https://example.org/synthetic-other",
                "publisher": "synthetic",
                "authority_type": "synthetic",
                "checked_at": "2026-11-07",
                "sha256": "a" * 64,
                "verification_depth": "full_text_read",
                "terms_note": None,
            },
        ],
        "passages": [
            {"id": P["p1"], "source_key": "SYN-SOURCE", "locator": "#s1", "excerpt": "SYNTHETIC 1", "review_status": "reviewed"},
            {"id": P["p2"], "source_key": "SYN-SOURCE", "locator": "#s2", "excerpt": "SYNTHETIC 2", "review_status": "reviewed"},
            {"id": P["p3"], "source_key": "SYN-OTHER", "locator": "#s3", "excerpt": "SYNTHETIC 3", "review_status": "reviewed"},
        ],
        "pathways": [
            {
                "key": "synthetic_detached",
                "title": "Synthetic detached pathway",
                "description": "SYNTHETIC",
                "applies_if": {"all": [{"eq": ["adu_form", "detached"]}, {"eq": ["existing_dwelling", True]}]},
                "citations": [P["p1"]],
            }
        ],
        "requirements": [
            req("synthetic_permit_a", "permit", {"eq": ["existing_dwelling", True]}, [P["p1"]]),
            req("synthetic_document_b", "document", {"gt": ["floor_area_sqft", 500]}, [P["p2"]]),
            req("synthetic_document_c", "document", {"lte": ["floor_area_sqft", 1200]}, [P["p2"], P["p3"]]),
            req("synthetic_review_d", "review", {"eq": ["existing_dwelling", True]}, [P["p3"]], prep=False),
        ],
        "milestones": [],
        "conflicts": [],
    }
    m.update(overrides)
    return m


def req(key, kind, applies_if, citations, prep=True, pathways=("synthetic_detached",)):
    return {
        "key": key,
        "pathways": list(pathways),
        "kind": kind,
        "title": f"SYNTHETIC {key}",
        "description": "SYNTHETIC test requirement, not a real form.",
        "applies_if": applies_if,
        "required_for_preparation": prep,
        "citations": list(citations),
    }


def release(manifest=None, mode="synthetic", rid="00000000-0000-4000-8000-000000000001"):
    return ReleaseData.from_manifest(manifest or synthetic_manifest(), release_id=rid, content_hash="0" * 64, dataset_mode=mode)


def provider(*releases, demo_mode=True, configured=()):
    return InMemoryReleaseProvider(releases or (release(),), demo_mode=demo_mode, configured=configured)


def body(facts=None, project_type="adu", jurisdiction="irvine-ca", **extra):
    b = {
        "location": {"selected_area": {"jurisdiction": jurisdiction}},
        "project_type": project_type,
        "facts": {"adu_form": "detached", "existing_dwelling": True} if facts is None else facts,
    }
    b.update(extra)
    return b


def by_key(result):
    return {r["key"]: r for r in result["requirements"]}


def warning_codes(result):
    return [w["code"] for w in result["warnings"]]


def example(name):
    return json.loads((EXAMPLES / name).read_text())


# --------------------------------------------------------------------------------------
# C01: detached ADU, existing dwelling, floor area unknown (SYNTHETIC data)
# --------------------------------------------------------------------------------------


def test_c01_floor_area_rules_need_information():
    result = lookup_permits(body(), provider(), REGISTRY)
    reqs = by_key(result)
    for key in ("synthetic_document_b", "synthetic_document_c"):
        assert reqs[key]["status"] == "needs_information"
        assert reqs[key]["status_reason"] == "missing_facts"
        assert reqs[key]["missing_fact_keys"] == ["floor_area_sqft"]
    assert reqs["synthetic_permit_a"]["status"] == "applies"
    assert reqs["synthetic_review_d"]["status"] == "applies"
    assert result["status"] == "needs_information"
    assert result["missing_fact_keys"] == ["floor_area_sqft"]
    assert result["pathways"][0]["status"] == "applies"
    for r in result["requirements"]:
        assert len(r["citations"]) >= 1
        if r["status"] == "not_applicable":
            assert r["missing_fact_keys"] == []
    assert result["notice"] == NOTICE
    assert "synthetic_dataset" in warning_codes(result)
    assert "selected_area_property_not_verified" in warning_codes(result)
    assert result["location"]["status"] == "selected_area"
    assert result["dataset_mode"] == "synthetic"
    assert result["release"] == {"id": "00000000-0000-4000-8000-000000000001", "content_hash": "0" * 64, "dataset_mode": "synthetic"}
    assert result["profile_key"] == PROFILE
    assert result["facts_used"] == {"adu_form": "detached", "existing_dwelling": True}


def test_all_facts_known_is_checklist_ready():
    facts = {"adu_form": "detached", "existing_dwelling": True, "floor_area_sqft": 600}
    result = lookup_permits(body(facts), provider(), REGISTRY)
    assert result["status"] == "checklist_ready"
    assert result["missing_fact_keys"] == []
    assert {r["status"] for r in result["requirements"]} == {"applies"}


def test_requirement_is_not_applicable_when_its_pathway_is_decided_false():
    result = lookup_permits(body({"adu_form": "attached", "existing_dwelling": True}), provider(), REGISTRY)
    assert result["pathways"][0]["status"] == "not_applicable"
    for r in result["requirements"]:
        assert r["status"] == "not_applicable"
        assert r["status_reason"] == "facts_not_met"
        assert r["missing_fact_keys"] == []


def test_missing_pathway_fact_propagates_to_requirements():
    result = lookup_permits(body({"existing_dwelling": True}), provider(), REGISTRY)
    assert result["pathways"][0]["missing_fact_keys"] == ["adu_form"]
    assert by_key(result)["synthetic_permit_a"]["missing_fact_keys"] == ["adu_form"]
    assert "not_applicable" not in {r["status"] for r in result["requirements"]}


def test_citations_resolve_from_release_only():
    result = lookup_permits(body(), provider(), REGISTRY)
    cite = by_key(result)["synthetic_document_c"]["citations"]
    assert [c["source_key"] for c in cite] == ["SYN-SOURCE", "SYN-OTHER"]
    assert cite[1] == {
        "source_key": "SYN-OTHER",
        "source_snapshot_id": None,
        "url": "https://example.org/synthetic-other",
        "title": "SYNTHETIC OTHER SOURCE",
        "locator": "#s3",
        "snapshot_sha256": "a" * 64,
        "checked_at": "2026-11-07",
        "excerpt": "SYNTHETIC 3",
    }
    urls = {c["url"] for r in result["requirements"] + result["pathways"] for c in r["citations"]}
    assert urls <= {"https://example.org/synthetic", "https://example.org/synthetic-other"}


# --------------------------------------------------------------------------------------
# Output shape matches the api_examples files
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["permit_lookup_applies.json", "permit_lookup_needs_information.json"])
def test_output_keys_match_examples(name):
    ex = example(name)["response"]
    result = lookup_permits(body(), provider(), REGISTRY)
    assert set(result) == set(ex) - {"example", "request_id"}
    assert set(result["requirements"][0]) == set(ex["requirements"][0])
    assert set(result["requirements"][0]["citations"][0]) == set(ex["requirements"][0]["citations"][0])
    assert set(result["pathways"][0]) == set(ex["pathways"][0])
    assert set(result["location"]) == set(ex["location"])
    for w in result["warnings"]:
        assert {"code", "message"} <= set(w)


def test_example_request_body_is_accepted():
    ex = example("permit_lookup_needs_information.json")
    result = lookup_permits(ex["request"]["body"], provider(), REGISTRY)
    assert result["status"] == "needs_information"


def test_conflict_keys_match_example():
    m = synthetic_manifest(conflicts=[{"rule_keys": ["synthetic_review_d"], "source_keys": ["SYN-SOURCE", "SYN-OTHER"], "summary": "SYNTHETIC conflict"}])
    result = lookup_permits(body(), provider(release(m)), REGISTRY)
    ex = example("permit_lookup_needs_information.json")["response"]
    assert set(result["conflicts"][0]) == set(ex["conflicts"][0])


# --------------------------------------------------------------------------------------
# Conflicts
# --------------------------------------------------------------------------------------


def test_conflicted_requirement_is_needs_information_source_conflict():
    m = synthetic_manifest(
        conflicts=[
            {"rule_keys": ["synthetic_permit_a"], "source_keys": ["SYN-SOURCE"], "summary": "SYNTHETIC conflict"},
            {"rule_keys": ["some_milestone", "free text (not entered)"], "source_keys": ["SYN-OTHER"], "summary": "SYNTHETIC other"},
        ],
        milestones=[{"key": "some_milestone"}],
    )
    facts = {"adu_form": "detached", "existing_dwelling": True, "floor_area_sqft": 600}
    result = lookup_permits(body(facts), provider(release(m)), REGISTRY)
    a = by_key(result)["synthetic_permit_a"]
    assert a["status"] == "needs_information"
    assert a["status_reason"] == "source_conflict"
    first, second = result["conflicts"]
    assert a["conflict_ids"] == [first["id"]]
    assert first["rule_keys"] == ["synthetic_permit_a"]
    assert first["source_keys"] == ["SYN-SOURCE"]
    # A conflict naming a milestone or free text passes through and changes no status.
    assert second["rule_keys"] == ["some_milestone", "free text (not entered)"]
    assert all(second["id"] not in r["conflict_ids"] for r in result["requirements"])
    assert by_key(result)["synthetic_document_b"]["status"] == "applies"
    assert result["status"] == "needs_information"


def test_conflict_never_yields_not_applicable():
    m = synthetic_manifest(conflicts=[{"rule_keys": ["synthetic_permit_a"], "source_keys": ["SYN-SOURCE"], "summary": "x"}])
    result = lookup_permits(body({"adu_form": "attached", "existing_dwelling": True}), provider(release(m)), REGISTRY)
    assert by_key(result)["synthetic_permit_a"]["status"] == "needs_information"


def test_conflicted_pathway_is_needs_information():
    m = synthetic_manifest(conflicts=[{"rule_keys": ["synthetic_detached"], "source_keys": ["SYN-SOURCE"], "summary": "x"}])
    result = lookup_permits(body(), provider(release(m)), REGISTRY)
    assert result["pathways"][0]["status"] == "needs_information"
    assert result["pathways"][0]["status_reason"] == "source_conflict"


def test_conflict_conflict_ids_are_stable():
    m = synthetic_manifest(conflicts=[{"rule_keys": ["synthetic_permit_a"], "source_keys": ["SYN-SOURCE"], "summary": "x"}])
    a = lookup_permits(body(), provider(release(m)), REGISTRY)["conflicts"][0]["id"]
    b = lookup_permits(body(), provider(release(m)), REGISTRY)["conflicts"][0]["id"]
    assert a == b


# --------------------------------------------------------------------------------------
# Coverage, profiles, availability
# --------------------------------------------------------------------------------------


def test_multifamily_has_no_coverage_and_never_falls_back_to_adu():
    result = lookup_permits(body({}, project_type="multifamily"), provider(), REGISTRY)
    assert result["status"] == "rule_coverage_unavailable"
    assert result["pathways"] == [] and result["requirements"] == []
    assert result["release"] is None and result["profile_key"] is None
    assert "rule_coverage_unavailable" in warning_codes(result)
    assert result["notice"] == NOTICE


def test_registry_city_without_coverage_returns_no_checklist():
    result = lookup_permits(body(jurisdiction="anaheim-ca"), provider(), REGISTRY)
    assert result["location"]["status"] == "outside_supported_area"
    assert result["status"] == "rule_coverage_unavailable"
    assert result["requirements"] == []


def test_unknown_slug_is_location_unresolved():
    result = lookup_permits(body(jurisdiction="atlantis-ca"), provider(), REGISTRY)
    assert result["location"]["status"] == "unresolved"
    assert result["status"] == "location_unresolved"
    assert result["requirements"] == [] and result["pathways"] == []


def test_point_mode_gives_no_property_checklist():
    b = body()
    b["location"] = {"point": {"lat": 0.0, "lon": 0.0}}
    result = lookup_permits(b, provider(), REGISTRY)
    assert result["status"] == "location_unresolved"
    assert result["requirements"] == []


def test_configured_profile_without_release_raises_dataset_unavailable():
    p = InMemoryReleaseProvider((), demo_mode=True, configured=[CoverageEntry("irvine-ca", "adu", PROFILE)])
    with pytest.raises(LookupUnavailable) as excinfo:
        lookup_permits(body(), p, REGISTRY)
    assert excinfo.value.code == "dataset_unavailable"
    assert excinfo.value.http_status == 503


def test_several_profiles_without_profile_key_need_information():
    second = synthetic_manifest(profile_key="irvine-adu-other-synthetic")
    p = provider(release(), release(second, rid="00000000-0000-4000-8000-000000000002"))
    result = lookup_permits(body(), p, REGISTRY)
    assert result["status"] == "needs_information"
    assert result["missing_fact_keys"] == ["profile_key"]
    assert result["requirements"] == []
    w = next(w for w in result["warnings"] if w["code"] == "profile_key_required")
    assert w["profile_keys"] == ["irvine-adu-detached-existing-dwelling", "irvine-adu-other-synthetic"]

    chosen = lookup_permits(body(profile_key="irvine-adu-other-synthetic"), p, REGISTRY)
    assert chosen["profile_key"] == "irvine-adu-other-synthetic"
    assert chosen["release"]["id"] == "00000000-0000-4000-8000-000000000002"


def test_unknown_profile_key_is_rule_coverage_unavailable():
    result = lookup_permits(body(profile_key="no-such-profile"), provider(), REGISTRY)
    assert result["status"] == "rule_coverage_unavailable"
    assert result["requirements"] == []


def test_demo_and_public_releases_cannot_mix():
    with pytest.raises(ValueError):
        InMemoryReleaseProvider([release()], demo_mode=False)
    with pytest.raises(ValueError):
        InMemoryReleaseProvider([release(synthetic_manifest(kind="reviewed_public"), mode="reviewed_public")], demo_mode=True)


def test_synthetic_manifest_cannot_be_loaded_as_public():
    with pytest.raises(ReleaseLoadError):
        release(synthetic_manifest(), mode="reviewed_public")


def test_reviewed_public_release_has_no_synthetic_warning():
    p = provider(release(synthetic_manifest(kind="reviewed_public"), mode="reviewed_public"), demo_mode=False)
    result = lookup_permits(body(), p, REGISTRY)
    assert result["dataset_mode"] == "reviewed_public"
    assert "synthetic_dataset" not in warning_codes(result)


# --------------------------------------------------------------------------------------
# project_type merge and input validation
# --------------------------------------------------------------------------------------


def test_project_type_is_merged_into_facts_and_schema():
    m = synthetic_manifest()
    m["requirements"].append(req("synthetic_typed", "document", {"eq": ["project_type", "adu"]}, [P["p1"]]))
    result = lookup_permits(body(), provider(release(m)), REGISTRY)
    assert by_key(result)["synthetic_typed"]["status"] == "applies"
    assert "project_type" not in result["facts_used"]


def test_client_fact_cannot_override_project_type():
    with pytest.raises(LookupInputError) as excinfo:
        lookup_permits(body({"adu_form": "detached", "project_type": "multifamily"}), provider(), REGISTRY)
    assert excinfo.value.code == "project_type_conflict"
    same = lookup_permits(body({"adu_form": "detached", "project_type": "adu"}), provider(), REGISTRY)
    assert "project_type" not in same["facts_used"]


@pytest.mark.parametrize(
    "facts, code",
    [
        ({"adu_form": "treehouse-SECRET"}, "enum_value_not_allowed"),
        ({"floor_area_sqft": "SECRET"}, "invalid_fact_value"),
        ({"lot_size_SECRET": 5}, "unknown_fact"),
        ({"existing_dwelling": 1}, "invalid_fact_value"),
    ],
)
def test_invalid_facts_raise_input_error_without_values(facts, code):
    with pytest.raises(LookupInputError) as excinfo:
        lookup_permits(body(facts), provider(), REGISTRY)
    assert excinfo.value.code == code
    assert excinfo.value.http_status == 422
    assert "SECRET" not in str(excinfo.value)


@pytest.mark.parametrize(
    "bad",
    [
        {"extra_field": 1},
        {"project_type": "castle"},
        {"facts": ["adu_form"]},
        {"profile_key": 5},
        {"location": {}},
    ],
)
def test_invalid_request_raises_input_error(bad):
    b = body()
    b.update(bad)
    with pytest.raises(LookupInputError):
        lookup_permits(b, provider(), REGISTRY)


def test_missing_required_request_fields():
    with pytest.raises(LookupInputError):
        lookup_permits({"project_type": "adu"}, provider(), REGISTRY)
    with pytest.raises(LookupInputError):
        lookup_permits({"location": {"area": {"jurisdiction": "irvine-ca"}}}, provider(), REGISTRY)


def test_input_dict_is_not_mutated():
    b = body()
    snapshot = copy.deepcopy(b)
    lookup_permits(b, provider(), REGISTRY)
    assert b == snapshot


# --------------------------------------------------------------------------------------
# Evidence quality warnings
# --------------------------------------------------------------------------------------


def test_unreviewed_passage_warns_with_source_keys():
    m = synthetic_manifest()
    m["passages"][2]["review_status"] = "needs_review"
    result = lookup_permits(body(), provider(release(m)), REGISTRY)
    w = next(w for w in result["warnings"] if w["code"] == "unreviewed_extraction")
    assert w["source_keys"] == ["SYN-OTHER"]


def test_all_reviewed_has_no_unreviewed_warning():
    assert "unreviewed_extraction" not in warning_codes(lookup_permits(body(), provider(), REGISTRY))


def test_passage_without_review_status_counts_as_unreviewed():
    m = synthetic_manifest()
    del m["passages"][0]["review_status"]
    result = lookup_permits(body(), provider(release(m)), REGISTRY)
    w = next(w for w in result["warnings"] if w["code"] == "unreviewed_extraction")
    assert w["source_keys"] == ["SYN-SOURCE"]


def test_requirement_without_resolvable_citation_is_not_definitive():
    m = synthetic_manifest()
    m["requirements"][0]["citations"] = ["7f9c2b1e-0000-4000-8000-0000000000ff"]
    result = lookup_permits(body(), provider(release(m)), REGISTRY)
    a = by_key(result)["synthetic_permit_a"]
    assert a["status"] == "needs_information"
    assert a["status_reason"] == "insufficient_evidence"
    assert a["citations"] == []
    assert "citation_unresolved" in warning_codes(result)


def test_invalid_rule_in_release_does_not_crash():
    m = synthetic_manifest()
    m["requirements"][0]["applies_if"] = {"eq": ["not_a_fact", True]}
    result = lookup_permits(body(), provider(release(m)), REGISTRY)
    a = by_key(result)["synthetic_permit_a"]
    assert a["status"] == "needs_information"
    assert a["status_reason"] == "rule_invalid"
    assert "rule_invalid" in warning_codes(result)


# --------------------------------------------------------------------------------------
# Draft manifests: Person 2's real-data shape (no fact_schema, no profile_key)
# --------------------------------------------------------------------------------------


def real_shape_manifest():
    """Inline copy of the SHAPE of backend/data/irvine_adu/manifest.json. Values are SYNTHETIC."""
    return {
        "schema_version": 1,
        "jurisdiction": "irvine-ca",
        "project_type": "adu",
        "subtype": "detached_adu_existing_dwelling",
        "_status": "SYNTHETIC draft",
        "sources": [
            {"key": "SYN-A", "url": "https://example.org/a", "title": "SYNTHETIC A", "publisher": "x",
             "authority_type": "x", "checked_at": "2026-11-07", "sha256": None,
             "verification_depth": "full_text_read", "terms_note": "unknown", "_review_note": "x"},
        ],
        "passages": [
            {"id": P["p1"], "source_key": "SYN-A", "locator": "item 1", "excerpt": "SYNTHETIC excerpt", "_review_note": "x"},
        ],
        "pathways": [
            {"key": "syn_standard", "title": "SYNTHETIC",
             "applies_if": {"all": [{"eq": ["project_type", "adu"]}, {"eq": ["adu_form", "detached"]}, {"eq": ["existing_dwelling", True]}]},
             "citations": [P["p1"]]},
        ],
        "requirements": [
            {"key": "syn-doc", "pathways": ["syn_standard"], "kind": "document", "title": "SYNTHETIC",
             "description": "SYNTHETIC", "applies_if": {"eq": ["project_type", "adu"]},
             "required_for_preparation": True, "citations": [P["p1"]]},
            {"key": "syn-doc-2", "pathways": ["syn_standard"], "kind": "document", "title": "SYNTHETIC",
             "description": "SYNTHETIC", "applies_if": {"eq": ["project_type", "adu"]},
             "required_for_preparation": True, "citations": [P["p1"]]},
        ],
        "milestones": [{"key": "syn_milestone", "title": "SYNTHETIC", "predecessors": [], "requirements": []}],
        "conflicts": [
            {"rule_keys": ["syn-doc-2"], "sources": ["SYN-A"], "summary": "SYNTHETIC"},
            {"rule_keys": ["syn_milestone"], "sources": ["SYN-A"], "summary": "SYNTHETIC"},
            {"rule_keys": ["not entered (free text)"], "sources": ["SYN-A"], "summary": "SYNTHETIC"},
        ],
        "_gaps": [{"item": "SYNTHETIC", "note": "SYNTHETIC"}],
    }


def test_draft_fallback_helper_derives_adu_schema_and_unknown_profile():
    fallbacks = derive_draft_manifest_fallbacks(real_shape_manifest())
    assert fallbacks.profile_key is None
    assert set(fallbacks.fact_schema) == {"adu_form", "existing_dwelling", "floor_area_sqft"}
    assert set(fallbacks.gaps) == {"fact_schema_missing", "profile_key_missing"}


def test_draft_fallback_not_used_when_manifest_is_complete():
    assert derive_draft_manifest_fallbacks(synthetic_manifest()).gaps == ()


def test_draft_fallback_refuses_non_adu_without_fact_schema():
    m = real_shape_manifest()
    m["project_type"] = "multifamily"
    with pytest.raises(ReleaseLoadError):
        ReleaseData.from_manifest(m, release_id="r", content_hash="0" * 64, dataset_mode="synthetic")


# ---- reviewed_public is earned, never assumed ----------------------------------------


def public_manifest():
    """SYNTHETIC content that passes every reviewed_public check."""
    return synthetic_manifest(kind="reviewed_public")


def test_complete_reviewed_manifest_can_be_public():
    r = release(public_manifest(), mode="reviewed_public")
    assert r.dataset_mode == "reviewed_public"
    assert r.test_only_unreviewed is False


@pytest.mark.parametrize(
    "make, reason",
    [
        (lambda: real_shape_manifest(), "kind"),
        (lambda: {k: v for k, v in public_manifest().items() if k != "kind"}, "kind"),
        (lambda: {**public_manifest(), "fact_schema": None}, "draft"),
        (lambda: {k: v for k, v in public_manifest().items() if k != "profile_key"}, "draft"),
    ],
    ids=["draft-real-shape", "no-kind", "no-fact-schema", "no-profile-key"],
)
def test_unreviewed_or_draft_manifest_cannot_be_public(make, reason):
    with pytest.raises(ReleaseLoadError) as excinfo:
        release(make(), mode="reviewed_public")
    assert reason in str(excinfo.value)


@pytest.mark.parametrize("review_status", ["needs_review", "failed", None])
def test_any_unreviewed_passage_blocks_public(review_status):
    m = public_manifest()
    if review_status is None:
        del m["passages"][1]["review_status"]
    else:
        m["passages"][1]["review_status"] = review_status
    with pytest.raises(ReleaseLoadError) as excinfo:
        release(m, mode="reviewed_public")
    assert "unreviewed" in str(excinfo.value)


def test_test_only_override_is_flagged_in_every_lookup():
    r = ReleaseData.from_manifest(real_shape_manifest(), release_id="r", content_hash="0" * 64,
                                  dataset_mode="reviewed_public", test_only_allow_unreviewed=True)
    assert r.test_only_unreviewed is True
    result = lookup_permits(body(), InMemoryReleaseProvider([r], demo_mode=False), REGISTRY)
    assert "test_only_unreviewed_release" in warning_codes(result)


def test_override_is_off_by_default_and_not_needed_for_synthetic():
    r = release(real_shape_manifest(), mode="synthetic")
    assert r.test_only_unreviewed is False
    assert "test_only_unreviewed_release" not in warning_codes(lookup_permits(body(), provider(r), REGISTRY))


def test_real_shape_manifest_lookup():
    r = release(real_shape_manifest(), mode="synthetic")
    assert r.profile_key is None
    result = lookup_permits(body(), provider(r), REGISTRY)
    assert result["pathways"][0]["status"] == "applies"
    reqs = by_key(result)
    assert reqs["syn-doc"]["status"] == "applies"
    assert reqs["syn-doc-2"]["status"] == "needs_information"
    assert reqs["syn-doc-2"]["status_reason"] == "source_conflict"
    assert [c["source_keys"] for c in result["conflicts"]] == [["SYN-A"]] * 3
    assert result["profile_key"] is None
    codes = warning_codes(result)
    assert "draft_manifest_defaults" in codes
    assert "unreviewed_extraction" in codes
    # An explicit profile_key cannot match a release whose profile is unknown.
    assert lookup_permits(body(profile_key=PROFILE), provider(r), REGISTRY)["status"] == "rule_coverage_unavailable"


# --------------------------------------------------------------------------------------
# The real manifest on main (read-only)
# --------------------------------------------------------------------------------------


@pytest.mark.skipif(not REAL_MANIFEST.exists(), reason="real Irvine manifest not present")
def test_real_irvine_manifest_c01_reviewed_public():
    # Person 2's manifest now passes every reviewed_public check (kind, profile_key,
    # fact_schema, all passages reviewed), so it loads as public with NO override.
    # Refusal of unreviewed data is covered by test_unreviewed_or_draft_manifest_cannot_be_public.
    manifest = json.loads(REAL_MANIFEST.read_text())
    before = copy.deepcopy(manifest)
    r = ReleaseData.from_manifest(manifest, release_id="00000000-0000-4000-8000-0000000000aa",
                                  content_hash="0" * 64, dataset_mode="reviewed_public")
    assert r.test_only_unreviewed is False
    assert r.draft_gaps == ()
    assert r.profile_key == PROFILE
    p = InMemoryReleaseProvider([r], demo_mode=False)
    result = lookup_permits(body({"adu_form": "detached", "existing_dwelling": True}), p, REGISTRY)
    codes = warning_codes(result)
    for absent in ("test_only_unreviewed_release", "synthetic_dataset", "draft_manifest_defaults", "unreviewed_extraction"):
        assert absent not in codes, absent
    assert result["dataset_mode"] == "reviewed_public"
    assert result["profile_key"] == PROFILE

    # C01 meets the pathway's rule and no conflict names the pathway, so it applies.
    pathway_row = next(pw for pw in manifest["pathways"] if pw["key"] == "irvine_adu_standard")
    c01_facts = {"project_type": "adu", "adu_form": "detached", "existing_dwelling": True}
    assert evaluate_predicate(pathway_row["applies_if"], c01_facts, r.fact_schema).value is Tri.TRUE
    pathways = {pw["key"]: pw for pw in result["pathways"]}
    pw = pathways["irvine_adu_standard"]
    assert pw["status"] == "applies"
    assert pw["status_reason"] == "facts_met"
    assert pw["missing_fact_keys"] == []
    assert not any("irvine_adu_standard" in c["rule_keys"] for c in result["conflicts"])
    # Conflicts naming only milestones pass through unchanged and change no checklist item.
    requirement_keys = {r_["key"] for r_ in result["requirements"]}
    milestone_keys = {m["key"] for m in manifest["milestones"]}
    for out, src in zip(result["conflicts"], manifest["conflicts"]):
        assert out["rule_keys"] == src["rule_keys"]
        assert out["source_keys"] == src["source_keys"]
        assert out["summary"] == src["summary"]
        if set(src["rule_keys"]) <= milestone_keys:
            assert out["effect"].startswith("Does not change any checklist item")
            assert all(out["id"] not in r_["conflict_ids"] for r_ in result["requirements"])
            assert not set(src["rule_keys"]) & requirement_keys
    assert any(set(c["rule_keys"]) <= milestone_keys for c in manifest["conflicts"])
    statuses = {r_["key"]: r_["status"] for r_ in result["requirements"]}
    assert all(v == "applies" for k, v in statuses.items() if k not in {"development-standards-checklist", "signed-affidavit-esig"}), statuses
    affidavit = by_key(result)["signed-affidavit-esig"]
    assert (affidavit["status"], affidavit["status_reason"]) == ("needs_information", "source_conflict")
    assert affidavit["conflict_ids"]
    assert result["requirements"]
    for r_ in result["requirements"]:
        assert len(r_["citations"]) >= 1, r_["key"]
        if r_["status"] == "not_applicable":
            assert r_["missing_fact_keys"] == []
    dsc = by_key(result)["development-standards-checklist"]
    assert dsc["status"] == "needs_information"
    assert dsc["status_reason"] == "source_conflict"
    assert len(result["conflicts"]) == len(manifest["conflicts"])
    source_urls = {s["url"] for s in manifest["sources"]}
    for item in result["requirements"] + result["pathways"]:
        for c in item["citations"]:
            assert c["url"] in source_urls
    assert manifest == before
