"""The reviewed Irvine manifest runs through the public lookup path without overrides.

Reads backend/data/irvine_adu/manifest.json read-only. Asserts behavior (statuses,
citation provenance), not curated wording, so data edits by the curator do not break it.
"""

import copy
import json
from pathlib import Path

import pytest

from clearpath.ingestion.validation import validate_bundle
from clearpath.locations.schemas import Jurisdiction
from clearpath.permits.release import InMemoryReleaseProvider, ReleaseData
from clearpath.permits.service import lookup_permits

MANIFEST = Path(__file__).resolve().parents[2] / "data" / "irvine_adu" / "manifest.json"
REGISTRY = [Jurisdiction("irvine-ca", "Irvine"), Jurisdiction("anaheim-ca", "Anaheim")]


@pytest.fixture(scope="module")
def release():
    bundle = validate_bundle(MANIFEST)
    raw = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return raw, ReleaseData.from_manifest(raw, release_id="00000000-0000-4000-8000-0000000000ab",
                                          content_hash=bundle.content_hash, dataset_mode="reviewed_public")


def lookup(release, facts):
    _, data = release
    body = {"location": {"selected_area": {"jurisdiction": "irvine-ca"}}, "project_type": "adu", "facts": facts}
    return lookup_permits(body, InMemoryReleaseProvider([data], demo_mode=False), REGISTRY)


def test_reviewed_manifest_loads_as_public_without_override(release):
    raw, data = release
    before = copy.deepcopy(raw)
    assert data.dataset_mode == "reviewed_public" and not data.test_only_unreviewed and not data.draft_gaps
    assert data.profile_key == raw["profile_key"]
    assert raw == before


def test_c01_detached_with_existing_dwelling_cites_real_sources(release):
    raw, _ = release
    result = lookup(release, {"adu_form": "detached", "existing_dwelling": True})
    codes = [w["code"] for w in result["warnings"]]
    assert result["dataset_mode"] == "reviewed_public"
    assert "test_only_unreviewed_release" not in codes and "unreviewed_extraction" not in codes
    assert "synthetic_dataset" not in codes
    conflicted = {key for conflict in raw["conflicts"] for key in conflict.get("rule_keys", [])}
    assert [p["key"] for p in result["pathways"]] == ["irvine_adu_standard"]
    for item in result["pathways"] + result["requirements"]:
        expected = (("needs_information", "source_conflict") if item["key"] in conflicted
                    else ("applies", "facts_met"))
        assert (item["status"], item["status_reason"]) == expected, item["key"]
        assert item["missing_fact_keys"] == []
    urls = {s["url"] for s in raw["sources"]}
    excerpts = {p["excerpt"] for p in raw["passages"]}
    assert result["requirements"]
    for item in result["pathways"] + result["requirements"]:
        assert item["citations"], item["key"]
        for citation in item["citations"]:
            assert citation["url"] in urls and citation["excerpt"] in excerpts and citation["title"]
    assert len(result["conflicts"]) == len(raw["conflicts"])


def test_c01_unknown_dwelling_is_never_not_applicable(release):
    result = lookup(release, {"adu_form": "detached"})
    statuses = {p["key"]: (p["status"], p["missing_fact_keys"]) for p in result["pathways"]}
    assert statuses == {"irvine_adu_standard": ("needs_information", ["existing_dwelling"])}
    assert result["status"] == "needs_information"
    assert "existing_dwelling" in result["missing_fact_keys"]
