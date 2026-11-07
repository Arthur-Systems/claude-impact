"""Person 5 integration tests against a real PostgreSQL (A7, A8, A9, A13).

Uses CLEARPATH_P5_TEST_DATABASE_URL (default: a local disposable DB that is wiped).
The schema is rebuilt at module start from Person 3's base migration
(``0001_initial``, which creates the project tables) followed by Person 5's
additive migration. Skipped when Person 3's base migration is not on the branch
(plain main before p3-platform merges) or when PostgreSQL is unreachable.
"""

from __future__ import annotations

import importlib.util
import json
import os
import threading
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
import sqlalchemy as sa

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from clearpath.projects import routes, service  # noqa: E402
from clearpath.projects.lookup import FixtureLookupStub  # noqa: E402
from clearpath.projects.schemas import RequirementUpdateInput  # noqa: E402
from clearpath.projects.standalone import create_standalone_app  # noqa: E402
from clearpath.timelines.model import DomainConflict  # noqa: E402

BACKEND = Path(__file__).resolve().parents[2]
EXAMPLES = BACKEND / "tests" / "fixtures" / "api_examples"
MIGRATION = BACKEND / "migrations" / "versions" / "20261107_p5_project_tables.py"
BASE_MIGRATION = BACKEND / "migrations" / "versions" / "0001_initial.py"  # Person 3 (p3-platform)
if not BASE_MIGRATION.exists():
    pytest.skip("Person 3's base schema migration (migrations/versions/0001_initial.py, branch p3-platform) is not "
                "on this branch; Person 5's migration only extends it. Runs after p3-platform merges.",
                allow_module_level=True)
STUB_RELEASE_ID = "c1ea0002-0000-4000-8000-000000000001"  # release id in projects/fixtures/lookup_stub_irvine_adu.json
DB_URL = os.environ.get(
    "CLEARPATH_P5_TEST_DATABASE_URL", "postgresql+psycopg://clearpath:clearpath@localhost:5432/clearpath_p5_test"
)
TABLES = ("project_events", "project_milestones", "project_requirements", "projects")


def _strip_example_warnings(body: dict) -> None:
    if isinstance(body.get("warnings"), list):
        body["warnings"] = [w for w in body["warnings"] if w.get("code") != "example_data"]


def example_response(name: str) -> dict:
    """The live-API part of an api_examples file: ``response`` minus the mock-only markers
    (``"example": true`` and the ``example_data`` warning)."""
    resp = json.loads((EXAMPLES / name).read_text())["response"]
    resp.pop("example", None)
    _strip_example_warnings(resp)
    if isinstance(resp.get("project"), dict):
        _strip_example_warnings(resp["project"])
    return resp


def _load(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def run_migration(engine, fn_name: str, path: Path = MIGRATION) -> None:
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    mod = _load(path)
    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            getattr(mod, fn_name)()


@pytest.fixture(scope="module")
def engine():
    assert _load(MIGRATION).down_revision == _load(BASE_MIGRATION).revision
    eng = sa.create_engine(DB_URL)
    try:
        with eng.connect():
            pass
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"PostgreSQL not available: {exc}")
    with eng.begin() as c:  # disposable test DB: start from an empty schema
        c.execute(sa.text("DROP SCHEMA public CASCADE"))
        c.execute(sa.text("CREATE SCHEMA public"))
    run_migration(eng, "upgrade", BASE_MIGRATION)
    run_migration(eng, "upgrade")
    with eng.begin() as c:  # the stub's pinned release must exist (projects.release_id FK, Person 3)
        jid = c.execute(sa.text("INSERT INTO jurisdictions (id, slug, name, state) VALUES "
                                "(gen_random_uuid(), 'irvine-ca', 'Irvine', 'CA') RETURNING id")).scalar_one()
        c.execute(sa.text(
            "INSERT INTO dataset_releases (id, jurisdiction_id, project_type, profile_key, kind, status, schema_version,"
            " content_hash, fact_schema, conflicts, curator_label) VALUES (:id, :j, 'adu',"
            " 'irvine-adu-detached-existing-dwelling', 'synthetic', 'active', 1, 'p5-stub', '{}', '[]', 'p5 test')"),
            {"id": STUB_RELEASE_ID, "j": jid})
    yield eng
    eng.dispose()


class Clock:
    def __init__(self):
        self.now = datetime(2026, 10, 20, 15, 30, tzinfo=timezone.utc)


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def client(engine, clock):
    with engine.begin() as c:
        c.execute(sa.text("TRUNCATE " + ", ".join(TABLES)))
    app = create_standalone_app(DB_URL)
    app.dependency_overrides[routes.get_now] = lambda: clock.now
    # These tests pin the synthetic stub so output matches the api_examples fixtures.
    app.dependency_overrides[routes.get_lookup_provider] = lambda: FixtureLookupStub()
    app.dependency_overrides[routes.get_dataset_mode] = lambda: "synthetic"
    with TestClient(app) as tc:
        yield tc
    app.state.engine.dispose()


C01 = {
    "project_label": "Backyard ADU demo",
    "project_type": "adu",
    "subtype": "detached_adu_existing_dwelling",
    "jurisdiction": "irvine-ca",
    "declared_location": {"mode": "selected_area", "area_key": "irvine-ca-citywide"},
    "proposed_unit_count": 1,
    "affordability_goal": "unspecified",
    "rule_facts": {"adu_form": "detached", "existing_dwelling": True},
}
PATHWAY = "irvine_adu_standard"


def create(client, body=None):
    r = client.post("/api/v1/projects", json=body or C01)
    assert r.status_code == 201, r.text
    return r.json()


def activate(client, pid, rev=1):
    r = client.post(f"/api/v1/projects/{pid}/activate", json={"pathway_key": PATHWAY, "expected_revision": rev})
    assert r.status_code == 200, r.text
    return r.json()


def patch_req(client, pid, key, status, rev):
    return client.patch(f"/api/v1/projects/{pid}/requirements/{key}", json={"status": status, "expected_revision": rev})


def mevent(client, pid, key, kind, at, rev, **kw):
    return client.post(f"/api/v1/projects/{pid}/milestone-events",
                       json={"milestone_key": key, "kind": kind, "occurred_at": at, "expected_revision": rev, **kw})


def count_events(engine, pid):
    with engine.connect() as c:
        return c.execute(sa.text("SELECT count(*) FROM project_events WHERE project_id = :p"), {"p": pid}).scalar()


# ------------------------------------------------------------------ schema

def test_migration_constraints(engine):
    with engine.connect() as c:
        names = set(sa.inspect(c).get_table_names())
    assert set(TABLES) <= names
    with pytest.raises(sa.exc.IntegrityError):
        with engine.begin() as c:  # an active project must have a pinned release (Person 3's constraint)
            c.execute(sa.text(
                "INSERT INTO projects (id, project_label, project_type, location, affordability_goal, state,"
                " coverage_status, revision, created_at, updated_at) VALUES (gen_random_uuid(), 'x', 'adu', '{}',"
                " 'unspecified', 'active', 'configured', 1, now(), now())"))
    with pytest.raises(sa.exc.IntegrityError):
        with engine.begin() as c:  # P5 check constraint
            c.execute(sa.text(
                "INSERT INTO projects (id, project_label, project_type, location, affordability_goal, state,"
                " coverage_status) VALUES (gen_random_uuid(), 'x', 'adu', '{}', 'unspecified', 'draft', 'bogus')"))
    with engine.begin() as c:  # Person 3-style insert without any P5 column still works (server defaults)
        pid = c.execute(sa.text(
            "INSERT INTO projects (id, project_label, project_type, location, affordability_goal, state) VALUES"
            " (gen_random_uuid(), 'x', 'adu', '{}', 'unspecified', 'draft') RETURNING id")).scalar_one()
        c.execute(sa.text("INSERT INTO project_requirements (project_id, requirement_key, status) VALUES (:p, 'r', 'not_started')"), {"p": pid})
        c.execute(sa.text("INSERT INTO project_milestones (project_id, milestone_key, status) VALUES (:p, 'm', 'not_started')"), {"p": pid})
        c.execute(sa.text("DELETE FROM projects WHERE id = :p"), {"p": pid})


def test_migration_downgrade_and_upgrade_round_trip():
    eng = sa.create_engine(DB_URL)
    try:
        run_migration(eng, "downgrade")
        with eng.connect() as c:  # Person 3's tables and columns stay; only P5's additions go
            insp = sa.inspect(c)
            assert set(TABLES) <= set(insp.get_table_names())
            cols = {col["name"] for col in insp.get_columns("projects")}
            assert "location" in cols and "coverage_status" not in cols
            assert {col["name"] for col in insp.get_columns("project_milestones")} == \
                {"project_id", "milestone_key", "status", "started_at", "completed_at"}
        run_migration(eng, "upgrade")
    finally:
        eng.dispose()


# ------------------------------------------------------------------ drafts (A7)

def test_create_draft_matches_project_created_example(client):
    want = example_response("project_created.json")
    got = create(client)
    for k in ("id", "created_at", "updated_at"):
        got.pop(k), want.pop(k)
    got.pop("citations")
    assert got == want
    again = client.get(f"/api/v1/projects/{create(client)['id']}")
    assert again.status_code == 200 and again.json()["state"] == "draft"


def test_unsupported_type_saved_as_unconfigured_draft(client):
    body = {"project_label": "Affordable multifamily idea", "project_type": "multifamily", "jurisdiction": "irvine-ca",
            "declared_location": {"mode": "selected_area", "area_key": "irvine-ca-citywide"},
            "proposed_unit_count": 40, "affordability_goal": "affordable_housing", "affordable_unit_count_goal": 40}
    p = create(client, body)
    assert p["coverage_reason"] == "rule_coverage_unavailable" and p["checklist"] == []
    assert p["affordability_verification"] == "not_assessed"
    r = client.post("/api/v1/projects", json={**body, "rule_facts": {"adu_form": "detached"}})
    assert r.status_code == 422 and r.json()["error"]["code"] == "rule_facts_not_accepted"
    r = client.post(f"/api/v1/projects/{p['id']}/activate", json={"pathway_key": PATHWAY, "expected_revision": 1})
    assert r.status_code == 409 and r.json()["error"]["code"] == "rule_coverage_unavailable"
    tl = client.get(f"/api/v1/projects/{p['id']}/timeline", params={"as_of": "2026-11-07"}).json()
    assert tl["status"] == "timeline_unconfigured" and tl["milestones"] == [] and tl["progress"] is None and tl["forecast"] is None


@pytest.mark.parametrize("bad", [
    {**C01, "applicant_name": "x"},
    {**C01, "rule_facts": {"adu_form": "detached", "owner_phone": "x"}},
    {**C01, "project_label": ""},
    {**C01, "proposed_unit_count": 2, "affordable_unit_count_goal": 3},
])
def test_create_rejects_unknown_or_invalid_fields(client, bad):
    r = client.post("/api/v1/projects", json=bad)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error" and "request_id" in r.json()


def test_failed_activation_keeps_draft_and_writes_nothing(client, engine):
    p = create(client, {**C01, "rule_facts": {"adu_form": "detached"}})
    assert p["coverage_reason"] == "missing_information"
    r = client.post(f"/api/v1/projects/{p['id']}/activate", json={"pathway_key": PATHWAY, "expected_revision": 1})
    assert r.status_code == 409
    err = r.json()["error"]
    assert err["code"] == "missing_information"
    assert err["details"]["current_revision"] == 1 and "existing_dwelling" in err["details"]["missing_fact_keys"]
    after = client.get(f"/api/v1/projects/{p['id']}").json()
    assert after["state"] == "draft" and after["revision"] == 1 and after["checklist"] == []
    assert count_events(engine, p["id"]) == 1
    with engine.connect() as c:
        assert c.execute(sa.text("SELECT count(*) FROM project_milestones WHERE project_id=:p"), {"p": p["id"]}).scalar() == 0


def test_activation_pins_release_and_generates_state(client, engine):
    p = create(client)
    r = client.post(f"/api/v1/projects/{p['id']}/activate", json={"pathway_key": PATHWAY, "expected_revision": 2})
    assert r.status_code == 409 and r.json()["error"]["code"] == "stale_revision"
    r = client.post(f"/api/v1/projects/{p['id']}/activate", json={"pathway_key": "nope", "expected_revision": 1})
    assert r.status_code == 409 and r.json()["error"]["code"] == "pathway_not_available"
    a = activate(client, p["id"])
    assert a["state"] == "active" and a["coverage_status"] == "configured" and a["revision"] == 2
    assert a["release"]["id"] == "c1ea0002-0000-4000-8000-000000000001" and a["pathway"]["key"] == PATHWAY
    assert len(a["checklist"]) == 12 and a["progress"] == {"completed": 0, "total": 6, "percent": 0.0}
    fee = next(c for c in a["checklist"] if c["key"] == "fee_determinations_school_transportation")
    assert fee["applicability"] == "needs_information" and fee["missing_fact_keys"] == ["floor_area_sqft"]
    assert any(w["code"] == "self_reported_status" for w in a["warnings"])
    r = client.post(f"/api/v1/projects/{p['id']}/activate", json={"pathway_key": PATHWAY, "expected_revision": 2})
    assert r.status_code == 409 and r.json()["error"]["code"] == "project_already_active"


def test_unknown_project_is_404(client):
    r = client.get(f"/api/v1/projects/{uuid.uuid4()}")
    assert r.status_code == 404 and r.json()["error"]["code"] == "project_not_found"


# ------------------------------------------------------------------ checklist + milestones (A8)

def test_draft_mutations_return_project_not_active(client):
    p = create(client)
    r = patch_req(client, p["id"], "site_plan", "ready", 1)
    assert r.status_code == 409 and r.json()["error"]["code"] == "project_not_active"
    r = mevent(client, p["id"], "application_preparation", "start", "2026-10-20T15:00:00Z", 1)
    assert r.status_code == 409 and r.json()["error"]["code"] == "project_not_active"


def test_requirement_patch_revision_and_audit_event(client, engine):
    p = create(client)
    activate(client, p["id"])
    r = patch_req(client, p["id"], "site_plan", "ready", 1)
    assert r.status_code == 409 and r.json()["error"]["code"] == "stale_revision"
    assert r.json()["error"]["details"]["current_revision"] == 2
    assert count_events(engine, p["id"]) == 2
    r = patch_req(client, p["id"], "site_plan", "in_progress", 2)
    assert r.status_code == 200
    body = r.json()
    assert set(body) == set(example_response("requirement_patch.json")) == {"dataset_mode", "event", "project", "warnings"}
    assert body["dataset_mode"] == "synthetic" and body["warnings"] == body["project"]["warnings"]
    assert body["event"]["event_type"] == "requirement_status_changed" and body["event"]["revision"] == 3
    assert body["event"]["payload"] == {"requirement_key": "site_plan", "from_status": "not_started", "to_status": "in_progress"}
    assert body["project"]["revision"] == 3
    assert patch_req(client, p["id"], "no_such_item", "ready", 3).status_code == 404
    r = patch_req(client, p["id"], "site_plan", "done", 3)
    assert r.status_code == 422


def test_premature_completion_is_409_with_no_writes(client, engine):
    want = example_response("milestone_event_conflict_409.json")["error"]
    p = create(client)
    activate(client, p["id"])
    r = mevent(client, p["id"], "plan_review", "complete", "2026-10-20T15:00:00Z", 2)
    assert r.status_code == 409
    err = r.json()["error"]
    assert err["code"] == want["code"] == "milestone_transition_conflict"
    assert set(want["details"]) <= set(err["details"])
    assert err["details"]["unmet_predecessor_keys"] == ["completeness_review"]
    assert err["details"]["current_revision"] == 2
    assert err["message"] == "Plan review can't be completed yet. It hasn't started, and completeness review isn't complete."
    assert client.get(f"/api/v1/projects/{p['id']}").json()["revision"] == 2
    assert count_events(engine, p["id"]) == 2



def test_future_timestamp_and_completion_before_start(client, clock):
    p = create(client)
    activate(client, p["id"])
    rev = 2
    for item in [c["key"] for c in client.get(f"/api/v1/projects/{p['id']}").json()["checklist"]
                 if "application_preparation" in c["milestone_keys"]]:
        assert patch_req(client, p["id"], item, "ready", rev).status_code == 200
        rev += 1
    future = (clock.now + timedelta(minutes=5)).isoformat()
    r = mevent(client, p["id"], "application_preparation", "start", future, rev)
    assert r.status_code == 409 and r.json()["error"]["details"]["reason"] == "future_timestamp"
    assert mevent(client, p["id"], "application_preparation", "start", "2026-10-20T15:00:00Z", rev).status_code == 200
    rev += 1
    r = mevent(client, p["id"], "application_preparation", "complete", "2026-10-20T14:00:00Z", rev)
    assert r.status_code == 409 and r.json()["error"]["details"]["reason"] == "completion_before_start"
    r = mevent(client, p["id"], "application_preparation", "start", "2026-10-20T15:00:00Z", rev, correction_code="city_correction")
    assert r.status_code == 422
    r = mevent(client, p["id"], "application_preparation", "start", "2026-10-20T15:00:00", rev)
    assert r.status_code == 422  # naive timestamp


def walk_to_timeline_example(client, clock):
    """Replay the history behind timeline.json / requirement_patch.json. Returns (project_id, revision)."""
    p = create(client)
    pid = p["id"]
    clock.now = datetime(2026, 10, 20, 16, 0, tzinfo=timezone.utc)
    activate(client, pid)
    rev = 2
    checklist = client.get(f"/api/v1/projects/{pid}").json()["checklist"]
    prep = [c["key"] for c in checklist if "application_preparation" in c["milestone_keys"]]
    for key in prep:
        assert patch_req(client, pid, key, "ready", rev).status_code == 200
        rev += 1
    clock.now = datetime(2026, 11, 7, 18, 12, tzinfo=timezone.utc)
    steps = [
        ("application_preparation", "start", "2026-10-20T16:00:00Z"),
        ("application_preparation", "complete", "2026-11-02T22:00:00Z"),
        ("submission", "start", "2026-11-03T16:00:00Z"),
        ("submission", "complete", "2026-11-03T17:30:00Z"),
        ("completeness_review", "start", "2026-11-04T17:00:00Z"),
    ]
    for key, kind, at in steps:
        r = mevent(client, pid, key, kind, at, rev)
        assert r.status_code == 200, r.text
        rev += 1
    assert patch_req(client, pid, "residential_takeoff_sheet", "in_progress", rev).status_code == 200
    rev += 1
    r = patch_req(client, pid, "developer_deposit_case_setup", "ready", rev)
    assert r.status_code == 200
    return pid, rev + 1, r.json()


def test_timeline_matches_example_end_to_end(client, clock):
    want = example_response("timeline.json")
    pid, rev, patched = walk_to_timeline_example(client, clock)
    assert patched["event"]["payload"] == {"requirement_key": "developer_deposit_case_setup",
                                           "from_status": "not_started", "to_status": "ready"}
    r = client.get(f"/api/v1/projects/{pid}/timeline", params={"as_of": "2026-11-07"})
    assert r.status_code == 200, r.text
    got = r.json()
    assert list(got) == list(want)
    assert got["revision"] == rev
    for k in ("dataset_mode", "status", "as_of", "coverage_status", "coverage_reason", "release", "pathway", "progress",
              "document_readiness", "forecast", "source_conflicts", "citations", "warnings"):
        if k == "forecast":
            assert got[k]["finish_range"] == want[k]["finish_range"] and got[k]["label"] == "ASSUMPTION"
        else:
            assert got[k] == want[k], k
    assert [(a["milestone_key"], a["event_kind"], a["title"]) for a in got["next_actions"]] == \
        [(a["milestone_key"], a["event_kind"], a["title"]) for a in want["next_actions"]]
    no_msg = lambda bs: [{k: v for k, v in b.items() if k != "message"} for b in bs]
    assert no_msg(got["bottlenecks"]) == no_msg(want["bottlenecks"])
    for g, w in zip(got["milestones"], want["milestones"]):
        assert g == w, g["key"]
    # same as_of -> identical output (no wall clock)
    assert client.get(f"/api/v1/projects/{pid}/timeline", params={"as_of": "2026-11-07"}).json() == got
    r = client.get(f"/api/v1/projects/{pid}/timeline", params={"as_of": "2026-11-03"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "as_of_before_latest_event"
    assert client.get(f"/api/v1/projects/{pid}/timeline").status_code == 422  # as_of required


def test_reopen_order_and_correction_cycle(client, clock):
    pid, rev, _ = walk_to_timeline_example(client, clock)
    r = mevent(client, pid, "submission", "reopen", "2026-11-05T17:00:00Z", rev, correction_code="city_correction")
    assert r.status_code == 409 and r.json()["error"]["details"]["active_dependent_keys"] == ["completeness_review"]
    r = mevent(client, pid, "completeness_review", "reopen", "2026-11-05T17:00:00Z", rev, correction_code="city_correction")
    assert r.status_code == 200
    assert r.json()["milestone"] == {"key": "completeness_review", "state": "not_started", "started_at": None, "completed_at": None}
    assert r.json()["event"]["payload"]["previous_started_at"] == "2026-11-04T17:00:00Z"
    rev += 1
    # demoting a ready prep item while its milestone is completed needs reopening first
    r = patch_req(client, pid, "site_plan", "in_progress", rev)
    assert r.status_code == 409 and r.json()["error"]["code"] == "requirement_transition_conflict"
    r = mevent(client, pid, "completeness_review", "start", "2026-11-06T17:00:00Z", rev)
    assert r.status_code == 200


# ------------------------------------------------------------------ isolation (A13)

def test_two_projects_sharing_release_are_independent(client, clock, engine):
    a, b = create(client), create(client)
    activate(client, a["id"]), activate(client, b["id"])
    before = client.get(f"/api/v1/projects/{b['id']}").json()
    tl_before = client.get(f"/api/v1/projects/{b['id']}/timeline", params={"as_of": "2026-11-07"}).json()
    assert patch_req(client, a["id"], "site_plan", "ready", 2).status_code == 200
    assert patch_req(client, b["id"], "site_plan", "ready", 3).json()["error"]["code"] == "stale_revision"
    assert client.get(f"/api/v1/projects/{b['id']}").json() == before
    assert client.get(f"/api/v1/projects/{b['id']}/timeline", params={"as_of": "2026-11-07"}).json() == tl_before
    assert count_events(engine, b["id"]) == 2 and count_events(engine, a["id"]) == 3


def test_concurrent_writers_one_wins_other_is_stale(client, engine, clock):
    from sqlalchemy.orm import Session

    p = create(client)
    activate(client, p["id"])
    pid = uuid.UUID(p["id"])
    s1 = Session(engine)
    service.set_requirement_status(s1, pid, "site_plan", RequirementUpdateInput(status="in_progress", expected_revision=2), clock.now)
    result = {}

    def second():
        with Session(engine) as s2:
            try:
                service.set_requirement_status(s2, pid, "site_plan", RequirementUpdateInput(status="ready", expected_revision=2), clock.now)
                s2.commit()
                result["ok"] = True
            except DomainConflict as exc:
                result["code"] = exc.code

    t = threading.Thread(target=second)
    t.start()
    t.join(timeout=1.0)
    assert t.is_alive(), "second writer should block on the row lock"
    s1.commit()
    s1.close()
    t.join(timeout=10)
    assert result == {"code": "stale_revision"}
    assert count_events(engine, p["id"]) == 3


# ------------------------------------------------------------------ events (task 7)

def test_events_cursor_pagination(client, clock):
    pid, rev, _ = walk_to_timeline_example(client, clock)
    total = rev
    page = client.get(f"/api/v1/projects/{pid}/events", params={"limit": 5}).json()
    assert [e["revision"] for e in page["items"]] == [1, 2, 3, 4, 5]
    assert page["items"][0]["event_type"] == "project_created"
    seen = [e["revision"] for e in page["items"]]
    while page["next_cursor"]:
        page = client.get(f"/api/v1/projects/{pid}/events", params={"limit": 5, "cursor": page["next_cursor"]}).json()
        seen += [e["revision"] for e in page["items"]]
    assert seen == list(range(1, total + 1))
    default = client.get(f"/api/v1/projects/{pid}/events").json()
    assert len(default["items"]) == total and default["next_cursor"] is None
    assert client.get(f"/api/v1/projects/{pid}/events", params={"limit": 101}).status_code == 422
    assert client.get(f"/api/v1/projects/{pid}/events", params={"cursor": "garbage!"}).status_code == 422


# ------------------------------------------------------------------ draft edit + portfolio (A14)

def test_draft_edit_then_activate_and_active_scope_immutable(client):
    p = create(client, {**C01, "rule_facts": {"adu_form": "detached"}})
    r = client.patch(f"/api/v1/projects/{p['id']}", json={"expected_revision": 1,
                                                          "rule_facts": {"adu_form": "detached", "existing_dwelling": True}})
    assert r.status_code == 200, r.text
    assert r.json()["revision"] == 2 and r.json()["coverage_reason"] == "activation_required"
    a = activate(client, p["id"], rev=2)
    r = client.patch(f"/api/v1/projects/{p['id']}", json={"expected_revision": a["revision"], "project_label": "x"})
    assert r.status_code == 409 and r.json()["error"]["code"] == "project_scope_immutable"
    r = client.patch(f"/api/v1/projects/{p['id']}", json={"expected_revision": 1, "owner_name": "x"})
    assert r.status_code == 422


def test_portfolio_list_filters_and_cursor(client, clock):
    ids = []
    for i in range(3):
        clock.now = datetime(2026, 11, 7, 17, 0, tzinfo=timezone.utc)  # tied created_at
        ids.append(create(client, {**C01, "project_label": f"ADU {i}"})["id"])
    mf = create(client, {"project_label": "Affordable multifamily", "project_type": "multifamily",
                         "jurisdiction": "irvine-ca", "affordability_goal": "affordable_housing",
                         "declared_location": {"mode": "selected_area", "area_key": "irvine-ca-citywide"}})
    activate(client, ids[0])
    seen, cursor = [], None
    while True:
        params = {"limit": 2, **({"cursor": cursor} if cursor else {})}
        page = client.get("/api/v1/projects", params=params).json()
        seen += [x["id"] for x in page["items"]]
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert sorted(seen) == sorted(ids + [mf["id"]]) and len(seen) == len(set(seen)) == 4
    active = client.get("/api/v1/projects", params={"state": "active"}).json()["items"]
    assert [x["id"] for x in active] == [ids[0]] and active[0]["progress"]["total"] == 6
    unconf = client.get("/api/v1/projects", params={"coverage_status": "unconfigured", "project_type": "multifamily"}).json()
    assert [x["id"] for x in unconf["items"]] == [mf["id"]] and unconf["items"][0]["progress"] is None
    assert client.get("/api/v1/projects", params={"limit": 101}).status_code == 422


# --- Real Irvine data through Person 4's ReleaseLookupProvider -------------------------


@pytest.fixture
def real_client(engine, clock):
    """The app with its default lookup: Person 2's reviewed Irvine manifest (CLEARPATH_MODE=public)."""
    provider = routes._build_lookup_provider("public")
    from clearpath.projects.lookup import LookupRequest
    probe = provider.lookup(LookupRequest("adu", C01["subtype"], "irvine-ca", C01["declared_location"], C01["rule_facts"]))
    with engine.begin() as c:
        c.execute(sa.text("TRUNCATE " + ", ".join(TABLES)))
        # Person 3's importer publishes this release; the test stands in for it (projects.release_id FK).
        c.execute(sa.text(
            "INSERT INTO dataset_releases (id, jurisdiction_id, project_type, profile_key, kind, status, schema_version,"
            " content_hash, fact_schema, conflicts, curator_label) SELECT :id, id, 'adu', :pk, 'reviewed_public',"
            " 'active', 1, :h, '{}', '[]', 'p5 real-data test' FROM jurisdictions WHERE slug = 'irvine-ca'"
            " ON CONFLICT (id) DO NOTHING"),
            {"id": probe.release["id"], "pk": probe.release["profile_key"], "h": probe.release["content_hash"]})
    app = create_standalone_app(DB_URL)
    app.dependency_overrides[routes.get_now] = lambda: clock.now
    with TestClient(app) as tc:
        yield tc
    app.state.engine.dispose()


def test_real_irvine_activation_with_source_conflicts(real_client, clock):
    p = create(real_client)
    r = real_client.post(f"/api/v1/projects/{p['id']}/activate", json={"pathway_key": PATHWAY, "expected_revision": 1})
    assert r.status_code == 200, r.json()
    project = r.json()
    assert project["state"] == "active"
    assert project["release"]["dataset_mode"] == "reviewed_public"
    assert project["checklist"], "real requirements were copied into the project"
    tl = real_client.get(f"/api/v1/projects/{p['id']}/timeline", params={"as_of": "2026-11-07"}).json()
    assert tl["progress"]["total"] == 6
    # Whatever conflicts the reviewed release reports are carried into the project unchanged.
    # (Person 2 may attach them to the pathway or to individual rules; both must activate.)
    from clearpath.projects.lookup import LookupRequest
    probe = routes._build_lookup_provider("public").lookup(
        LookupRequest("adu", C01["subtype"], "irvine-ca", C01["declared_location"], C01["rule_facts"]))
    assert bool(tl["source_conflicts"]) == bool(probe.conflicts)
    # Every assumed duration in the reviewed manifest is null, so no forecast is invented.
    assert tl["forecast"]["missing_stage_estimates"]


def test_rule_facts_accept_jadu_and_reject_junior(client):
    ok = client.post("/api/v1/projects", json={**C01, "rule_facts": {"adu_form": "jadu", "existing_dwelling": True}})
    assert ok.status_code == 201, ok.json()
    bad = client.post("/api/v1/projects", json={**C01, "rule_facts": {"adu_form": "junior", "existing_dwelling": True}})
    assert bad.status_code == 422
