from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from clearpath.db.models import (
    CitationLink, DatasetRelease, Jurisdiction, Project, ProjectEvent,
    ProjectMilestone, ProjectRequirement, SourcePassage, SourceSnapshot,
)


@pytest.fixture
def session(settings):
    assert settings.database_url.endswith("/clearpath_test")
    engine = create_engine(settings.database_url)
    with engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            yield session
        transaction.rollback()
    engine.dispose()


@pytest.fixture
def jurisdiction(session):
    row = Jurisdiction(slug=uuid4().hex, name="Test City", state="CA")
    session.add(row)
    session.flush()
    return row


def release(session, jurisdiction, **overrides):
    values = dict(jurisdiction_id=jurisdiction.id, project_type="adu", profile_key="test",
                  kind="synthetic", status="draft", schema_version=1, content_hash=uuid4().hex,
                  fact_schema={}, conflicts=[], curator_label="test")
    values.update(overrides)
    row = DatasetRelease(**values)
    session.add(row)
    session.flush()
    return row


def project(**overrides):
    values = dict(project_label="Test", project_type="adu", location={},
                  affordability_goal="unspecified", state="draft")
    values.update(overrides)
    return Project(**values)


@pytest.mark.parametrize("values,constraint", [
    ({"state": "active"}, "ck_project_release_state"),
    ({"state": "active", "pathway_key": "test"}, "ck_project_release_state"),
    ({"project_label": ""}, "ck_project_label_length"),
    ({"project_label": "x" * 81}, "ck_project_label_length"),
    ({"proposed_unit_count": -1}, "ck_project_proposed_units"),
    ({"affordable_unit_count_goal": -1}, "ck_project_affordable_units"),
    ({"proposed_unit_count": 1, "affordable_unit_count_goal": 2}, "ck_project_affordable_limit"),
    ({"state": "unknown"}, "ck_project_release_state"),
])
def test_project_state_check(session, values, constraint):
    with pytest.raises(IntegrityError) as error, session.begin_nested():
        session.add(project(**values))
        session.flush()
    assert error.value.orig.diag.constraint_name == constraint


def test_project_release_combinations(session, jurisdiction):
    dataset = release(session, jurisdiction)
    for values in ({"release_id": dataset.id}, {"pathway_key": "test"},
                   {"release_id": dataset.id, "pathway_key": "test"},
                   {"state": "active", "release_id": dataset.id}):
        with pytest.raises(IntegrityError) as error, session.begin_nested():
            session.add(project(**values))
            session.flush()
        assert error.value.orig.diag.constraint_name == "ck_project_release_state"
    draft = project(proposed_unit_count=0, affordable_unit_count_goal=0)
    active = project(state="active", release_id=dataset.id, pathway_key="test")
    session.add_all([draft, active])
    session.flush()
    assert draft.rule_facts == {} and draft.revision == 1
    assert draft.created_at.utcoffset().total_seconds() == 0


def test_active_release_scope_is_unique(session, jurisdiction):
    release(session, jurisdiction, status="active")
    release(session, jurisdiction, status="retired")
    with pytest.raises(IntegrityError) as error, session.begin_nested():
        release(session, jurisdiction, status="active")
    assert error.value.orig.diag.constraint_name == "uq_active_release_scope"
    release(session, jurisdiction, status="active", kind="reviewed_public")
    release(session, jurisdiction, status="active", profile_key="other")


def test_passages_have_release_scoped_manifest_ids_and_restrict_citations(session, jurisdiction):
    manifest_id = uuid4()
    passages = []
    for _ in range(2):
        dataset = release(session, jurisdiction)
        snapshot = SourceSnapshot(release_id=dataset.id, source_key="test", url="https://example.org",
                                  title="Test", publisher="Test", authority_type="city_guidance",
                                  checked_at=dataset.created_at, verification_depth="full_text_read")
        session.add(snapshot)
        session.flush()
        passage = SourcePassage(release_id=dataset.id, manifest_passage_id=manifest_id,
                                snapshot_id=snapshot.id, locator="#test", excerpt="test",
                                excerpt_hash="test", review_status="reviewed")
        session.add(passage)
        session.flush()
        passages.append(passage)
    assert passages[0].id != passages[1].id
    passage = passages[0]
    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(SourcePassage(release_id=passage.release_id, manifest_passage_id=manifest_id,
                                 snapshot_id=passage.snapshot_id, locator="#other", excerpt="other",
                                 excerpt_hash="other", review_status="reviewed"))
        session.flush()
    session.add(CitationLink(release_id=passage.release_id, owner_type="pathway", owner_key="test", passage_id=passage.id))
    session.flush()
    with pytest.raises(IntegrityError), session.begin_nested():
        session.execute(delete(SourcePassage).where(SourcePassage.id == passage.id))
    with pytest.raises(IntegrityError), session.begin_nested():
        session.execute(delete(DatasetRelease).where(DatasetRelease.id == passage.release_id))


def test_project_event_revision_unique_and_children_cascade(session):
    row = project()
    session.add(row)
    session.flush()
    session.add_all([
        ProjectRequirement(project_id=row.id, requirement_key="test", status="not_started"),
        ProjectMilestone(project_id=row.id, milestone_key="test", status="not_started"),
        ProjectEvent(project_id=row.id, revision=1, event_type="created", payload={}),
    ])
    session.flush()
    with pytest.raises(IntegrityError), session.begin_nested():
        session.add(ProjectEvent(project_id=row.id, revision=1, event_type="duplicate", payload={}))
        session.flush()
    session.execute(delete(Project).where(Project.id == row.id))
    for model in (ProjectRequirement, ProjectMilestone, ProjectEvent):
        assert session.scalars(select(model).where(model.project_id == row.id)).all() == []
