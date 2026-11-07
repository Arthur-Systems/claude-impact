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
