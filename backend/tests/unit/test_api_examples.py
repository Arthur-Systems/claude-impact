"""Sanity checks for the frontend mock files in backend/tests/fixtures/api_examples/."""

import json
from pathlib import Path

import pytest

from clearpath.permits.predicates import PredicateResult, Tri, to_status

EXAMPLES = Path(__file__).resolve().parents[1] / "fixtures" / "api_examples"
FILES = sorted(EXAMPLES.glob("*.json"))
STATUSES = {to_status(PredicateResult(t)) for t in Tri}
ALLOWED_FACTS = {"adu_form", "existing_dwelling", "floor_area_sqft"}


def load(path):
    return json.loads(path.read_text())


def all_strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for k, v in node.items():
            yield k
            yield from all_strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from all_strings(v)


def test_expected_files_exist():
    names = {p.name for p in FILES}
    assert names == {
        "jurisdictions.json",
        "locations_resolve_selected_area.json",
        "locations_resolve_ambiguous.json",
        "permit_lookup_applies.json",
        "permit_lookup_needs_information.json",
        "permit_lookup_rule_coverage_unavailable.json",
        "sources_get.json",
        "error_envelope.json",
        # Person 5: projects and timeline
        "project_created.json",
        "requirement_patch.json",
        "timeline.json",
        "milestone_event_conflict_409.json",
    }


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_file_shape(path):
    doc = load(path)
    assert {"request", "status_code", "response"} <= doc.keys()
    assert isinstance(doc["status_code"], int)
    assert doc["response"]["example"] is True


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_no_real_urls(path):
    for s in all_strings(load(path)):
        assert "http://" not in s and "https://" not in s, s


@pytest.mark.parametrize("path", [p for p in FILES if load(p)["status_code"] < 400], ids=lambda p: p.name)
def test_success_files_are_marked_synthetic(path):
    response = load(path)["response"]
    assert response["dataset_mode"] == "synthetic"
    assert any(w["code"] == "example_data" for w in response["warnings"])


@pytest.mark.parametrize("path", sorted(EXAMPLES.glob("permit_lookup_*.json")), ids=lambda p: p.name)
def test_permit_lookup_statuses(path):
    doc = load(path)
    assert set(doc["request"]["body"]["facts"]) <= ALLOWED_FACTS
    response = doc["response"]
    assert response["notice"] == "Prototype. Not legal advice. Confirm with the City of Irvine or a professional."
    for item in response["pathways"] + response["requirements"]:
        assert item["status"] in STATUSES
        if item["status"] == "not_applicable":
            assert item["missing_fact_keys"] == [], item["key"]
    union = sorted({k for r in response["requirements"] for k in r["missing_fact_keys"]})
    assert response["missing_fact_keys"] == union
    cited = []
    for item in response["pathways"] + response["requirements"]:
        for c in item["citations"]:
            if c["source_key"] not in cited:
                cited.append(c["source_key"])
    assert [s["source_key"] for s in response["sources_used"]] == cited
    for s in response["sources_used"]:
        assert set(s) == {"source_key", "title", "url", "publisher", "checked_at", "verification_depth"}


def test_needs_information_example_shows_missing_floor_area():
    response = load(EXAMPLES / "permit_lookup_needs_information.json")["response"]
    assert response["status"] == "needs_information"
    assert any(
        r["status"] == "needs_information" and r["missing_fact_keys"] == ["floor_area_sqft"]
        for r in response["requirements"]
    )
    conflict_ids = {c["id"] for c in response["conflicts"]}
    assert conflict_ids
    for r in response["requirements"]:
        assert set(r["conflict_ids"]) <= conflict_ids


def test_error_envelope_shape():
    doc = load(EXAMPLES / "error_envelope.json")
    assert doc["status_code"] == 401
    response = doc["response"]
    assert set(response["error"]) == {"code", "message", "details"}
    assert "request_id" in response


# --------------------------------------------------------------------------------------
# The examples must match what the real service returns
# --------------------------------------------------------------------------------------

from clearpath.locations.schemas import Jurisdiction  # noqa: E402
from clearpath.permits.release import InMemoryReleaseProvider, ReleaseData  # noqa: E402
from clearpath.permits.service import lookup_permits  # noqa: E402

REGISTRY = [Jurisdiction("irvine-ca", "Irvine")]
LOOKUP_BODY = {
    "location": {"selected_area": {"jurisdiction": "irvine-ca"}},
    "project_type": "adu",
    "facts": {"adu_form": "detached", "existing_dwelling": True, "floor_area_sqft": 600},
}


def synthetic_provider():
    """SYNTHETIC manifest, not real Irvine rules. 500 is an arbitrary test value."""
    pid = "7f9c2b1e-0000-4000-8000-000000000001"
    manifest = {
        "kind": "synthetic",
        "jurisdiction": "irvine-ca",
        "project_type": "adu",
        "profile_key": "irvine-adu-detached-existing-dwelling",
        "fact_schema": {
            "adu_form": {"type": "enum", "values": ["detached", "attached"]},
            "existing_dwelling": {"type": "bool"},
            "floor_area_sqft": {"type": "number"},
        },
        "sources": [{"key": "SYN-SOURCE", "url": "<synthetic url>", "title": "SYNTHETIC", "checked_at": "2026-11-07",
                     "sha256": None, "verification_depth": "title_only"}],
        "passages": [{"id": pid, "source_key": "SYN-SOURCE", "locator": "#s1", "excerpt": "SYNTHETIC", "review_status": "reviewed"}],
        "pathways": [{"key": "syn_path", "title": "SYNTHETIC", "applies_if": {"eq": ["adu_form", "detached"]}, "citations": [pid]}],
        "requirements": [{"key": "syn_doc", "pathways": ["syn_path"], "kind": "document", "title": "SYNTHETIC",
                          "description": "SYNTHETIC", "applies_if": {"gt": ["floor_area_sqft", 500]},
                          "required_for_preparation": True, "citations": [pid]}],
        "milestones": [],
        "conflicts": [{"rule_keys": ["syn_doc"], "source_keys": ["SYN-SOURCE"], "summary": "SYNTHETIC"}],
    }
    release = ReleaseData.from_manifest(manifest, "00000000-0000-4000-8000-000000000001", "0" * 64, "synthetic")
    return InMemoryReleaseProvider([release], demo_mode=True)


def test_service_output_keys_match_applies_example():
    ex = load(EXAMPLES / "permit_lookup_applies.json")["response"]
    out = lookup_permits(LOOKUP_BODY, synthetic_provider(), REGISTRY)
    assert set(out) == set(ex) - {"example", "request_id"}
    assert set(out["location"]) == set(ex["location"])
    assert set(out["release"]) == set(ex["release"])
    assert set(out["pathways"][0]) == set(ex["pathways"][0])
    assert set(out["requirements"][0]) == set(ex["requirements"][0])
    assert set(out["requirements"][0]["citations"][0]) == set(ex["requirements"][0]["citations"][0])
    assert set(out["pathways"][0]["citations"][0]) == set(ex["pathways"][0]["citations"][0])
    assert set(out["sources_used"][0]) == set(ex["sources_used"][0])
    assert {"code", "message"} <= set(out["warnings"][0])


def test_service_conflict_keys_match_needs_information_example():
    ex = load(EXAMPLES / "permit_lookup_needs_information.json")["response"]
    out = lookup_permits(LOOKUP_BODY, synthetic_provider(), REGISTRY)
    assert set(out["conflicts"][0]) == set(ex["conflicts"][0])


def test_service_matches_rule_coverage_unavailable_example():
    doc = load(EXAMPLES / "permit_lookup_rule_coverage_unavailable.json")
    out = lookup_permits(doc["request"]["body"], synthetic_provider(), REGISTRY)
    expected = {k: v for k, v in doc["response"].items() if k not in ("example", "request_id")}
    expected["warnings"] = [w for w in expected["warnings"] if w["code"] != "example_data"]
    assert out == expected


def test_example_values_are_documented_in_readme():
    readme = (EXAMPLES / "README.md").read_text()
    used = set()
    for path in FILES:
        response = load(path)["response"]
        used |= {w["code"] for w in response.get("warnings", [])}
        if "error" in response:
            used.add(response["error"]["code"])
        if "location" in response:
            loc = response["location"]
            used |= {loc["status"], loc["mode"]} | ({loc["status_reason"]} if loc["status_reason"] else set())
        if path.name.startswith("permit_lookup_"):
            used.add(response["status"])
            for item in response["pathways"] + response["requirements"]:
                used |= {item["status"], item["status_reason"]}
    missing = sorted(v for v in used if f"`{v}`" not in readme)
    assert not missing, missing
