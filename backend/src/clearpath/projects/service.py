"""Project services: drafts, activation, checklist status, milestone events, timeline, events.

Services receive a SQLAlchemy ``Session`` and never commit; the caller (route/CLI)
owns the transaction. Every mutation locks the project row (SELECT ... FOR UPDATE),
checks ``expected_revision``, validates, writes state, bumps the revision and
appends exactly one audit event, all inside the caller's transaction. Any
DomainConflict raised before commit leaves no partial state or event.
``now`` and ``as_of`` are passed in; nothing here reads the wall clock.
"""

from __future__ import annotations

import base64
import uuid
from datetime import date, datetime, timezone
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from clearpath.timelines.calculate import build_timeline, progress as calc_progress
from clearpath.timelines.graph import apply_event, check_requirement_change, topo_order
from clearpath.timelines.model import (
    AssumedDays,
    DomainConflict,
    MilestoneDef,
    MilestoneState,
    RequirementState,
    SourceConflict,
)

from .lookup import LookupRequest, PermitLookupProvider, location_status
from .schemas import (
    MilestoneEventInput,
    ProjectActivationInput,
    ProjectCreateInput,
    ProjectUpdateInput,
    RequirementUpdateInput,
)
from .tables import jurisdictions, project_events, project_milestones, project_requirements, projects

SELF_REPORTED_WARNING = {
    "code": "self_reported_status",
    "message": "Ready means you marked it prepared. It does not mean the city accepted it.",
}
EVENTS_DEFAULT_LIMIT = 50
EVENTS_MAX_LIMIT = 100


def iso(ts: datetime | None) -> str | None:
    if ts is None:
        return None
    return ts.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------- loading

def _get_row(session: Session, project_id: uuid.UUID, *, lock: bool) -> Any:
    stmt = sa.select(projects).where(projects.c.id == project_id)
    if lock:
        stmt = stmt.with_for_update()
    row = session.execute(stmt).mappings().first()
    if row is None:
        raise DomainConflict("project_not_found", "No project with that id.", {"project_id": str(project_id)}, 404)
    return row


def _check_revision(row: Any, expected: int) -> None:
    if row["revision"] != expected:
        raise DomainConflict(
            "stale_revision",
            "This project changed since you loaded it. Reload and try again.",
            {"project_id": str(row["id"]), "expected_revision": expected, "current_revision": row["revision"]},
        )


def _require_active(row: Any) -> None:
    if row["state"] != "active":
        raise DomainConflict(
            "project_not_active",
            "Activate this project before updating its checklist or milestones.",
            {"project_id": str(row["id"]), "current_revision": row["revision"], "coverage_reason": row["coverage_reason"]},
        )


def _requirement_rows(session: Session, project_id: uuid.UUID, *, lock: bool = False) -> list[Any]:
    stmt = (sa.select(project_requirements).where(project_requirements.c.project_id == project_id)
            .order_by(project_requirements.c.position))
    if lock:
        stmt = stmt.with_for_update()
    return list(session.execute(stmt).mappings())


def _milestone_rows(session: Session, project_id: uuid.UUID, *, lock: bool = False) -> list[Any]:
    stmt = (sa.select(project_milestones).where(project_milestones.c.project_id == project_id)
            .order_by(project_milestones.c.position))
    if lock:
        stmt = stmt.with_for_update()
    return list(session.execute(stmt).mappings())


def _defs(rows: list[Any]) -> list[MilestoneDef]:
    return [
        MilestoneDef(
            key=r["milestone_key"], title=r["title"], position=r["position"],
            predecessors=tuple(r["predecessor_keys"]), requirement_keys=tuple(r["requirement_keys"]),
            actor=r["actor"],
            assumed=AssumedDays(r["assumed_min_days"], r["assumed_max_days"], r["assumed_rationale"]),
            citation_ids=tuple(r["citation_ids"]), action_titles=r["action_titles"],
            city_service_target=r["city_service_target"], statutory_clock=r["statutory_clock"],
        )
        for r in rows
    ]


def _states(rows: list[Any]) -> dict[str, MilestoneState]:
    return {r["milestone_key"]: MilestoneState(r["milestone_key"], r["status"], r["started_at"], r["completed_at"]) for r in rows}


def _reqs(rows: list[Any]) -> dict[str, RequirementState]:
    return {
        r["requirement_key"]: RequirementState(
            r["requirement_key"], r["applicability"], r["status"], r["required_for_preparation"],
            tuple(r["missing_fact_keys"]), r["title"], r["kind"],
        )
        for r in rows
    }


def _conflicts(row: Any) -> list[SourceConflict]:
    return [SourceConflict(tuple(c.get("rule_keys", [])), tuple(c.get("sources", [])), c.get("summary", ""))
            for c in row["source_conflicts"] or []]


def _bump(session: Session, row: Any, now: datetime, **values: Any) -> int:
    new_rev = row["revision"] + 1
    session.execute(sa.update(projects).where(projects.c.id == row["id"])
                    .values(revision=new_rev, updated_at=now, **values))
    return new_rev


def _append_event(session: Session, project_id: uuid.UUID, revision: int, event_type: str,
                  occurred_at: datetime, recorded_at: datetime, payload: dict) -> dict:
    event = {
        "id": uuid.uuid4(), "project_id": project_id, "revision": revision, "event_type": event_type,
        "occurred_at": occurred_at, "recorded_at": recorded_at, "payload": payload,
    }
    session.execute(sa.insert(project_events).values(**event))
    return _event_out(event)


def _event_out(e: Any) -> dict:
    return {
        "id": str(e["id"]), "event_type": e["event_type"], "revision": e["revision"],
        "occurred_at": iso(e["occurred_at"]), "recorded_at": iso(e["recorded_at"]), "payload": e["payload"],
    }


# ---------------------------------------------------------------- serialization

def project_detail(session: Session, project_id: uuid.UUID) -> dict:
    row = _get_row(session, project_id, lock=False)
    req_rows = _requirement_rows(session, project_id)
    ms_rows = _milestone_rows(session, project_id)
    milestone_keys: dict[str, list[str]] = {}
    for m in ms_rows:
        for k in m["requirement_keys"]:
            milestone_keys.setdefault(k, []).append(m["milestone_key"])
    warnings = list(row["warnings"] or [])
    if row["state"] == "active":
        warnings.append(SELF_REPORTED_WARNING)
    return {
        "id": str(row["id"]),
        "project_label": row["project_label"],
        "project_type": row["project_type"],
        "subtype": row["subtype"],
        "jurisdiction": row["jurisdiction"],
        "state": row["state"],
        "coverage_status": row["coverage_status"],
        "coverage_reason": row["coverage_reason"],
        "release": row["release_summary"],
        "pathway": row["pathway_summary"],
        "declared_location": row["location"],
        "proposed_unit_count": row["proposed_unit_count"],
        "affordability_goal": row["affordability_goal"],
        "affordable_unit_count_goal": row["affordable_unit_count_goal"],
        "affordability_verification": "not_assessed",
        "rule_facts": row["rule_facts"],
        "missing_fact_keys": row["missing_fact_keys"],
        "checklist": [
            {
                "key": r["requirement_key"], "kind": r["kind"], "title": r["title"],
                "milestone_keys": milestone_keys.get(r["requirement_key"], []),
                "applicability": r["applicability"], "missing_fact_keys": r["missing_fact_keys"],
                "required_for_preparation": r["required_for_preparation"], "status": r["status"],
                "updated_at": iso(r["updated_at"]), "citation_ids": r["citation_ids"],
            }
            for r in req_rows
        ],
        "progress": calc_progress(_states(ms_rows)) if row["state"] == "active" else None,
        "revision": row["revision"],
        "created_at": iso(row["created_at"]),
        "updated_at": iso(row["updated_at"]),
        "citations": row["citations"] or [],
        "warnings": warnings,
    }


# ---------------------------------------------------------------- create / read

def _row_scope(row: Any) -> dict:
    """The lookup-relevant fields of a stored project row (column ``location`` = API ``declared_location``)."""
    return {"project_type": row["project_type"], "subtype": row["subtype"], "jurisdiction": row["jurisdiction"],
            "declared_location": row["location"], "rule_facts": row["rule_facts"]}


def _jurisdiction_id(slug: str | None) -> Any:
    """Scalar subquery resolving Person 3's projects.jurisdiction_id from the slug (NULL if unknown)."""
    if slug is None:
        return None
    return sa.select(jurisdictions.c.id).where(jurisdictions.c.slug == slug).scalar_subquery()


def _lookup_request(row_or_input: Any, profile_key: str | None = None) -> LookupRequest:
    g = row_or_input.get if isinstance(row_or_input, dict) else row_or_input.__getitem__
    return LookupRequest(
        project_type=g("project_type"), subtype=g("subtype"), jurisdiction=g("jurisdiction"),
        location=g("declared_location"), rule_facts=g("rule_facts") or {}, profile_key=profile_key,
    )


def create_draft(session: Session, request: ProjectCreateInput, provider: PermitLookupProvider, now: datetime) -> dict:
    location = request.declared_location.model_dump(exclude_none=True)
    location["resolution_status"] = location_status(location)
    values = {
        "project_type": request.project_type, "subtype": request.subtype, "jurisdiction": request.jurisdiction,
        "declared_location": location, "rule_facts": request.rule_facts.model_dump(exclude_none=True),
    }
    assessment = provider.assess_scope(_lookup_request(values))
    if assessment.accepted_fact_keys is None and values["rule_facts"]:
        raise DomainConflict(
            "rule_facts_not_accepted",
            "No sourced rule profile matches this project yet, so rule facts can't be saved. Save it without rule facts.",
            {"rule_fact_keys": sorted(values["rule_facts"])}, 422,
        )
    project_id = uuid.uuid4()
    columns = {k: v for k, v in values.items() if k != "declared_location"}
    session.execute(sa.insert(projects).values(
        location=values["declared_location"], jurisdiction_id=_jurisdiction_id(request.jurisdiction),
        id=project_id, project_label=request.project_label, proposed_unit_count=request.proposed_unit_count,
        affordability_goal=request.affordability_goal, affordable_unit_count_goal=request.affordable_unit_count_goal,
        state="draft", coverage_status="unconfigured", coverage_reason=assessment.coverage_reason,
        missing_fact_keys=assessment.missing_fact_keys, source_conflicts=[], citations=[],
        warnings=assessment.warnings, revision=1, created_at=now, updated_at=now, **columns,
    ))
    _append_event(session, project_id, 1, "project_created", now, now,
                  {"project_type": request.project_type, "jurisdiction": request.jurisdiction})
    return project_detail(session, project_id)


def get_project(session: Session, project_id: uuid.UUID) -> dict:
    return project_detail(session, project_id)


# ---------------------------------------------------------------- activation

def activate_project(session: Session, project_id: uuid.UUID, request: ProjectActivationInput,
                     provider: PermitLookupProvider, now: datetime) -> dict:
    row = _get_row(session, project_id, lock=True)
    _check_revision(row, request.expected_revision)
    base = {"project_id": str(project_id), "current_revision": row["revision"]}
    if row["state"] != "draft":
        raise DomainConflict("project_already_active", "This project is already active.", base)

    result = provider.lookup(_lookup_request(_row_scope(row), request.profile_key))

    def fail(code: str, message: str, **extra: Any) -> DomainConflict:
        return DomainConflict(code, message, {**base, "coverage_reason": code, **extra})

    if result.status == "dataset_unavailable":
        raise DomainConflict("dataset_unavailable", "The rule dataset is unavailable right now.", base, 503)
    if result.status != "ok":
        msg = {
            "rule_coverage_unavailable": "No sourced rules cover this project type and location yet.",
            "location_unresolved": "The project location isn't resolved to a supported area.",
            "missing_information": "More project facts are needed before guidance can be activated.",
        }.get(result.status, "Guidance can't be activated for this project.")
        raise fail(result.status, msg, missing_fact_keys=result.missing_fact_keys)
    pathway = next((p for p in result.pathways if p["key"] == request.pathway_key), None)
    if pathway is None:
        raise fail("pathway_not_available", "That pathway isn't available for this project.",
                   available_pathway_keys=[p["key"] for p in result.pathways if p["status"] == "applies"])
    # A pathway whose rule is met but whose sources disagree (status needs_information,
    # status_reason source_conflict) can still be activated: the conflicts are saved in
    # source_conflicts and the timeline shows them as a source_conflict bottleneck.
    pathway_ok = pathway["status"] == "applies" or (
        pathway.get("status_reason") == "source_conflict" and pathway.get("rule_status") == "applies")
    if not pathway_ok:
        raise fail("missing_information", "More project facts are needed before this pathway applies.",
                   missing_fact_keys=pathway.get("missing_fact_keys", []))
    defs = [MilestoneDef(m["key"], m["title"], i, tuple(m["predecessor_keys"])) for i, m in enumerate(result.milestones)]
    try:
        topo_order(defs)
    except ValueError as exc:
        raise DomainConflict("release_graph_invalid", "The pinned release has an invalid milestone graph.",
                             {**base, "reason": str(exc)}, 503) from exc
    req_keys = {r["key"] for r in result.requirements}
    for m in result.milestones:
        unknown = [k for k in m["requirement_keys"] if k not in req_keys]
        if unknown:
            raise DomainConflict("release_graph_invalid", "A milestone references unknown requirements.",
                                 {**base, "milestone_key": m["key"], "requirement_keys": unknown}, 503)

    # All checks passed: write rows, pin the release, bump revision, append event (one transaction).
    for i, r in enumerate(result.requirements):
        session.execute(sa.insert(project_requirements).values(
            project_id=project_id, requirement_key=r["key"], position=i, kind=r["kind"], title=r["title"],
            applicability=r["applicability"], missing_fact_keys=r.get("missing_fact_keys", []),
            required_for_preparation=r["required_for_preparation"], citation_ids=r.get("citation_ids", []),
            status="not_started", updated_at=now,
        ))
    for i, m in enumerate(result.milestones):
        a = m.get("assumed_days") or {}
        session.execute(sa.insert(project_milestones).values(
            project_id=project_id, milestone_key=m["key"], position=i, title=m["title"],
            predecessor_keys=m["predecessor_keys"], requirement_keys=m["requirement_keys"], actor=m.get("actor"),
            assumed_min_days=a.get("min"), assumed_max_days=a.get("max"), assumed_rationale=a.get("rationale"),
            action_titles=m.get("action_titles"), city_service_target=m.get("city_service_target"),
            statutory_clock=m.get("statutory_clock"), citation_ids=m.get("citation_ids", []), status="not_started",
        ))
    release = result.release or {}
    new_rev = _bump(
        session, row, now, state="active", coverage_status="configured", coverage_reason=None,
        release_id=uuid.UUID(release["id"]), release_summary=release, pathway_key=pathway["key"],
        pathway_summary={"key": pathway["key"], "title": pathway["title"], "citation_ids": pathway["citation_ids"]},
        missing_fact_keys=result.missing_fact_keys,
        location_evidence={"resolution_status": result.location_status},
        source_conflicts=result.conflicts, citations=result.citations, warnings=result.warnings,
    )
    _append_event(session, project_id, new_rev, "project_activated", now, now,
                  {"release_id": release["id"], "pathway_key": pathway["key"]})
    return project_detail(session, project_id)


# ---------------------------------------------------------------- checklist

def set_requirement_status(session: Session, project_id: uuid.UUID, key: str,
                           request: RequirementUpdateInput, now: datetime) -> dict:
    row = _get_row(session, project_id, lock=True)
    _check_revision(row, request.expected_revision)
    _require_active(row)
    req_row = session.execute(
        sa.select(project_requirements)
        .where(project_requirements.c.project_id == project_id, project_requirements.c.requirement_key == key)
        .with_for_update()
    ).mappings().first()
    if req_row is None:
        raise DomainConflict("requirement_not_found", "That checklist item is not part of this project.",
                             {"project_id": str(project_id), "requirement_key": key}, 404)
    req = _reqs([req_row])[key]
    ms_rows = _milestone_rows(session, project_id)
    try:
        check_requirement_change(_defs(ms_rows), _states(ms_rows), req, request.status)
    except DomainConflict as exc:
        exc.details.update(project_id=str(project_id), current_revision=row["revision"])
        raise
    if req.status == request.status:
        return {"event": None, "project": project_detail(session, project_id)}
    session.execute(
        sa.update(project_requirements)
        .where(project_requirements.c.project_id == project_id, project_requirements.c.requirement_key == key)
        .values(status=request.status, updated_at=now)
    )
    new_rev = _bump(session, row, now)
    event = _append_event(session, project_id, new_rev, "requirement_status_changed", now, now,
                          {"requirement_key": key, "from_status": req.status, "to_status": request.status})
    return {"event": event, "project": project_detail(session, project_id)}


# ---------------------------------------------------------------- milestones

def record_milestone_event(session: Session, project_id: uuid.UUID, request: MilestoneEventInput, now: datetime) -> dict:
    row = _get_row(session, project_id, lock=True)
    _check_revision(row, request.expected_revision)
    _require_active(row)
    ms_rows = _milestone_rows(session, project_id, lock=True)
    states = _states(ms_rows)
    new_state = apply_event(
        _defs(ms_rows), states, _reqs(_requirement_rows(session, project_id)),
        milestone_key=request.milestone_key, kind=request.kind, occurred_at=request.occurred_at, now=now,
        correction_code=request.correction_code, project_id=str(project_id), current_revision=row["revision"],
    )
    old = states[request.milestone_key]
    session.execute(
        sa.update(project_milestones)
        .where(project_milestones.c.project_id == project_id, project_milestones.c.milestone_key == request.milestone_key)
        .values(status=new_state.state, started_at=new_state.started_at, completed_at=new_state.completed_at)
    )
    new_rev = _bump(session, row, now)
    event_type = {"start": "milestone_started", "complete": "milestone_completed", "reopen": "milestone_reopened"}[request.kind]
    event = _append_event(session, project_id, new_rev, event_type, request.occurred_at, now, {
        "milestone_key": request.milestone_key, "event_kind": request.kind,
        "from_state": old.state, "to_state": new_state.state, "correction_code": request.correction_code,
        "previous_started_at": iso(old.started_at), "previous_completed_at": iso(old.completed_at),
    })
    return {
        "event": event,
        "milestone": {"key": request.milestone_key, "state": new_state.state,
                      "started_at": iso(new_state.started_at), "completed_at": iso(new_state.completed_at)},
        "project": project_detail(session, project_id),
    }


# ---------------------------------------------------------------- timeline

def get_timeline(session: Session, project_id: uuid.UUID, as_of: date) -> dict:
    row = _get_row(session, project_id, lock=False)
    head = {
        "project_id": str(project_id), "as_of": as_of.isoformat(), "revision": row["revision"],
        "coverage_status": row["coverage_status"], "coverage_reason": row["coverage_reason"],
        "release": row["release_summary"], "pathway": row["pathway_summary"],
    }
    warnings = list(row["warnings"] or [])
    if row["state"] != "active":
        return {
            **head, "status": "timeline_unconfigured", "progress": None, "document_readiness": None,
            "next_actions": [], "bottlenecks": [], "milestones": [], "forecast": None,
            "source_conflicts": [], "citations": [], "warnings": warnings,
        }
    ms_rows = _milestone_rows(session, project_id)
    computed = build_timeline(_defs(ms_rows), _states(ms_rows), _reqs(_requirement_rows(session, project_id)),
                              _conflicts(row), as_of)
    return {
        "project_id": head["project_id"], "status": "timeline_available", **{k: v for k, v in head.items() if k != "project_id"},
        **computed,
        "source_conflicts": row["source_conflicts"] or [],
        "citations": row["citations"] or [],
        "warnings": warnings + [SELF_REPORTED_WARNING],
    }


# ---------------------------------------------------------------- events

def _encode_cursor(revision: int) -> str:
    return base64.urlsafe_b64encode(f"rev:{revision}".encode()).decode().rstrip("=")


def _decode_cursor(cursor: str) -> int:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        prefix, value = raw.split(":", 1)
        if prefix != "rev":
            raise ValueError
        return int(value)
    except Exception as exc:  # noqa: BLE001 - any malformed cursor is a client error
        raise DomainConflict("invalid_cursor", "The cursor is not valid.", {}, 422) from exc


def list_events(session: Session, project_id: uuid.UUID, cursor: str | None, limit: int | None) -> dict:
    limit = EVENTS_DEFAULT_LIMIT if limit is None else limit
    if not 1 <= limit <= EVENTS_MAX_LIMIT:
        raise DomainConflict("validation_error", f"limit must be between 1 and {EVENTS_MAX_LIMIT}.", {"limit": limit}, 422)
    _get_row(session, project_id, lock=False)
    stmt = sa.select(project_events).where(project_events.c.project_id == project_id)
    if cursor:
        stmt = stmt.where(project_events.c.revision > _decode_cursor(cursor))
    rows = list(session.execute(stmt.order_by(project_events.c.revision).limit(limit + 1)).mappings())
    more = len(rows) > limit
    rows = rows[:limit]
    return {
        "project_id": str(project_id),
        "items": [_event_out(r) for r in rows],
        "next_cursor": _encode_cursor(rows[-1]["revision"]) if more and rows else None,
    }


# ---------------------------------------------------------------- draft edit + portfolio list

def update_draft(session: Session, project_id: uuid.UUID, request: ProjectUpdateInput,
                 provider: PermitLookupProvider, now: datetime) -> dict:
    row = _get_row(session, project_id, lock=True)
    _check_revision(row, request.expected_revision)
    if row["state"] != "draft":
        raise DomainConflict("project_scope_immutable",
                             "An active project's scope can't be edited. Start a new draft to change it.",
                             {"project_id": str(project_id), "current_revision": row["revision"]})
    changes: dict[str, Any] = {}
    for name in request.model_fields_set - {"expected_revision"}:
        value = getattr(request, name)
        if name == "declared_location" and value is not None:
            value = value.model_dump(exclude_none=True)
            value["resolution_status"] = location_status(value)
        elif name == "rule_facts":
            value = value.model_dump(exclude_none=True) if value is not None else {}
        changes[name] = value
    merged = {**_row_scope(row), **{k: row[k] for k in ("proposed_unit_count", "affordable_unit_count_goal", "project_label")}}
    merged.update(changes)
    if merged["project_label"] is None or merged["project_type"] is None or merged["declared_location"] is None:
        raise DomainConflict("validation_error", "project_label, project_type and declared_location can't be cleared.", {}, 422)
    if (merged["affordable_unit_count_goal"] is not None and merged["proposed_unit_count"] is not None
            and merged["affordable_unit_count_goal"] > merged["proposed_unit_count"]):
        raise DomainConflict("validation_error", "affordable_unit_count_goal cannot exceed proposed_unit_count.", {}, 422)
    assessment = provider.assess_scope(_lookup_request(merged))
    if assessment.accepted_fact_keys is None and merged["rule_facts"]:
        raise DomainConflict("rule_facts_not_accepted",
                             "No sourced rule profile matches this project yet, so rule facts can't be saved.",
                             {"rule_fact_keys": sorted(merged["rule_facts"])}, 422)
    if not changes:
        return project_detail(session, project_id)
    columns = {("location" if k == "declared_location" else k): v for k, v in changes.items()}
    if "jurisdiction" in changes:
        columns["jurisdiction_id"] = _jurisdiction_id(changes["jurisdiction"])
    new_rev = _bump(session, row, now, coverage_reason=assessment.coverage_reason,
                    missing_fact_keys=assessment.missing_fact_keys, warnings=assessment.warnings, **columns)
    _append_event(session, project_id, new_rev, "project_updated", now, now, {"changed_fields": sorted(changes)})
    return project_detail(session, project_id)


def _encode_list_cursor(created_at: datetime, pid: uuid.UUID) -> str:
    return base64.urlsafe_b64encode(f"{iso(created_at)}|{pid}".encode()).decode().rstrip("=")


def _decode_list_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()
        ts, pid = raw.split("|", 1)
        return datetime.fromisoformat(ts.replace("Z", "+00:00")), uuid.UUID(pid)
    except Exception as exc:  # noqa: BLE001
        raise DomainConflict("invalid_cursor", "The cursor is not valid.", {}, 422) from exc


def list_projects(session: Session, *, jurisdiction: str | None = None, project_type: str | None = None,
                  state: str | None = None, coverage_status: str | None = None,
                  cursor: str | None = None, limit: int = EVENTS_DEFAULT_LIMIT) -> dict:
    if not 1 <= limit <= EVENTS_MAX_LIMIT:
        raise DomainConflict("validation_error", f"limit must be between 1 and {EVENTS_MAX_LIMIT}.", {"limit": limit}, 422)
    stmt = sa.select(projects)
    for col, val in ((projects.c.jurisdiction, jurisdiction), (projects.c.project_type, project_type),
                     (projects.c.state, state), (projects.c.coverage_status, coverage_status)):
        if val is not None:
            stmt = stmt.where(col == val)
    if cursor:
        ts, pid = _decode_list_cursor(cursor)
        stmt = stmt.where(sa.tuple_(projects.c.created_at, projects.c.id) > sa.tuple_(sa.literal(ts), sa.literal(pid)))
    rows = list(session.execute(stmt.order_by(projects.c.created_at, projects.c.id).limit(limit + 1)).mappings())
    more = len(rows) > limit
    rows = rows[:limit]
    counts: dict[Any, tuple[int, int]] = {}
    if rows:
        q = (sa.select(project_milestones.c.project_id, sa.func.count(),
                       sa.func.count().filter(project_milestones.c.status == "completed"))
             .where(project_milestones.c.project_id.in_([r["id"] for r in rows]))
             .group_by(project_milestones.c.project_id))
        counts = {pid: (total, done) for pid, total, done in session.execute(q)}
    from clearpath.timelines.calculate import percent

    items = []
    for r in rows:
        total, done = counts.get(r["id"], (0, 0))
        items.append({
            "id": str(r["id"]), "project_label": r["project_label"], "project_type": r["project_type"],
            "subtype": r["subtype"], "jurisdiction": r["jurisdiction"], "state": r["state"],
            "coverage_status": r["coverage_status"], "coverage_reason": r["coverage_reason"],
            "proposed_unit_count": r["proposed_unit_count"], "affordability_goal": r["affordability_goal"],
            "affordable_unit_count_goal": r["affordable_unit_count_goal"], "affordability_verification": "not_assessed",
            "revision": r["revision"],
            "progress": {"completed": done, "total": total, "percent": percent(done, total)} if total else None,
            "created_at": iso(r["created_at"]),
        })
    return {"items": items, "next_cursor": _encode_list_cursor(rows[-1]["created_at"], rows[-1]["id"]) if more else None}
