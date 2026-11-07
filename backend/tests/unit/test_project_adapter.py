"""ReleaseLookupProvider: Person 4's lookup behind Person 5's PermitLookupProvider Protocol.

Synthetic data comes from backend/tests/fixtures/lookup_synthetic/manifest.json (SYNTHETIC).
Real data is backend/data/irvine_adu/manifest.json, read-only. No network, no database.
"""

import json
import os
from dataclasses import fields
from pathlib import Path

import pytest

from clearpath.locations.schemas import CoverageEntry
from clearpath.locations.service import load_registry
from clearpath.permits.dev_server import load_real_provider, load_synthetic_provider
from clearpath.permits.project_adapter import ReleaseLookupProvider
from clearpath.permits.release import InMemoryReleaseProvider
from clearpath.projects.lookup import (
    ACCEPTED_LOCATION_STATES,
    FixtureLookupStub,
    LookupRequest,
    LookupResult,
    PermitLookupProvider,
    ScopeAssessment,
)

REPO = Path(__file__).resolve().parents[3]
REAL_MANIFEST = REPO / "backend" / "data" / "irvine_adu" / "manifest.json"
PROFILE = "irvine-adu-detached-existing-dwelling"
AREA = {"mode": "selected_area", "area_key": "irvine-ca-citywide", "resolution_status": "selected_area"}


def req(rule_facts=None, *, project_type="adu", jurisdiction="irvine-ca", location=None, profile_key=None,
        subtype="detached_adu_existing_dwelling"):
    return LookupRequest(
        project_type=project_type, subtype=subtype, jurisdiction=jurisdiction,
        location=dict(location or AREA),
        rule_facts={"adu_form": "detached", "existing_dwelling": True} if rule_facts is None else rule_facts,
        profile_key=profile_key,
    )


@pytest.fixture(scope="module")
def synthetic():
    return ReleaseLookupProvider(load_synthetic_provider(), load_registry())


@pytest.fixture(scope="module")
def real():
    if not REAL_MANIFEST.exists():
        pytest.skip("real Irvine manifest not present")
    return ReleaseLookupProvider(load_real_provider(REAL_MANIFEST), load_registry())


# --------------------------------------------------------------------------------------
# 1. Protocol
# --------------------------------------------------------------------------------------


def test_satisfies_person5_protocol(synthetic):
    provider: PermitLookupProvider = synthetic  # static shape
    assert callable(provider.assess_scope) and callable(provider.lookup)
    assert isinstance(synthetic.assess_scope(req()), ScopeAssessment)
    assert isinstance(synthetic.lookup(req()), LookupResult)
    proto = {n for n in vars(PermitLookupProvider) if not n.startswith("_")}
    assert proto <= {n for n in dir(synthetic) if not n.startswith("_")}


# --------------------------------------------------------------------------------------
# 2. Same field set as Person 5's FixtureLookupStub
# --------------------------------------------------------------------------------------

EXTRA = {
    "pathways": {"status_reason", "rule_status"},
    "requirements": {"status_reason"},
    "milestones": {"published_clock"},
    "citations": {"excerpt"},
}


def test_field_sets_match_fixture_stub(synthetic):
    stub = FixtureLookupStub().lookup(req())
    mine = synthetic.lookup(req())
    assert stub.status == mine.status == "ok"
    assert [f.name for f in fields(stub)] == [f.name for f in fields(mine)]
    assert set(stub.release) == set(mine.release)
    for name, extra in EXTRA.items():
        stub_keys = set(getattr(stub, name)[0])
        my_keys = set(getattr(mine, name)[0])
        assert stub_keys <= my_keys, (name, stub_keys - my_keys)
        assert my_keys - stub_keys == extra, (name, my_keys - stub_keys)
    assert {r["applicability"] for r in mine.requirements} <= {"applies", "needs_information", "not_applicable"}
    assert mine.location_status in ACCEPTED_LOCATION_STATES


def test_synthetic_c01_floor_area(synthetic):
    res = synthetic.lookup(req())
    reqs = {r["key"]: r for r in res.requirements}
    floor = reqs["synthetic_large_unit_document"]
    assert (floor["applicability"], floor["status_reason"], floor["missing_fact_keys"]) == (
        "needs_information", "missing_facts", ["floor_area_sqft"])
    assert reqs["synthetic_conflicted_checklist"]["status_reason"] == "source_conflict"
    assert res.missing_fact_keys == ["floor_area_sqft"]
    assert "synthetic_dataset" in [w["code"] for w in res.warnings]
    assert res.release["dataset_mode"] == "synthetic"


# --------------------------------------------------------------------------------------
# 3. Real Irvine manifest, C01 facts
# --------------------------------------------------------------------------------------


def test_real_irvine_c01(real):
    manifest = json.loads(REAL_MANIFEST.read_text())
    res = real.lookup(req())
    assert res.status == "ok"
    assert res.location_status == "selected_area"
    assert len(res.requirements) == 10
    cite_ids = {c["id"] for c in res.citations}
    assert len(cite_ids) == len(res.citations)
    for r in res.requirements:
        assert r["citation_ids"], r["key"]
        assert set(r["citation_ids"]) <= cite_ids, r["key"]
    # milestones: 6, template order, renamed keys, actor passed through
    assert [m["key"] for m in res.milestones] == [m["key"] for m in manifest["milestones"]]
    assert len(res.milestones) == 6
    for m, src in zip(res.milestones, manifest["milestones"]):
        assert m["predecessor_keys"] == src["predecessors"]
        assert m["requirement_keys"] == src["requirements"]
        assert m["actor"] == src["actor"] and m["actor"] in ("city", "applicant")
        assert set(m["citation_ids"]) <= cite_ids
        assert m["assumed_days"] == src.get("assumed_days")
        assert m["published_clock"] == src.get("published_clock")
        # never invent: these are only filled from fields of the same name
        assert m["city_service_target"] == src.get("city_service_target")
        assert m["statutory_clock"] == src.get("statutory_clock")
        if src.get("published_clock"):
            assert set(src["published_clock"]["citations"]) <= cite_ids
    # pathway: C01 meets its rule and no conflict names it
    pw = {p["key"]: p for p in res.pathways}["irvine_adu_standard"]
    assert pw["status"] == "applies"
    assert pw["status_reason"] == "facts_met"
    assert pw["rule_status"] == "applies"
    affidavit = {r["key"]: r for r in res.requirements}["signed-affidavit-esig"]
    assert (affidavit["applicability"], affidavit["status_reason"]) == ("needs_information", "source_conflict")
    # conflicts naming milestones pass through unchanged
    for out, src in zip(res.conflicts, manifest["conflicts"]):
        assert out["rule_keys"] == src["rule_keys"] and out["sources"] == src["source_keys"]
    assert ["fee_payment_readiness", "plan_review"] in [c["rule_keys"] for c in res.conflicts]
    assert pw["citation_ids"] and set(pw["citation_ids"]) <= cite_ids
    dsc = {r["key"]: r for r in res.requirements}["development-standards-checklist"]
    assert dsc["status_reason"] == "source_conflict"
    # every citation is a real passage with its real source URL
    urls = {s["key"]: s["url"] for s in manifest["sources"]}
    passages = {p["id"]: p for p in manifest["passages"]}
    for c in res.citations:
        assert c["id"] in passages and c["url"] == urls[c["source_key"]]
        assert c["excerpt"] == passages[c["id"]]["excerpt"]
    assert res.release["dataset_mode"] == "reviewed_public"
    assert res.release["profile_key"] == PROFILE
    assert all("sources" in c and c["sources"] == c["source_keys"] for c in res.conflicts)


def test_real_assess_scope_c01(real):
    a = real.assess_scope(req())
    assert a.coverage_reason == "activation_required"
    assert a.accepted_fact_keys == ["adu_form", "existing_dwelling", "floor_area_sqft"]


# --------------------------------------------------------------------------------------
# 4. Coverage, location, scope, availability
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("project_type", ["multifamily", "duplex", "other_housing"])
def test_non_adu_is_rule_coverage_unavailable(synthetic, project_type):
    r = req({}, project_type=project_type, subtype=None)
    assert synthetic.lookup(r).status == "rule_coverage_unavailable"
    assert synthetic.lookup(r).requirements == []
    a = synthetic.assess_scope(r)
    assert a.coverage_reason == "rule_coverage_unavailable"
    assert a.accepted_fact_keys is None


def test_assess_scope_reasons(synthetic):
    assert synthetic.assess_scope(req()).coverage_reason == "activation_required"
    missing = synthetic.assess_scope(req({"existing_dwelling": True}))
    assert missing.coverage_reason == "missing_information"
    assert "adu_form" in missing.missing_fact_keys
    contradicted = synthetic.assess_scope(req({"adu_form": "attached", "existing_dwelling": True}))
    assert contradicted.coverage_reason == "rule_coverage_unavailable"
    bad_area = synthetic.assess_scope(req(location={"mode": "selected_area", "area_key": "atlantis-citywide"}))
    assert bad_area.coverage_reason == "location_unresolved"
    point = synthetic.assess_scope(req(location={"mode": "point", "longitude": 0.0, "latitude": 0.0}))
    assert point.coverage_reason == "location_unresolved"


def test_lookup_status_mapping(synthetic):
    assert synthetic.lookup(req({"existing_dwelling": True})).status == "missing_information"
    assert synthetic.lookup(req({"adu_form": "attached", "existing_dwelling": True})).status == "rule_coverage_unavailable"
    loc = synthetic.lookup(req(location={"mode": "address", "address": {"number": "<n>", "street_name": "<s>"}}))
    assert loc.status == "location_unresolved" and loc.location_status == "unresolved"
    other_city = synthetic.lookup(req(jurisdiction="anaheim-ca", location={"mode": "selected_area", "area_key": "anaheim-ca-citywide"}))
    assert other_city.status == "rule_coverage_unavailable"


@pytest.mark.parametrize(
    "location, expected",
    [
        ({"mode": "selected_area", "area_key": "irvine-ca-citywide"}, "selected_area"),
        ({"mode": "selected_area", "area_key": "irvine-ca"}, "selected_area"),
        ({"mode": "fixture", "fixture_id": "synthetic-lot-1"}, "synthetic_fixture"),
        ({"mode": "selected_area", "area_key": "anaheim-ca-citywide"}, "unresolved"),  # contradicts jurisdiction
        ({"mode": "selected_area", "area_key": "nowhere"}, "unresolved"),
    ],
)
def test_location_mapping(synthetic, location, expected):
    assert synthetic.lookup(req(location=location)).location_status == expected


def test_jurisdiction_can_come_from_area_key(synthetic):
    assert synthetic.lookup(req(jurisdiction=None)).status == "ok"


def test_fixture_location_refused_on_public_data(real):
    res = real.lookup(req(location={"mode": "fixture", "fixture_id": "synthetic-lot-1"}))
    assert res.status == "location_unresolved"


def test_dataset_unavailable():
    p = InMemoryReleaseProvider((), demo_mode=True, configured=[CoverageEntry("irvine-ca", "adu", PROFILE)])
    adapter = ReleaseLookupProvider(p, load_registry())
    assert adapter.lookup(req()).status == "dataset_unavailable"
    a = adapter.assess_scope(req())
    assert a.accepted_fact_keys is None
    assert "dataset_unavailable" in [w["code"] for w in a.warnings]


def test_unknown_profile_key(synthetic):
    assert synthetic.lookup(req(profile_key="no-such-profile")).status == "rule_coverage_unavailable"
    assert synthetic.lookup(req(profile_key=PROFILE)).status == "ok"


def test_rule_fact_outside_release_enum_is_not_a_crash(real):
    # Person 5's RuleFacts allows adu_form "junior"; the real manifest's enum says "jadu".
    res = real.lookup(req({"adu_form": "junior", "existing_dwelling": True}))
    assert res.status == "missing_information"
    assert "invalid_rule_facts" in [w["code"] for w in res.warnings]
    assert "junior" not in json.dumps(res.warnings)


def test_never_invents_release_fields(synthetic):
    rel = synthetic.lookup(req()).release
    assert rel["published_at"] is None
    assert rel["schema_version"] == "1"
    assert rel["jurisdiction"] == "irvine-ca" and rel["project_type"] == "adu"


# --------------------------------------------------------------------------------------
# 5. Person 5's activation
# --------------------------------------------------------------------------------------


def test_person5_activate_project_needs_database():
    """activate_project writes PostgreSQL JSONB tables through a SQLAlchemy Session."""
    pytest.importorskip("sqlalchemy", reason="activate_project needs SQLAlchemy + PostgreSQL (not installed here)")
    if not os.environ.get("CLEARPATH_P5_TEST_DATABASE_URL"):
        pytest.skip("activate_project needs a PostgreSQL database; set CLEARPATH_P5_TEST_DATABASE_URL")
    pytest.skip("run Person 5's integration test (tests/integration/test_project_timeline.py) with the adapter")


def _person5_activation_gate(result: LookupResult, pathway_key: str, *, accept_conflicted_pathway: bool) -> str:
    """COPY of the checks in projects/service.py activate_project (lines ~280-307), no DB writes.

    Returns "activated" or the DomainConflict code it would raise. With
    accept_conflicted_pathway=True it applies the rule change proposed to Person 5.
    """
    if result.status == "dataset_unavailable":
        return "dataset_unavailable"
    if result.status != "ok":
        return result.status
    pathway = next((p for p in result.pathways if p["key"] == pathway_key), None)
    if pathway is None:
        return "pathway_not_available"
    ok = pathway["status"] == "applies"
    if accept_conflicted_pathway:
        ok = ok or (pathway.get("status_reason") == "source_conflict" and pathway.get("rule_status") == "applies")
    if not ok:
        return "missing_information"
    keys = [m["key"] for m in result.milestones]
    known = set(keys)
    if any(p not in known for m in result.milestones for p in m["predecessor_keys"]):
        return "release_graph_invalid"
    req_keys = {r["key"] for r in result.requirements}
    if any(k not in req_keys for m in result.milestones for k in m["requirement_keys"]):
        return "release_graph_invalid"
    import uuid

    uuid.UUID(result.release["id"])  # activate_project does uuid.UUID(release["id"])
    return "activated"


def test_activation_with_real_data_today_vs_proposed_rule(real):
    res = real.lookup(req())
    # No conflict names the pathway any more, so it applies and Person 5's CURRENT rule activates.
    assert _person5_activation_gate(res, "irvine_adu_standard", accept_conflicted_pathway=False) == "activated"
    # The proposed rule (also accept a conflicted pathway whose rule is met) still activates.
    assert _person5_activation_gate(res, "irvine_adu_standard", accept_conflicted_pathway=True) == "activated"


def test_proposed_rule_still_refuses_unmet_or_unknown_pathways(synthetic):
    unknown = synthetic.lookup(req({"existing_dwelling": True}))
    assert _person5_activation_gate(unknown, "synthetic_detached_standard", accept_conflicted_pathway=True) == "missing_information"
    synthetic_ok = synthetic.lookup(req())
    assert _person5_activation_gate(synthetic_ok, "synthetic_detached_standard", accept_conflicted_pathway=True) == "activated"
