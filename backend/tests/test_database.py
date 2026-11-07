"""Migrations must build a usable PostgreSQL dataset schema, never project tables."""

from conftest import migrate
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text

from clearpath.api.app import create_app
from clearpath.core.config import Settings


def test_migration_installs_dataset_schema_and_real_vector(migrated):
    with migrated.connect() as connection:
        assert connection.scalar(text("SELECT extversion FROM pg_extension WHERE extname='vector'"))
        assert connection.scalar(text("SELECT '[1,2,3]'::vector <-> '[1,2,4]'::vector")) == 1.0
        assert int(connection.scalar(text("SHOW server_version_num"))) >= 170000
    assert set(inspect(migrated).get_table_names()) == {
        "alembic_version",
        "jurisdictions",
        "source_snapshots",
        "source_passages",
        "ingestion_runs",
        "dataset_releases",
        "pathways",
        "requirements",
        "milestone_templates",
        "pathway_citations",
        "requirement_citations",
        "milestone_citations",
    }
    migrate(migrated)  # Repeat upgrade is a no-op.


def test_readiness_distinguishes_unmigrated_from_empty_dataset(database):
    config = Settings(
        database_url=database.url.render_as_string(hide_password=False),
        api_key="test-only-" + "a" * 40,
    )
    with TestClient(create_app(config)) as client:
        assert client.get("/health/live").status_code == 200
        before = client.get("/health/ready")
        assert before.status_code == 503
        assert before.json()["error"]["code"] == "not_ready"
        migrate(database)
        after = client.get("/health/ready")
        assert after.status_code == 200
        assert after.json() == {
            "status": "ready",
            "data_mode": "public",
            "dataset_available": False,
        }


def test_active_uniqueness_is_per_jurisdiction_type_and_profile(migrated):
    import pytest
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import Session

    from clearpath.db.models import DatasetRelease, Jurisdiction

    with Session(migrated) as session, session.begin():
        city = Jurisdiction(
            slug="test-city",
            name="Synthetic test jurisdiction",
            state="CA",
            timezone="America/Los_Angeles",
        )
        session.add(city)
        session.flush()

        def release(project_type, profile, checksum, status="active"):
            return DatasetRelease(
                jurisdiction_id=city.id,
                project_type=project_type,
                profile_key=profile,
                content_hash=checksum * 64,
                status=status,
                data_classification="synthetic",
                schema_version=1,
                fact_schema={},
                normalized_manifest={},
                curator_label="test",
            )

        session.add(release("adu", "standard", "a"))
        session.flush()
        with pytest.raises(IntegrityError), session.begin_nested():
            session.add(release("adu", "standard", "b"))
            session.flush()
        # These are distinct coverage keys, or non-active history: all must remain possible.
        session.add_all(
            [
                release("multifamily", "standard", "c"),
                release("adu", "detached", "d"),
                release("adu", "standard", "e", "draft"),
                release("adu", "standard", "f", "retired"),
            ]
        )
        second_city = Jurisdiction(
            slug="another-test-city",
            name="Synthetic other jurisdiction",
            state="CA",
            timezone="America/Los_Angeles",
        )
        session.add(second_city)
        session.flush()
        other = release("adu", "standard", "b")
        other.jurisdiction_id = second_city.id
        session.add(other)
        session.flush()


def test_sources_and_citation_foreign_keys_preserve_evidence(migrated):
    from datetime import UTC, datetime
    from uuid import uuid4

    import pytest
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import Session

    from clearpath.db.models import (
        DatasetRelease,
        Jurisdiction,
        MilestoneCitation,
        MilestoneTemplate,
        Pathway,
        PathwayCitation,
        Requirement,
        RequirementCitation,
        SourcePassage,
        SourceSnapshot,
    )

    now = datetime.now(UTC)
    with Session(migrated) as session, session.begin():
        source = SourceSnapshot(
            source_key="technical-test",
            canonical_url="https://example.invalid",
            title="Synthetic technical fixture",
            publisher="Test only",
            authority_type="synthetic",
            mime_type="text/plain",
            fetched_at=now,
            checked_at=now,
            sha256="a" * 64,
            local_artifact_key="technical/source.txt",
            extraction_status="parsed",
            review_status="reviewed",
        )
        session.add(source)
        session.flush()
        with pytest.raises(IntegrityError), session.begin_nested():
            duplicate = SourceSnapshot(
                **{
                    column.name: getattr(source, column.name)
                    for column in SourceSnapshot.__table__.columns
                    if column.name != "id"
                }
            )
            session.add(duplicate)
            session.flush()
        passage = SourcePassage(
            snapshot_id=source.id,
            locator="heading:technical-fixture",
            excerpt="Synthetic technical fixture; no regulatory facts.",
            excerpt_hash="b" * 64,
        )
        city = Jurisdiction(
            slug="technical-city",
            name="Synthetic jurisdiction",
            state="CA",
            timezone="America/Los_Angeles",
            boundary_snapshot_id=source.id,
        )
        session.add_all([passage, city])
        session.flush()
        release = DatasetRelease(
            jurisdiction_id=city.id,
            project_type="multifamily",
            profile_key="technical",
            content_hash="c" * 64,
            status="draft",
            data_classification="synthetic",
            schema_version=1,
            fact_schema={},
            normalized_manifest={},
            curator_label="test",
        )
        session.add(release)
        session.flush()
        pathway = Pathway(
            release_id=release.id,
            key="technical-path",
            title="Synthetic path",
            applicability={"always": True},
            explanation="Test only",
        )
        requirement = Requirement(
            release_id=release.id,
            key="technical-requirement",
            pathway_keys=["technical-path"],
            kind="document",
            title="Test",
            description="Synthetic fixture",
            applicability={"always": True},
            required_for_preparation=True,
        )
        session.add_all([pathway, requirement])
        session.flush()
        milestone = MilestoneTemplate(
            release_id=release.id,
            pathway_key=pathway.key,
            key="technical-milestone",
            title="Synthetic fixture",
            predecessor_keys=[],
            requirement_keys=[requirement.key],
        )
        session.add(milestone)
        session.flush()
        assert release.created_at.utcoffset().total_seconds() == 0
        for owner, owner_id, citation_type in (
            ("pathway_id", pathway.id, PathwayCitation),
            ("requirement_id", requirement.id, RequirementCitation),
            ("milestone_id", milestone.id, MilestoneCitation),
        ):
            with pytest.raises(IntegrityError), session.begin_nested():
                session.add(citation_type(**{owner: owner_id, "passage_id": uuid4()}))
                session.flush()
            session.add(citation_type(**{owner: owner_id, "passage_id": passage.id}))
            session.flush()
        with pytest.raises(IntegrityError), session.begin_nested():
            session.execute(text("DELETE FROM source_passages WHERE id=:id"), {"id": passage.id})
        with pytest.raises(IntegrityError), session.begin_nested():
            session.execute(text("DELETE FROM source_snapshots WHERE id=:id"), {"id": source.id})


def test_sessions_leave_transaction_ownership_with_the_caller(migrated, monkeypatch):
    from sqlalchemy.orm import Session

    from clearpath.db import session as sessions
    from clearpath.db.models import Jurisdiction

    config = Settings(
        database_url=migrated.url.render_as_string(hide_password=False),
        api_key="test-only-" + "a" * 40,
    )
    factory = sessions.create_session_factory(config)
    monkeypatch.setattr(sessions, "default_session_factory", lambda: factory)
    try:
        dependency = sessions.get_session()
        session = next(dependency)
        session.add(Jurisdiction(slug="uncommitted", name="Synthetic", state="CA", timezone="UTC"))
        session.flush()
        dependency.close()
        with Session(migrated) as verify:
            assert verify.scalar(text("SELECT count(*) FROM jurisdictions")) == 0
        dependency = sessions.get_session()
        session = next(dependency)
        with session.begin():
            session.add(
                Jurisdiction(slug="committed", name="Synthetic", state="CA", timezone="UTC")
            )
        dependency.close()
        with Session(migrated) as verify:
            assert verify.scalar(text("SELECT slug FROM jurisdictions")) == "committed"
    finally:
        sessions.dispose_session_factory(factory)


def test_readiness_reports_only_active_dataset_in_selected_mode(migrated):
    from sqlalchemy.orm import Session

    from clearpath.db.models import DatasetRelease, Jurisdiction

    with Session(migrated) as session, session.begin():
        city = Jurisdiction(slug="test-city", name="Synthetic", state="CA", timezone="UTC")
        session.add(city)
        session.flush()
        release = DatasetRelease(
            jurisdiction_id=city.id,
            project_type="adu",
            profile_key="test",
            content_hash="a" * 64,
            status="draft",
            data_classification="synthetic",
            schema_version=1,
            fact_schema={},
            normalized_manifest={},
            curator_label="test",
        )
        session.add(release)
        session.flush()
        release_id = release.id
    values = {
        "database_url": migrated.url.render_as_string(hide_password=False),
        "api_key": "test-only-" + "a" * 40,
    }
    with (
        TestClient(create_app(Settings(**values, data_mode="public"))) as public,
        TestClient(create_app(Settings(**values, data_mode="synthetic"))) as synthetic,
    ):
        assert synthetic.get("/health/ready").json()["dataset_available"] is False
        with Session(migrated) as session, session.begin():
            session.get(DatasetRelease, release_id).status = "active"
        assert synthetic.get("/health/ready").json()["dataset_available"] is True
        assert public.get("/health/ready").json()["dataset_available"] is False
        with Session(migrated) as session, session.begin():
            session.get(DatasetRelease, release_id).status = "retired"
        assert synthetic.get("/health/ready").json()["dataset_available"] is False


def test_orm_and_explicit_migration_expose_the_same_schema(migrated):
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext

    from clearpath.db.models import Base

    with migrated.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        assert compare_metadata(context, Base.metadata) == []


def test_extraction_states_are_distinct_from_review_states(migrated):
    import pytest
    from sqlalchemy.exc import IntegrityError

    with migrated.begin() as connection:
        statement = text("""
            INSERT INTO source_snapshots
                (source_key, canonical_url, title, publisher, authority_type, mime_type,
                 fetched_at, checked_at, sha256, local_artifact_key,
                 extraction_status, review_status)
            VALUES (:key, 'https://example.invalid', 'Synthetic technical fixture', 'Test',
                    'synthetic', 'text/plain', now(), now(), :hash, 'test/source.txt',
                    :extraction, :review)
        """)
        for index, extraction in enumerate(["pending", "parsed", "needs_review", "failed"]):
            connection.execute(
                statement,
                {
                    "key": f"technical-{index}",
                    "hash": str(index) * 64,
                    "extraction": extraction,
                    "review": "pending",
                },
            )
        for index, invalid in enumerate(["succeeded", "reviewed"]):
            with pytest.raises(IntegrityError), connection.begin_nested():
                connection.execute(
                    statement,
                    {
                        "key": f"invalid-{index}",
                        "hash": "a" * 64,
                        "extraction": invalid,
                        "review": "pending",
                    },
                )
        with pytest.raises(IntegrityError), connection.begin_nested():
            connection.execute(
                statement,
                {
                    "key": "invalid-review",
                    "hash": "b" * 64,
                    "extraction": "parsed",
                    "review": "parsed",
                },
            )
        assert (
            connection.scalar(
                text("SELECT count(*) FROM source_snapshots WHERE review_status='pending'")
            )
            == 4
        )


def test_forward_migration_preserves_legacy_snapshot_and_has_coherent_downgrade(database):
    import os
    import subprocess

    from conftest import BACKEND

    migrate(database, "0001_dataset_foundation")
    with database.begin() as connection:
        snapshot_id = connection.scalar(
            text("""
            INSERT INTO source_snapshots
                (source_key, canonical_url, title, publisher, authority_type, mime_type,
                 fetched_at, checked_at, sha256, local_artifact_key,
                 extraction_status, review_status)
            VALUES ('legacy-technical', 'https://example.invalid', 'Synthetic fixture', 'Test',
                    'synthetic', 'text/plain', now(), now(), repeat('a',64), 'technical/source.txt',
                    'succeeded', 'pending') RETURNING id
        """)
        )
    migrate(database)
    with database.connect() as connection:
        assert connection.execute(
            text("SELECT extraction_status, review_status FROM source_snapshots WHERE id=:id"),
            {"id": snapshot_id},
        ).one() == ("parsed", "pending")
    environment = os.environ | {
        "DATABASE_URL": database.url.render_as_string(hide_password=False),
        "CLEARPATH_DATABASE_URL": database.url.render_as_string(hide_password=False),
        "CLEARPATH_API_KEY": "test-only-" + "a" * 40,
    }
    result = subprocess.run(
        [
            str(BACKEND / ".venv/bin/alembic"),
            "-c",
            str(BACKEND / "alembic.ini"),
            "downgrade",
            "0001_dataset_foundation",
        ],
        env=environment,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    with database.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT extraction_status FROM source_snapshots WHERE id=:id"),
                {"id": snapshot_id},
            )
            == "succeeded"
        )
    migrate(database)


def test_readiness_uses_current_alembic_heads_instead_of_hardcoded_revision(
    migrated, tmp_path, monkeypatch
):
    import shutil

    from alembic import command
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from conftest import BACKEND

    from clearpath.api import app as app_module

    scripts = tmp_path / "migrations"
    shutil.copytree(BACKEND / "migrations", scripts)
    previous_head = ScriptDirectory(str(scripts)).get_current_head()
    (scripts / "versions/future_noop.py").write_text(
        f"revision = 'test_future_revision'\ndown_revision = {previous_head!r}\n"
        "def upgrade():\n    pass\ndef downgrade():\n    pass\n"
    )
    monkeypatch.setattr(app_module, "MIGRATIONS_PATH", scripts, raising=False)
    url = migrated.url.render_as_string(hide_password=False)
    key = "test-only-" + "a" * 40
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("CLEARPATH_DATABASE_URL", url)
    monkeypatch.setenv("CLEARPATH_API_KEY", key)
    config = Config()
    config.set_main_option("script_location", str(scripts))
    with TestClient(create_app(Settings(database_url=url, api_key=key))) as client:
        assert client.get("/health/ready").status_code == 503
        command.upgrade(config, "head")
        assert client.get("/health/ready").status_code == 200
