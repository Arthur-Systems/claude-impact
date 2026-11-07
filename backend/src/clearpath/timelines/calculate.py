"""Timeline calculation: progress, readiness, next actions, bottlenecks, forecast.

Pure functions. ``as_of`` is always passed in; nothing here reads the wall clock.
Forecast numbers are ASSUMPTIONS from per-stage team estimates. They are never
a city promise or a legal due date (statutory arithmetic is disabled, spec §8).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Mapping, Sequence
from zoneinfo import ZoneInfo

from .graph import availability, blocked_by, template_order, topo_order, unmet_predecessors, unready_requirements
from .model import DomainConflict, MilestoneDef, MilestoneState, RequirementState, SourceConflict

CITY_TZ = ZoneInfo("America/Los_Angeles")
ASSUMPTION = "ASSUMPTION"
FORECAST_DISCLAIMER = (
    "Assumed range from per-stage estimates labeled ASSUMPTION. Not a city promise or a legal due date. "
    "Running past it does not mean the city missed a deadline."
)


def civil_date(ts: datetime) -> date:
    """City civil date (America/Los_Angeles) for a timezone-aware timestamp."""
    return ts.astimezone(CITY_TZ).date()


def percent(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    value = (Decimal(numerator) * 100 / Decimal(denominator)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return float(value)


def progress(states: Mapping[str, MilestoneState]) -> dict | None:
    total = len(states)
    if total == 0:
        return None
    completed = sum(1 for s in states.values() if s.state == "completed")
    return {"completed": completed, "total": total, "percent": percent(completed, total)}


def document_readiness(reqs: Mapping[str, RequirementState]) -> dict:
    """ready applicable / (applicable + needs_information). Unknown items stay pending."""
    applicable = [r for r in reqs.values() if r.applicability == "applies"]
    unknown = [r for r in reqs.values() if r.applicability == "needs_information"]
    ready = sum(1 for r in applicable if r.status == "ready")
    denominator = len(applicable) + len(unknown)
    return {
        "ready": ready,
        "applicable": len(applicable),
        "needs_information": len(unknown),
        "denominator": denominator,
        "percent": percent(ready, denominator),
        "provisional": len(unknown) > 0,
        "unknown_count": len(unknown),
    }


def _action_title(d: MilestoneDef, kind: str) -> str:
    if d.action_titles and d.action_titles.get(kind):
        return d.action_titles[kind]
    return f"Start {d.title.lower()}" if kind == "start" else f"Mark {d.title.lower()} complete"


def next_actions(defs: Sequence[MilestoneDef], states: Mapping[str, MilestoneState], reqs: Mapping[str, RequirementState]) -> list[dict]:
    """All available actions in template order (predecessors + required items satisfied)."""
    out = []
    for d in template_order(defs):
        st = states[d.key].state
        if st == "completed" or blocked_by(d, states, reqs):
            continue
        kind = "start" if st == "not_started" else "complete"
        out.append({"milestone_key": d.key, "event_kind": kind, "title": _action_title(d, kind), "citation_ids": list(d.citation_ids)})
    return out


def _elapsed_days(started_at: datetime, as_of: date) -> int:
    return max(0, (as_of - civil_date(started_at)).days)


def bottlenecks(
    defs: Sequence[MilestoneDef],
    states: Mapping[str, MilestoneState],
    reqs: Mapping[str, RequirementState],
    conflicts: Sequence[SourceConflict],
    as_of: date,
) -> list[dict]:
    """Reason-coded bottlenecks, grouped by milestone in template order.

    - awaiting_city: a city-owned milestone is in progress.
    - missing_information: a pending milestone needs an item whose applicability is unknown.
    - missing_documents: a milestone whose predecessors are complete waits on unready items.
    - estimate_exceeded: an in-progress stage ran past its assumed max (not a legal finding).
    - source_conflict: the pinned release records disagreeing sources.
    """
    out: list[dict] = []
    for d in template_order(defs):
        s = states[d.key]
        if s.state == "completed":
            continue
        if s.state == "in_progress" and d.actor == "city":
            out.append({
                "code": "awaiting_city", "milestone_key": d.key, "requirement_keys": [], "missing_fact_keys": [],
                "since": civil_date(s.started_at).isoformat() if s.started_at else None,
                "message": f"Waiting on the city's {d.title.lower()}.",
            })
        unknown = [reqs[k] for k in d.requirement_keys if k in reqs and reqs[k].applicability == "needs_information"
                   and reqs[k].status != "ready"]
        if unknown:
            facts = sorted({f for r in unknown for f in r.missing_fact_keys})
            out.append({
                "code": "missing_information", "milestone_key": d.key,
                "requirement_keys": [r.key for r in unknown], "missing_fact_keys": facts,
                "since": None,
                "message": (f"Add {', '.join(f.replace('_', ' ') for f in facts)} to see whether "
                            f"{'this item applies' if len(unknown) == 1 else 'these items apply'}.") if facts
                else "More information is needed to know whether this item applies.",
            })
        if not unmet_predecessors(d, states):
            missing = [k for k in unready_requirements(d, reqs) if reqs[k].applicability == "applies"]
            if missing:
                names = [reqs[k].title or k for k in missing]
                out.append({
                    "code": "missing_documents", "milestone_key": d.key, "requirement_keys": missing,
                    "missing_fact_keys": [], "since": None,
                    "message": f"{'; '.join(names)} {'is' if len(names) == 1 else 'are'} not marked ready yet.",
                })
        if s.state == "in_progress" and s.started_at and d.assumed.max_days is not None:
            elapsed = _elapsed_days(s.started_at, as_of)
            if elapsed > d.assumed.max_days:
                out.append({
                    "code": "estimate_exceeded", "milestone_key": d.key, "requirement_keys": [], "missing_fact_keys": [],
                    "since": civil_date(s.started_at).isoformat(),
                    "message": (f"{d.title} has taken {elapsed} days, past the assumed maximum of "
                                f"{d.assumed.max_days} days (ASSUMPTION). This is not a finding that a legal deadline was missed."),
                })
    for c in conflicts:
        out.append({
            "code": "source_conflict", "milestone_key": None, "requirement_keys": list(c.rule_keys),
            "missing_fact_keys": [], "since": None,
            "message": f"Sources disagree: {c.summary}",
        })
    return out


def latest_actual_date(states: Mapping[str, MilestoneState]) -> date | None:
    stamps = [t for s in states.values() for t in (s.started_at, s.completed_at) if t is not None]
    return max((civil_date(t) for t in stamps), default=None)


def forecast(defs: Sequence[MilestoneDef], states: Mapping[str, MilestoneState], as_of: date) -> tuple[dict, dict[str, dict | None]]:
    """Earliest-finish propagation through the DAG (max of predecessors, not a sum).

    Returns (project forecast, per-milestone forecast_finish). Completed stages use
    their actual completion date. In-progress stages subtract elapsed days from each
    bound, clamped at zero. Not-started stages begin no earlier than ``as_of`` and
    their predecessors' finishes. Any non-completed stage with an unknown estimate
    makes the project range null with ``missing_stage_estimates``.
    """
    by_key = {d.key: d for d in defs}
    if not defs:
        return ({"label": ASSUMPTION, "timing_kind": "assumption", "status": "unavailable", "finish_range": None,
                 "missing_stage_estimates": [], "disclaimer": FORECAST_DISCLAIMER}, {})
    missing = [d.key for d in template_order(defs) if states[d.key].state != "completed" and not d.assumed.known]
    finish: dict[str, tuple[date, date] | None] = {}
    per: dict[str, dict | None] = {}
    for key in topo_order(defs):
        d, s = by_key[key], states[key]
        if s.state == "completed":
            day = civil_date(s.completed_at) if s.completed_at else as_of
            finish[key] = (day, day)
            per[key] = None
            continue
        pred_fin = [finish[p] for p in d.predecessors]
        if not d.assumed.known or any(f is None for f in pred_fin):
            finish[key] = None
            per[key] = None
            continue
        if s.state == "in_progress":
            elapsed = _elapsed_days(s.started_at, as_of) if s.started_at else 0
            lo = as_of + timedelta(days=max(0, d.assumed.min_days - elapsed))
            hi = as_of + timedelta(days=max(0, d.assumed.max_days - elapsed))
        else:
            start_lo = max([as_of] + [f[0] for f in pred_fin])
            start_hi = max([as_of] + [f[1] for f in pred_fin])
            lo = start_lo + timedelta(days=d.assumed.min_days)
            hi = start_hi + timedelta(days=d.assumed.max_days)
        finish[key] = (lo, hi)
        per[key] = {"earliest": lo.isoformat(), "latest": hi.isoformat(), "label": ASSUMPTION}
    if missing:
        project = {"label": ASSUMPTION, "timing_kind": "assumption", "status": "missing_stage_estimates",
                   "finish_range": None, "missing_stage_estimates": missing,
                   "disclaimer": "No estimate available: one or more stages have no assumed duration."}
    else:
        lo = max(f[0] for f in finish.values())
        hi = max(f[1] for f in finish.values())
        project = {"label": ASSUMPTION, "timing_kind": "assumption", "status": "available",
                   "finish_range": {"earliest": lo.isoformat(), "latest": hi.isoformat()},
                   "missing_stage_estimates": [], "disclaimer": FORECAST_DISCLAIMER}
    return project, per


def _timing(d: MilestoneDef) -> dict:
    a = d.assumed
    return {
        "city_service_target": d.city_service_target,
        "statutory_clock": d.statutory_clock,
        "observed": None,
        "assumption": None if (a.min_days is None and a.max_days is None) else {
            "min_days": a.min_days, "max_days": a.max_days, "label": ASSUMPTION, "rationale": a.rationale,
        },
    }


def _iso(ts: datetime | None) -> str | None:
    if ts is None:
        return None
    from datetime import timezone
    return ts.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def build_timeline(
    defs: Sequence[MilestoneDef],
    states: Mapping[str, MilestoneState],
    reqs: Mapping[str, RequirementState],
    conflicts: Sequence[SourceConflict],
    as_of: date,
) -> dict:
    """Assemble the computed part of the timeline response."""
    latest = latest_actual_date(states)
    if latest is not None and as_of < latest:
        raise DomainConflict(
            "as_of_before_latest_event",
            "as_of can't be earlier than the latest recorded milestone date.",
            {"as_of": as_of.isoformat(), "latest_event_date": latest.isoformat()},
            422,
        )
    project_forecast, per = forecast(defs, states, as_of)
    milestones = []
    for d in template_order(defs):
        s = states[d.key]
        milestones.append({
            "key": d.key,
            "title": d.title,
            "predecessor_keys": list(d.predecessors),
            "requirement_keys": list(d.requirement_keys),
            "state": s.state,
            "availability": availability(d, states, reqs),
            "started_at": _iso(s.started_at),
            "completed_at": _iso(s.completed_at),
            "blocked_by": blocked_by(d, states, reqs) if s.state != "completed" else [],
            "timing": _timing(d),
            "forecast_finish": per.get(d.key),
            "citation_ids": list(d.citation_ids),
        })
    return {
        "progress": progress(states),
        "document_readiness": document_readiness(reqs),
        "next_actions": next_actions(defs, states, reqs),
        "bottlenecks": bottlenecks(defs, states, reqs, conflicts, as_of),
        "milestones": milestones,
        "forecast": project_forecast,
    }
