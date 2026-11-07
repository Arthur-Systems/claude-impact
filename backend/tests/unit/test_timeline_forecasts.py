"""Timeline calculation and ASSUMPTION forecast (A9). Every test passes as_of explicitly."""

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from clearpath.timelines.calculate import build_timeline, document_readiness, forecast, progress
from clearpath.timelines.model import AssumedDays, DomainConflict, MilestoneDef, MilestoneState, RequirementState, SourceConflict

EXAMPLES = Path(__file__).resolve().parents[1] / "fixtures" / "api_examples"


def utc(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def m(key, pos, preds=(), lo=None, hi=None, reqs=(), actor=None):
    return MilestoneDef(key, key.title(), pos, tuple(preds), tuple(reqs), actor, AssumedDays(lo, hi))


def st(defs, **kw):
    out = {d.key: MilestoneState(d.key) for d in defs}
    for k, v in kw.items():
        out[k] = MilestoneState(k, *v)
    return out


def test_progress_one_decimal_and_empty_graph_null():
    defs = [m("a", 1), m("b", 2), m("c", 3)]
    s = st(defs, a=("completed", utc("2026-11-01T17:00Z"), utc("2026-11-02T17:00Z")))
    assert progress(s) == {"completed": 1, "total": 3, "percent": 33.3}
    s["b"] = MilestoneState("b", "completed", utc("2026-11-02T17:00Z"), utc("2026-11-02T18:00Z"))
    assert progress(s)["percent"] == 66.7
    assert progress({}) is None


def test_document_readiness_keeps_unknowns_pending_and_provisional():
    r = {
        "a": RequirementState("a", "applies", "ready"),
        "b": RequirementState("b", "applies", "in_progress"),
        "c": RequirementState("c", "needs_information", "ready", missing_fact_keys=("floor_area_sqft",)),
        "d": RequirementState("d", "not_applicable", "not_started"),
    }
    assert document_readiness(r) == {"ready": 1, "applicable": 2, "needs_information": 1, "denominator": 3,
                                     "percent": 33.3, "provisional": True, "unknown_count": 1}
    assert document_readiness({})["percent"] is None


def test_parallel_paths_take_max_not_sum():
    defs = [m("a", 1, (), 2, 4), m("b", 2, ("a",), 10, 20), m("c", 3, ("a",), 1, 30), m("d", 4, ("b", "c"), 1, 1)]
    proj, per = forecast(defs, st(defs), date(2026, 1, 1))
    # a: Jan 3..5; b: Jan 13..25; c: Jan 4..Feb 4; d: max(13,4)+1=Jan 14 .. max(25 Jan, 4 Feb)+1 = Feb 5
    assert per["d"] == {"earliest": "2026-01-14", "latest": "2026-02-05", "label": "ASSUMPTION"}
    assert proj["finish_range"] == {"earliest": "2026-01-14", "latest": "2026-02-05"}
    assert proj["label"] == "ASSUMPTION" and proj["status"] == "available"


def test_unknown_required_duration_makes_forecast_null():
    defs = [m("a", 1, (), 2, 4), m("b", 2, ("a",), None, None), m("c", 3, ("b",), 1, 2)]
    proj, per = forecast(defs, st(defs), date(2026, 1, 1))
    assert proj["finish_range"] is None
    assert proj["status"] == "missing_stage_estimates"
    assert proj["missing_stage_estimates"] == ["b"]
    assert per["b"] is None and per["c"] is None and per["a"] is not None


def test_completed_stage_with_unknown_duration_does_not_block_forecast():
    defs = [m("a", 1, (), None, None), m("b", 2, ("a",), 3, 5)]
    s = st(defs, a=("completed", utc("2025-12-20T18:00Z"), utc("2025-12-30T18:00Z")))
    proj, per = forecast(defs, s, date(2026, 1, 1))
    assert proj["finish_range"] == {"earliest": "2026-01-04", "latest": "2026-01-06"}


def test_in_progress_elapsed_days_clamp_to_zero():
    defs = [m("a", 1, (), 5, 10)]
    s = st(defs, a=("in_progress", utc("2025-12-25T18:00Z"), None))  # 7 days elapsed at Jan 1
    proj, _ = forecast(defs, s, date(2026, 1, 1))
    assert proj["finish_range"] == {"earliest": "2026-01-01", "latest": "2026-01-04"}


def test_as_of_is_reproducible_and_must_not_precede_actual_dates():
    defs = [m("a", 1, (), 5, 10), m("b", 2, ("a",), 1, 2)]
    s = st(defs, a=("in_progress", utc("2026-01-03T18:00Z"), None))
    first = build_timeline(defs, s, {}, [], date(2026, 1, 5))
    assert first == build_timeline(defs, s, {}, [], date(2026, 1, 5))
    with pytest.raises(DomainConflict) as e:
        build_timeline(defs, s, {}, [], date(2026, 1, 2))
    assert e.value.code == "as_of_before_latest_event" and e.value.http_status == 422


def test_civil_dates_use_los_angeles():
    # 2026-01-03T05:00Z is still Jan 2 in Irvine.
    defs = [m("a", 1, (), 0, 0)]
    s = st(defs, a=("in_progress", utc("2026-01-03T05:00Z"), None))
    build_timeline(defs, s, {}, [], date(2026, 1, 2))  # must not raise


def test_bottleneck_codes():
    defs = [
        m("prep", 1, (), 1, 2, reqs=("doc", "unknown_doc")),
        m("review", 2, (), 1, 3, actor="city"),
    ]
    r = {"doc": RequirementState("doc", "applies", "in_progress", title="Doc"),
         "unknown_doc": RequirementState("unknown_doc", "needs_information", missing_fact_keys=("floor_area_sqft",))}
    s = st(defs, review=("in_progress", utc("2026-01-01T18:00Z"), None))
    out = build_timeline(defs, s, r, [SourceConflict(("doc",), ("IRV-ADU", "HCD"), "renumbered statute")], date(2026, 1, 10))
    codes = [(b["code"], b["milestone_key"]) for b in out["bottlenecks"]]
    assert codes == [("missing_information", "prep"), ("missing_documents", "prep"),
                     ("awaiting_city", "review"), ("estimate_exceeded", "review"), ("source_conflict", None)]
    assert out["bottlenecks"][0]["missing_fact_keys"] == ["floor_area_sqft"]
    assert "not a finding" in out["bottlenecks"][3]["message"]
    assert out["next_actions"] == [{"milestone_key": "review", "event_kind": "complete", "title": "Mark review complete", "citation_ids": []}]


def test_matches_timeline_api_example():
    """Rebuild the committed timeline.json example from its own inputs and compare computed fields."""
    tl = json.loads((EXAMPLES / "timeline.json").read_text())["response"]
    checklist = json.loads((EXAMPLES / "requirement_patch.json").read_text())["response"]["project"]["checklist"]
    city = {"completeness_review", "plan_review", "permit_issuance"}
    defs = [
        MilestoneDef(x["key"], x["title"], i, tuple(x["predecessor_keys"]), tuple(x["requirement_keys"]),
                     "city" if x["key"] in city else "applicant",
                     AssumedDays(x["timing"]["assumption"]["min_days"], x["timing"]["assumption"]["max_days"]),
                     tuple(x["citation_ids"]))
        for i, x in enumerate(tl["milestones"])
    ]
    states = {x["key"]: MilestoneState(x["key"], x["state"], x["started_at"] and utc(x["started_at"]),
                                       x["completed_at"] and utc(x["completed_at"])) for x in tl["milestones"]}
    reqs = {c["key"]: RequirementState(c["key"], c["applicability"], c["status"], c["required_for_preparation"],
                                       tuple(c["missing_fact_keys"]), c["title"], c["kind"]) for c in checklist}
    out = build_timeline(defs, states, reqs, [], date.fromisoformat(tl["as_of"]))
    assert out["progress"] == tl["progress"]
    assert out["document_readiness"] == tl["document_readiness"]
    assert [(a["milestone_key"], a["event_kind"]) for a in out["next_actions"]] == \
        [(a["milestone_key"], a["event_kind"]) for a in tl["next_actions"]]
    strip = lambda b: {k: v for k, v in b.items() if k != "message"}
    assert [strip(b) for b in out["bottlenecks"]] == [strip(b) for b in tl["bottlenecks"]]
    assert out["forecast"]["finish_range"] == tl["forecast"]["finish_range"]
    for got, want in zip(out["milestones"], tl["milestones"]):
        assert {k: got[k] for k in ("key", "state", "availability", "blocked_by", "forecast_finish", "started_at", "completed_at")} == \
               {k: want[k] for k in ("key", "state", "availability", "blocked_by", "forecast_finish", "started_at", "completed_at")}
        assert got["timing"]["assumption"]["label"] == "ASSUMPTION"
