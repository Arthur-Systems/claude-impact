"""Milestone graph and the spec section 8 transition table, as pure functions.

| Event    | Allowed prior state                              | New state                       |
|----------|--------------------------------------------------|---------------------------------|
| start    | not_started, prerequisites + required items ok   | in_progress, started_at set     |
| complete | in_progress, prerequisites + required items ok   | completed, completed_at set     |
| reopen   | in_progress/completed, no started/completed dep. | not_started, timestamps cleared |

Every other transition is a 409 ``milestone_transition_conflict``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Mapping, Sequence

from .model import (
    CORRECTION_CODES,
    EVENT_KINDS,
    DomainConflict,
    MilestoneDef,
    MilestoneState,
    RequirementState,
)

ALLOWED_PRIOR = {
    "start": ("not_started",),
    "complete": ("in_progress",),
    "reopen": ("in_progress", "completed"),
}


def topo_order(defs: Sequence[MilestoneDef]) -> list[str]:
    """Stable topological order (ties broken by template position).

    Raises ValueError for unknown predecessor keys or cycles.
    """
    by_key = {d.key: d for d in defs}
    if len(by_key) != len(defs):
        raise ValueError("duplicate milestone keys")
    for d in defs:
        for p in d.predecessors:
            if p not in by_key:
                raise ValueError(f"milestone {d.key!r} has unknown predecessor {p!r}")
    remaining = {d.key: set(d.predecessors) for d in defs}
    ordered: list[str] = []
    while remaining:
        ready = sorted((k for k, preds in remaining.items() if not preds), key=lambda k: (by_key[k].position, k))
        if not ready:
            raise ValueError("milestone graph has a cycle")
        k = ready[0]
        ordered.append(k)
        del remaining[k]
        for preds in remaining.values():
            preds.discard(k)
    return ordered


def template_order(defs: Iterable[MilestoneDef]) -> list[MilestoneDef]:
    return sorted(defs, key=lambda d: (d.position, d.key))


def dependents_of(defs: Sequence[MilestoneDef], key: str) -> list[str]:
    return [d.key for d in template_order(defs) if key in d.predecessors]


def requirement_blocks(req: RequirementState | None) -> bool:
    """A required preparation item blocks until it is marked ready.

    Items whose applicability is unknown (needs_information) are treated
    conservatively: they block until ready. Inapplicable items never block.
    """
    if req is None:
        return False
    if req.applicability == "not_applicable" or not req.required_for_preparation:
        return False
    return req.status != "ready"


def unmet_predecessors(d: MilestoneDef, states: Mapping[str, MilestoneState]) -> list[str]:
    return [p for p in d.predecessors if states[p].state != "completed"]


def unready_requirements(d: MilestoneDef, reqs: Mapping[str, RequirementState]) -> list[str]:
    return [k for k in d.requirement_keys if requirement_blocks(reqs.get(k))]


def blocked_by(d: MilestoneDef, states: Mapping[str, MilestoneState], reqs: Mapping[str, RequirementState]) -> list[dict]:
    out = [{"kind": "predecessor", "key": p} for p in unmet_predecessors(d, states)]
    out += [{"kind": "requirement", "key": k} for k in unready_requirements(d, reqs)]
    return out


def availability(d: MilestoneDef, states: Mapping[str, MilestoneState], reqs: Mapping[str, RequirementState]) -> str:
    st = states[d.key].state
    if st == "completed":
        return "completed"
    if st == "in_progress":
        return "in_progress"
    return "blocked" if blocked_by(d, states, reqs) else "available"


def _human_list(items: list[str]) -> str:
    items = [i.replace("_", " ") for i in items]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def apply_event(
    defs: Sequence[MilestoneDef],
    states: Mapping[str, MilestoneState],
    reqs: Mapping[str, RequirementState],
    *,
    milestone_key: str,
    kind: str,
    occurred_at: datetime,
    now: datetime,
    correction_code: str | None = None,
    project_id: str | None = None,
    current_revision: int | None = None,
) -> MilestoneState:
    """Validate one milestone event and return the milestone's new state.

    Raises DomainConflict (409, or 404/422 for unknown keys/bad input).
    ``now`` is passed in by the caller; this function never reads the clock.
    """
    by_key = {d.key: d for d in defs}
    base = {"project_id": project_id, "milestone_key": milestone_key, "event_kind": kind, "current_revision": current_revision}
    if milestone_key not in by_key:
        raise DomainConflict("milestone_not_found", "That milestone is not part of this project.", base, 404)
    if kind not in EVENT_KINDS:
        raise DomainConflict("validation_error", "Unknown milestone event kind.", base, 422)
    if occurred_at.tzinfo is None or occurred_at.utcoffset() is None:
        raise DomainConflict("validation_error", "occurred_at must include a timezone.", base, 422)
    if correction_code is not None:
        if correction_code not in CORRECTION_CODES:
            raise DomainConflict("validation_error", "Unknown correction code.", base, 422)
        if kind != "reopen":
            raise DomainConflict("validation_error", "A correction code is only accepted on reopen.", base, 422)

    d = by_key[milestone_key]
    cur = states[milestone_key]
    title = d.title
    details = {
        **base,
        "current_state": cur.state,
        "allowed_prior_states": list(ALLOWED_PRIOR[kind]),
        "unmet_predecessor_keys": [],
        "unready_requirement_keys": [],
    }

    if occurred_at > now:
        raise DomainConflict(
            "milestone_transition_conflict",
            f"{title} can't be recorded with a future date.",
            {**details, "reason": "future_timestamp"},
        )

    if kind in ("start", "complete"):
        preds = unmet_predecessors(d, states)
        unready = unready_requirements(d, reqs)
        wrong_state = cur.state not in ALLOWED_PRIOR[kind]
        if wrong_state or preds or unready:
            verb = "started" if kind == "start" else "completed"
            reasons = []
            if wrong_state:
                if kind == "complete" and cur.state == "not_started":
                    reasons.append("it hasn't started")
                elif cur.state == "completed":
                    reasons.append("it is already complete")
                else:
                    reasons.append("it is already in progress")
            if preds:
                reasons.append(f"{_human_list(preds)} {'isn' if len(preds) == 1 else 'aren'}'t complete")
            if unready:
                reasons.append(f"{_human_list(unready)} {'is' if len(unready) == 1 else 'are'} not marked ready")
            msg = f"{title} can't be {verb} yet. " + (reasons[0][0].upper() + reasons[0][1:])
            if len(reasons) > 1:
                msg += ", and " + ", and ".join(reasons[1:])
            msg += "."
            raise DomainConflict(
                "milestone_transition_conflict",
                msg,
                {**details, "unmet_predecessor_keys": preds, "unready_requirement_keys": unready},
            )
        if kind == "start":
            latest_pred = max((states[p].completed_at for p in d.predecessors if states[p].completed_at), default=None)
            if latest_pred is not None and occurred_at < latest_pred:
                raise DomainConflict(
                    "milestone_transition_conflict",
                    f"{title} can't start before its previous step was completed.",
                    {**details, "reason": "start_before_predecessor_completion"},
                )
            return cur.with_(state="in_progress", started_at=occurred_at, completed_at=None)
        # complete
        if cur.started_at is not None and occurred_at < cur.started_at:
            raise DomainConflict(
                "milestone_transition_conflict",
                f"{title} can't be completed before it started.",
                {**details, "reason": "completion_before_start"},
            )
        return cur.with_(state="completed", completed_at=occurred_at)

    # reopen
    if cur.state not in ALLOWED_PRIOR["reopen"]:
        raise DomainConflict(
            "milestone_transition_conflict",
            f"{title} can't be reopened because it hasn't started.",
            details,
        )
    active_deps = [k for k in dependents_of(defs, milestone_key) if states[k].state != "not_started"]
    if active_deps:
        raise DomainConflict(
            "milestone_transition_conflict",
            f"Reopen {_human_list(active_deps)} first, then {title.lower()}.",
            {**details, "active_dependent_keys": active_deps},
        )
    latest_own = max((t for t in (cur.started_at, cur.completed_at) if t), default=None)
    if latest_own is not None and occurred_at < latest_own:
        raise DomainConflict(
            "milestone_transition_conflict",
            f"{title} can't be reopened before its last recorded date.",
            {**details, "reason": "reopen_before_last_event"},
        )
    return cur.with_(state="not_started", started_at=None, completed_at=None)


def check_requirement_change(
    defs: Sequence[MilestoneDef],
    states: Mapping[str, MilestoneState],
    req: RequirementState,
    new_status: str,
) -> None:
    """Demoting a ready item requires reopening dependent started/completed milestones first."""
    if req.applicability == "not_applicable":
        raise DomainConflict(
            "requirement_not_applicable",
            "This item does not apply to the project, so its status can't be changed.",
            {"requirement_key": req.key},
        )
    if req.status == "ready" and new_status != "ready":
        active = [
            d.key for d in template_order(defs)
            if req.key in d.requirement_keys and states[d.key].state != "not_started"
        ]
        if active:
            raise DomainConflict(
                "requirement_transition_conflict",
                f"Reopen {_human_list(active)} before changing this item from ready.",
                {"requirement_key": req.key, "active_milestone_keys": active},
            )
