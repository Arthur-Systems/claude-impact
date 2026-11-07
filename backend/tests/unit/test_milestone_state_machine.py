"""Spec §8 milestone transition table, tested without a database (A8)."""

from datetime import datetime, timedelta, timezone

import pytest

from clearpath.timelines.graph import apply_event, check_requirement_change, topo_order
from clearpath.timelines.model import DomainConflict, MilestoneDef, MilestoneState, RequirementState

T0 = datetime(2026, 11, 1, 16, 0, tzinfo=timezone.utc)
NOW = datetime(2026, 11, 7, 18, 0, tzinfo=timezone.utc)

DEFS = [
    MilestoneDef("prep", "Application preparation", 1, (), ("doc_a",)),
    MilestoneDef("submit", "Submission", 2, ("prep",)),
    MilestoneDef("review", "Plan review", 3, ("submit",)),
    MilestoneDef("fees", "Fee readiness", 4, ("submit",), ("doc_b",)),
    MilestoneDef("issue", "Permit issuance", 5, ("review", "fees")),
]


def states(**overrides):
    base = {d.key: MilestoneState(d.key) for d in DEFS}
    base.update({k: MilestoneState(k, *v) for k, v in overrides.items()})
    return base


def reqs(a="ready", b="ready", b_app="applies"):
    return {
        "doc_a": RequirementState("doc_a", "applies", a),
        "doc_b": RequirementState("doc_b", b_app, b),
    }


def ev(st, rq, key, kind, at=T0, **kw):
    return apply_event(DEFS, st, rq, milestone_key=key, kind=kind, occurred_at=at, now=NOW, **kw)


def test_start_then_complete_sets_and_retains_timestamps():
    s = states()
    started = ev(s, reqs(), "prep", "start")
    assert started.state == "in_progress" and started.started_at == T0
    s["prep"] = started
    done = ev(s, reqs(), "prep", "complete", T0 + timedelta(days=2))
    assert done.state == "completed" and done.started_at == T0 and done.completed_at == T0 + timedelta(days=2)


def test_start_blocked_by_unready_required_item():
    with pytest.raises(DomainConflict) as e:
        ev(states(), reqs(a="in_progress"), "prep", "start")
    assert e.value.code == "milestone_transition_conflict"
    assert e.value.details["unready_requirement_keys"] == ["doc_a"]


def test_needs_information_item_blocks_until_ready_and_not_applicable_never_blocks():
    s = states(prep=("completed", T0, T0), submit=("completed", T0, T0))
    with pytest.raises(DomainConflict):
        ev(s, reqs(b="not_started", b_app="needs_information"), "fees", "start")
    assert ev(s, reqs(b="not_started", b_app="not_applicable"), "fees", "start").state == "in_progress"


def test_premature_completion_matches_fixture_message():
    s = states(prep=("completed", T0, T0), submit=("completed", T0, T0))
    with pytest.raises(DomainConflict) as e:
        ev(s, reqs(), "review", "complete")
    assert e.value.http_status == 409
    s2 = states(prep=("completed", T0, T0))
    with pytest.raises(DomainConflict) as e:
        ev(s2, reqs(), "review", "complete")
    assert e.value.details["current_state"] == "not_started"
    assert e.value.details["allowed_prior_states"] == ["in_progress"]
    assert e.value.details["unmet_predecessor_keys"] == ["submit"]
    assert e.value.message == "Plan review can't be completed yet. It hasn't started, and submit isn't complete."


@pytest.mark.parametrize("prior,kind", [("in_progress", "start"), ("completed", "start"), ("completed", "complete"), ("not_started", "reopen")])
def test_other_transitions_conflict(prior, kind):
    s = states(prep=(prior, T0 if prior != "not_started" else None, T0 if prior == "completed" else None))
    with pytest.raises(DomainConflict) as e:
        ev(s, reqs(), "prep", kind, T0 + timedelta(days=1))
    assert e.value.code == "milestone_transition_conflict"


def test_future_timestamp_rejected():
    with pytest.raises(DomainConflict) as e:
        ev(states(), reqs(), "prep", "start", NOW + timedelta(minutes=1))
    assert e.value.details["reason"] == "future_timestamp"


def test_completion_before_start_rejected():
    s = states(prep=("in_progress", T0, None))
    with pytest.raises(DomainConflict) as e:
        ev(s, reqs(), "prep", "complete", T0 - timedelta(hours=1))
    assert e.value.details["reason"] == "completion_before_start"


def test_start_before_predecessor_completion_rejected():
    s = states(prep=("completed", T0, T0 + timedelta(days=1)))
    with pytest.raises(DomainConflict):
        ev(s, reqs(), "submit", "start", T0)


def test_naive_timestamp_is_422():
    with pytest.raises(DomainConflict) as e:
        ev(states(), reqs(), "prep", "start", datetime(2026, 11, 1, 9, 0))
    assert e.value.http_status == 422


def test_reopen_requires_dependents_reopened_first_reverse_topological():
    s = states(prep=("completed", T0, T0), submit=("completed", T0, T0), review=("in_progress", T0, None))
    with pytest.raises(DomainConflict) as e:
        ev(s, reqs(), "submit", "reopen", T0 + timedelta(days=1))
    assert e.value.details["active_dependent_keys"] == ["review"]
    s["review"] = ev(s, reqs(), "review", "reopen", T0 + timedelta(days=1), correction_code="city_correction")
    assert s["review"] == MilestoneState("review")
    reopened = ev(s, reqs(), "submit", "reopen", T0 + timedelta(days=1))
    assert reopened.state == "not_started" and reopened.started_at is None and reopened.completed_at is None


def test_correction_code_only_on_reopen_and_validated():
    with pytest.raises(DomainConflict) as e:
        ev(states(), reqs(), "prep", "start", correction_code="city_correction")
    assert e.value.http_status == 422
    s = states(prep=("in_progress", T0, None))
    with pytest.raises(DomainConflict):
        ev(s, reqs(), "prep", "reopen", T0, correction_code="made_up")


def test_unknown_milestone_is_404():
    with pytest.raises(DomainConflict) as e:
        ev(states(), reqs(), "nope", "start")
    assert e.value.http_status == 404


def test_demoting_ready_item_requires_reopening_dependent_milestone():
    s = states(prep=("in_progress", T0, None))
    r = RequirementState("doc_a", "applies", "ready")
    with pytest.raises(DomainConflict) as e:
        check_requirement_change(DEFS, s, r, "in_progress")
    assert e.value.details["active_milestone_keys"] == ["prep"]
    check_requirement_change(DEFS, states(), r, "in_progress")  # no active milestone: fine


def test_not_applicable_requirement_cannot_be_changed():
    with pytest.raises(DomainConflict) as e:
        check_requirement_change(DEFS, states(), RequirementState("x", "not_applicable"), "ready")
    assert e.value.code == "requirement_not_applicable"


def test_topo_order_rejects_cycles_and_unknown_refs():
    assert topo_order(DEFS) == ["prep", "submit", "review", "fees", "issue"]
    with pytest.raises(ValueError):
        topo_order([MilestoneDef("a", "A", 1, ("b",)), MilestoneDef("b", "B", 2, ("a",))])
    with pytest.raises(ValueError):
        topo_order([MilestoneDef("a", "A", 1, ("zzz",))])
