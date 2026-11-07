"""Exercise publication locks and active-scope uniqueness on real PostgreSQL."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic, sleep
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from clearpath.db.models import DatasetRelease, Jurisdiction
from clearpath.ingestion.service import publish_release


def release(jurisdiction_id, **overrides):
    values = dict(
        jurisdiction_id=jurisdiction_id, project_type="adu", profile_key="synthetic-race",
        kind="synthetic", status="draft", schema_version=1, content_hash=uuid4().hex,
        fact_schema={}, conflicts=[], curator_label="SYNTHETIC concurrency test",
    )
    values.update(overrides)
    return DatasetRelease(**values)


@pytest.fixture
def committed_drafts(settings, test_database_name):
    # Only this test's rows are committed, and all are deleted even on failure.
    name = make_url(settings.database_url).database
    assert name == test_database_name
    engine = create_engine(settings.database_url, hide_parameters=True, connect_args={"connect_timeout": 2})
    jurisdiction_id, first_id, second_id = uuid4(), uuid4(), uuid4()
    try:
        with Session(engine) as session:
            session.add(Jurisdiction(id=jurisdiction_id, slug="synthetic-" + uuid4().hex,
                                     name="SYNTHETIC race city", state="CA"))
            session.flush()
            session.add_all([release(jurisdiction_id, id=first_id), release(jurisdiction_id, id=second_id)])
            session.commit()
        yield engine, jurisdiction_id, first_id, second_id
    finally:
        with engine.begin() as connection:
            connection.execute(delete(DatasetRelease).where(DatasetRelease.id.in_([first_id, second_id])))
            connection.execute(delete(Jurisdiction).where(Jurisdiction.id == jurisdiction_id))
        engine.dispose()


def test_concurrent_publish_serializes_and_leaves_exactly_one_active(committed_drafts):
    engine, jurisdiction_id, first_id, second_id = committed_drafts
    first_published, release_first, second_started = Event(), Event(), Event()
    pids = {}

    def first_publisher():
        with Session(engine) as session:
            session.execute(text("SET LOCAL lock_timeout = '5s'"))
            pids["first"] = session.scalar(text("SELECT pg_backend_pid()"))
            publish_release(session, first_id, reviewed=True, mode="synthetic")
            first_published.set()
            assert release_first.wait(10), "test did not release the first publisher"
            session.commit()

    def second_publisher():
        assert first_published.wait(10), "first publisher did not reach the lock"
        with Session(engine) as session:
            session.execute(text("SET LOCAL lock_timeout = '5s'"))
            pids["second"] = session.scalar(text("SELECT pg_backend_pid()"))
            second_started.set()
            publish_release(session, second_id, reviewed=True, mode="synthetic")
            session.commit()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(first_publisher)
        second = pool.submit(second_publisher)
        try:
            assert first_published.wait(5)
            assert second_started.wait(5)
            assert pids["first"] != pids["second"]
            deadline = monotonic() + 4
            blocked = False
            with engine.connect() as observer:
                while monotonic() < deadline:
                    blocked = pids["first"] in observer.scalar(
                        text("SELECT pg_blocking_pids(:pid)"), {"pid": pids["second"]},
                    )
                    if blocked:
                        break
                    sleep(0.01)
            assert blocked, "second publisher never waited on the first PostgreSQL connection"
        finally:
            release_first.set()
            first.result(timeout=10)
            second.result(timeout=10)

    # Read committed effects through a new connection, not either session's cache.
    with Session(engine) as check:
        rows = check.scalars(select(DatasetRelease).where(
            DatasetRelease.jurisdiction_id == jurisdiction_id,
        )).all()
        assert {row.id: row.status for row in rows} == {first_id: "retired", second_id: "active"}
        assert sum(row.status == "active" for row in rows) == 1
        assert all(row.published_at is not None for row in rows)


@pytest.mark.parametrize("different", ["project_type", "jurisdiction", "kind", "profile_key"])
def test_active_release_uniqueness_preserves_independent_scopes(db_session, different):
    first_city = Jurisdiction(slug="synthetic-" + uuid4().hex, name="SYNTHETIC A", state="CA")
    second_city = Jurisdiction(slug="synthetic-" + uuid4().hex, name="SYNTHETIC B", state="CA")
    db_session.add_all([first_city, second_city])
    db_session.flush()
    first = release(first_city.id, status="active")
    changes = {
        "project_type": {"project_type": "multifamily"},
        "jurisdiction": {"jurisdiction_id": second_city.id},
        "kind": {"kind": "reviewed_public"},
        "profile_key": {"profile_key": "synthetic-other"},
    }[different]
    second = release(**{"jurisdiction_id": first_city.id, "status": "active", **changes})
    db_session.add_all([first, second])
    db_session.flush()
    assert db_session.scalar(select(func.count()).select_from(DatasetRelease).where(
        DatasetRelease.id.in_([first.id, second.id]), DatasetRelease.status == "active",
    )) == 2
    with pytest.raises(IntegrityError) as error, db_session.begin_nested():
        db_session.add(release(first_city.id, status="active"))
        db_session.flush()
    assert error.value.orig.diag.constraint_name == "uq_active_release_scope"
