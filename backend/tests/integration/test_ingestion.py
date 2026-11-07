"""PostgreSQL ingestion contracts; every service test rolls back its outer transaction."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session

from clearpath.db.models import (
    CitationLink, DatasetRelease, IngestionRun, Jurisdiction, MilestoneTemplate,
    Pathway, Project, Requirement, SourcePassage, SourceSnapshot,
)
from clearpath.domain.errors import DomainError
from clearpath.ingestion.schemas import Manifest
from clearpath.ingestion.service import import_bundle
from clearpath.ingestion.validation import ValidatedBundle, validate_bundle, validate_manifest_dict

REPO = Path(__file__).resolve().parents[3]
SYNTHETIC = REPO / "backend/tests/fixtures/irvine_adu_synthetic/manifest.json"
CITIES = REPO / "lanes/2-clear-it/data/oc-cities.json"
CONTENT_MODELS = (
    DatasetRelease, SourceSnapshot, SourcePassage, Pathway, Requirement,
    MilestoneTemplate, CitationLink,
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
    row = Jurisdiction(slug="irvine-ca", name="Irvine", state="CA")
    session.add(row)
    session.flush()
    return row


@pytest.fixture
def bundle():
    return validate_bundle(SYNTHETIC)


def changed_bundle(bundle, **changes):
    data = bundle.manifest.model_dump(mode="json")
    data.update(changes)
    assert validate_manifest_dict(data) == []
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return ValidatedBundle(
        manifest=Manifest.model_validate(data),
        content_hash=sha256(canonical.encode("utf-8")).hexdigest(),
        manifest_path=bundle.manifest_path,
    )


def row_counts(session, models=CONTENT_MODELS):
    return {model.__tablename__: session.scalar(select(func.count()).select_from(model))
            for model in models}


def test_reimport_is_noop(session, jurisdiction, bundle):
    commits = []
    event.listen(session, "after_commit", lambda _session: commits.append(True))
    first = import_bundle(session, bundle)
    assert isinstance(first.release_id, UUID)
    assert first.no_op is False
    assert first.counts == {
        "dataset_releases": 1, "source_snapshots": 1, "source_passages": 3,
        "pathways": 1, "requirements": 3, "milestone_templates": 6, "citation_links": 10,
    }
    before = row_counts(session)
    second = import_bundle(session, bundle)
    assert second.release_id == first.release_id
    assert second.no_op is True
    assert second.counts == dict.fromkeys(first.counts, 0)
    assert row_counts(session) == before
    assert commits == []
    runs = session.scalars(select(IngestionRun).order_by(IngestionRun.started_at)).all()
    assert [run.status for run in runs] == ["ok", "no_op"]
    for run in runs:
        assert run.command == "import"
        assert run.manifest_path == "backend/tests/fixtures/irvine_adu_synthetic/manifest.json"
        assert run.release_id == first.release_id
        assert run.content_hash == bundle.content_hash
        assert run.error_codes == []
    assert runs[0].counts == first.counts
    assert runs[1].counts == second.counts
    release = session.get(DatasetRelease, first.release_id)
    assert release.status == "draft" and release.published_at is None
    assert release.jurisdiction_id == jurisdiction.id
    assert release.kind == bundle.manifest.kind
    assert release.fact_schema == {key: value.model_dump(mode="json")
                                   for key, value in bundle.manifest.fact_schema.items()}
    snapshot = session.scalars(select(SourceSnapshot)).one()
    assert snapshot.checked_at == datetime(2026, 11, 7, tzinfo=timezone.utc)
    passages = session.scalars(select(SourcePassage)).all()
    assert {p.manifest_passage_id for p in passages} == {p.id for p in bundle.manifest.passages}
    assert all(p.id != p.manifest_passage_id and p.snapshot_id == snapshot.id for p in passages)
    assert all(p.excerpt_hash == sha256(p.excerpt.encode("utf-8")).hexdigest() for p in passages)
    milestones = session.scalars(select(MilestoneTemplate).order_by(MilestoneTemplate.position)).all()
    for position, (row, source) in enumerate(zip(milestones, bundle.manifest.milestones, strict=True)):
        assert row.position == position
        assert row.requirement_keys == source.requirements
        assert row.predecessors == source.predecessors
        assert row.assumed_days == source.assumed_days.model_dump(mode="json")


def test_import_rejects_unknown_jurisdiction(session, bundle):
    before = row_counts(session, (*CONTENT_MODELS, IngestionRun))
    with pytest.raises(DomainError) as error:
        import_bundle(session, bundle)
    assert error.value.code == "unknown_jurisdiction"
    assert row_counts(session, (*CONTENT_MODELS, IngestionRun)) == before


def test_publish_retires_previous(session, jurisdiction, bundle):
    from clearpath.ingestion.service import publish_release

    commits = []
    event.listen(session, "after_commit", lambda _session: commits.append(True))
    first = import_bundle(session, bundle)
    active = publish_release(session, first.release_id, reviewed=True, mode="synthetic")
    assert active.status == "active"
    assert active.published_at.utcoffset().total_seconds() == 0
    original_published_at = active.published_at
    project = Project(
        project_label="Synthetic pinned project", project_type="adu", location={},
        jurisdiction_id=jurisdiction.id, affordability_goal="unspecified", state="active",
        release_id=first.release_id, pathway_key=bundle.manifest.pathways[0].key,
    )
    session.add(project)
    session.flush()
    other = import_bundle(session, changed_bundle(bundle, profile_key="other-synthetic-profile"))
    publish_release(session, other.release_id, reviewed=True, mode="synthetic")
    second = import_bundle(session, changed_bundle(bundle, curator_label="SYNTHETIC revision B"))
    replacement = publish_release(session, second.release_id, reviewed=True, mode="synthetic")
    session.expire_all()
    assert session.get(DatasetRelease, first.release_id).status == "retired"
    assert session.get(DatasetRelease, first.release_id).published_at == original_published_at
    assert session.get(DatasetRelease, other.release_id).status == "active"
    assert replacement.status == "active"
    assert session.get(Project, project.id).release_id == first.release_id
    first_ids = set(session.scalars(select(SourcePassage.id).where(SourcePassage.release_id == first.release_id)))
    second_ids = set(session.scalars(select(SourcePassage.id).where(SourcePassage.release_id == second.release_id)))
    assert first_ids.isdisjoint(second_ids)
    assert commits == []


@pytest.mark.parametrize("status", ["active", "retired"])
def test_publish_requires_draft(session, jurisdiction, bundle, status):
    from clearpath.ingestion.service import publish_release

    imported = import_bundle(session, bundle)
    release = session.get(DatasetRelease, imported.release_id)
    release.status = status
    session.flush()
    with pytest.raises(DomainError) as error:
        publish_release(session, release.id, reviewed=True, mode="synthetic")
    assert error.value.code == "release_not_draft"
    assert release.status == status


@pytest.mark.parametrize("reviewed,exists,code", [
    (False, True, "review_confirmation_required"),
    (True, False, "release_not_found"),
])
def test_publish_review_and_existence_guards(session, jurisdiction, bundle, reviewed, exists, code):
    from clearpath.ingestion.service import publish_release

    imported = import_bundle(session, bundle)
    with pytest.raises(DomainError) as error:
        publish_release(session, imported.release_id if exists else uuid4(), reviewed=reviewed, mode="synthetic")
    assert error.value.code == code
    assert session.get(DatasetRelease, imported.release_id).status == "draft"


@pytest.mark.parametrize("kind,mode", [("synthetic", "public"), ("reviewed_public", "synthetic")])
def test_publish_kind_mismatch(session, jurisdiction, bundle, kind, mode):
    from clearpath.ingestion.service import publish_release

    imported = import_bundle(session, changed_bundle(bundle, kind=kind))
    with pytest.raises(DomainError) as error:
        publish_release(session, imported.release_id, reviewed=True, mode=mode)
    assert error.value.code == "release_kind_mismatch"
    assert session.get(DatasetRelease, imported.release_id).status == "draft"


@pytest.mark.parametrize("owner_type", ["pathway", "requirement", "milestone", "published_clock"])
def test_publish_rejects_unreviewed(session, jurisdiction, bundle, owner_type):
    from clearpath.ingestion.service import publish_release

    data = bundle.manifest.model_dump(mode="json")
    unreviewed = data["passages"][2]["id"]
    if owner_type == "published_clock":
        owner = data["milestones"][0]
        owner["citations"] = []
        owner["published_clock"] = {"text": "SYNTHETIC display-only clock", "citations": [unreviewed, unreviewed]}
    else:
        collection = {"pathway": "pathways", "requirement": "requirements", "milestone": "milestones"}[owner_type]
        owner = data[collection][0]
        owner["citations"] = [unreviewed, unreviewed]
    imported = import_bundle(session, changed_bundle(bundle, **data))
    with pytest.raises(DomainError) as error:
        publish_release(session, imported.release_id, reviewed=True, mode="synthetic")
    assert error.value.code == "unreviewed_evidence"
    assert error.value.details["owner_keys"] == [owner["key"]]
    release = session.get(DatasetRelease, imported.release_id)
    assert release.status == "draft" and release.published_at is None


@pytest.mark.parametrize("empty", ["pathways", "requirements"])
def test_publish_rejects_empty_release(session, jurisdiction, bundle, empty):
    from clearpath.ingestion.service import publish_release

    public = changed_bundle(bundle, kind="reviewed_public")
    previous = import_bundle(session, public)
    publish_release(session, previous.release_id, reviewed=True, mode="public")
    changes = {"requirements": [], "milestones": []}
    if empty == "pathways":
        changes["pathways"] = []
    imported = import_bundle(session, changed_bundle(public, **changes))
    with pytest.raises(DomainError) as error:
        publish_release(session, imported.release_id, reviewed=True, mode="public")
    assert error.value.code == "empty_release"
    assert session.get(DatasetRelease, imported.release_id).status == "draft"
    assert session.get(DatasetRelease, previous.release_id).status == "active"


def test_citation_links_match_cited_passages(session, jurisdiction, bundle):
    data = bundle.manifest.model_dump(mode="json")
    first, second = [p["id"] for p in data["passages"][:2]]
    data["pathways"][0]["citations"] = [first, first]
    data["requirements"][0]["citations"] = [first, second, second]
    milestone = data["milestones"][0]
    milestone["citations"] = [first, first]
    milestone["published_clock"] = {"text": "SYNTHETIC clock", "citations": [first, second, second]}
    data["milestones"][1]["citations"] = []
    data["milestones"][1]["published_clock"] = {"text": "SYNTHETIC clock only", "citations": [first]}
    data["milestones"][2]["assumed_days"] = None
    data["conflicts"] = [{"rule_keys": [data["pathways"][0]["key"]],
                          "source_keys": [data["sources"][0]["key"]], "summary": "SYNTHETIC conflict"}]
    changed = changed_bundle(bundle, **data)
    imported = import_bundle(session, changed)
    expected = set()
    for owner_type, collection in (("pathway", "pathways"), ("requirement", "requirements"), ("milestone", "milestones")):
        for owner in data[collection]:
            citations = owner["citations"] + ((owner.get("published_clock") or {}).get("citations", []))
            expected.update((owner_type, owner["key"], UUID(passage)) for passage in citations)
    actual = session.execute(select(CitationLink.owner_type, CitationLink.owner_key, SourcePassage.manifest_passage_id)
                             .join(SourcePassage, CitationLink.passage_id == SourcePassage.id)
                             .where(CitationLink.release_id == imported.release_id,
                                    SourcePassage.release_id == imported.release_id)).all()
    assert set(actual) == expected
    assert len(actual) == imported.counts["citation_links"] == len(expected)
    stored = session.scalar(select(MilestoneTemplate).where(MilestoneTemplate.key == milestone["key"]))
    assert stored.published_clock == milestone["published_clock"]
    assert session.get(DatasetRelease, imported.release_id).conflicts == data["conflicts"]
    requirements = session.scalars(select(Requirement)).all()
    assert all(row.pathway_keys == data["requirements"][0]["pathways"] for row in requirements)


def test_import_database_error_rolls_back_whole_release(session, jurisdiction, bundle, monkeypatch):
    from sqlalchemy.exc import IntegrityError
    import clearpath.ingestion.service as service

    # Force a real PostgreSQL duplicate primary key in the second passage.
    monkeypatch.setattr(service, "uuid4", lambda: UUID(int=1))
    with pytest.raises(IntegrityError):
        import_bundle(session, bundle)
    session.rollback()  # The caller, not the service, owns failure rollback.
    assert row_counts(session, (*CONTENT_MODELS, IngestionRun)) == dict.fromkeys(
        [model.__tablename__ for model in (*CONTENT_MODELS, IngestionRun)], 0,
    )



def test_import_cities_idempotent(session):
    from clearpath.ingestion.service import import_cities

    commits = []
    event.listen(session, "after_commit", lambda _session: commits.append(True))
    assert import_cities(session, CITIES) == 34
    rows = session.scalars(select(Jurisdiction).order_by(Jurisdiction.slug)).all()
    assert len(rows) == 34
    before = [(row.id, row.slug, row.name, row.state, row.timezone,
               row.permit_page_url, row.adu_checklist_url, row.fee_schedule_url, row.checked_at) for row in rows]
    assert all(row.state == "CA" and row.timezone == "America/Los_Angeles" for row in rows)
    assert all(row.permit_page_url is None and row.adu_checklist_url is None
               and row.fee_schedule_url is None and row.checked_at is None for row in rows)
    assert import_cities(session, CITIES) == 34
    session.expire_all()
    after = [(row.id, row.slug, row.name, row.state, row.timezone,
              row.permit_page_url, row.adu_checklist_url, row.fee_schedule_url, row.checked_at)
             for row in session.scalars(select(Jurisdiction).order_by(Jurisdiction.slug))]
    assert after == before
    irvine = session.scalar(select(Jurisdiction).where(Jurisdiction.slug == "irvine-ca"))
    irvine.permit_page_url = "https://example.org/synthetic-checked"
    irvine.adu_checklist_url = "https://example.org/synthetic-checklist"
    irvine.fee_schedule_url = "https://example.org/synthetic-fees"
    irvine.checked_at = datetime(2026, 11, 7, tzinfo=timezone.utc)
    session.flush()
    assert import_cities(session, CITIES) == 34
    session.refresh(irvine)
    assert irvine.permit_page_url == "https://example.org/synthetic-checked"
    assert irvine.adu_checklist_url == "https://example.org/synthetic-checklist"
    assert irvine.fee_schedule_url == "https://example.org/synthetic-fees"
    assert irvine.checked_at == datetime(2026, 11, 7, tzinfo=timezone.utc)
    assert commits == []


def test_import_cities_updates_non_null_fields_and_strips_punctuation(session, tmp_path):
    from clearpath.ingestion.service import import_cities

    path = tmp_path / "synthetic-cities.json"
    data = {"cities": [{"name": "SYNTHETIC St. John's", "permit_page": "https://example.org/synthetic",
                        "adu_checklist": None, "fee_schedule": None, "checked": "2026-11-07"}]}
    path.write_text(json.dumps(data))
    assert import_cities(session, path) == 1
    city = session.scalars(select(Jurisdiction)).one()
    assert city.slug == "synthetic-st-johns-ca"
    assert city.permit_page_url == "https://example.org/synthetic"
    assert city.checked_at == datetime(2026, 11, 7, tzinfo=timezone.utc)
    data["cities"][0].update(permit_page=None, adu_checklist="https://example.org/synthetic-update", checked=None)
    path.write_text(json.dumps(data))
    assert import_cities(session, path) == 1
    session.refresh(city)
    assert city.permit_page_url == "https://example.org/synthetic"
    assert city.adu_checklist_url == "https://example.org/synthetic-update"
    assert city.checked_at == datetime(2026, 11, 7, tzinfo=timezone.utc)
    assert session.scalar(select(func.count()).select_from(Jurisdiction)) == 1



def test_dry_run_writes_nothing(session, monkeypatch):
    from typer.testing import CliRunner
    from clearpath.cli import app

    before = row_counts(session, (*CONTENT_MODELS, IngestionRun, Jurisdiction))
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://unused:unused@invalid.invalid:1/no_database?connect_timeout=1")
    monkeypatch.delenv("CLEARPATH_API_KEY", raising=False)
    monkeypatch.chdir(REPO / "backend")
    result = CliRunner().invoke(app, ["data", "import", "--manifest", "tests/fixtures/irvine_adu_synthetic/manifest.json", "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "dry_run=true" in result.stdout
    counts_line = next(line for line in result.stdout.splitlines() if line.startswith("counts="))
    assert json.loads(counts_line.removeprefix("counts=")) == {
        "dataset_releases": 1, "source_snapshots": 1, "source_passages": 3,
        "pathways": 1, "requirements": 3, "milestone_templates": 6, "citation_links": 10,
    }
    assert result.stderr == ""
    assert row_counts(session, (*CONTENT_MODELS, IngestionRun, Jurisdiction)) == before


def test_cli_validation_errors_are_sanitized(monkeypatch, tmp_path):
    from typer.testing import CliRunner
    from clearpath.cli import app

    outside = tmp_path / "outside.json"
    outside.write_text(SYNTHETIC.read_text())
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://unused:unused@invalid.invalid:1/no_database?connect_timeout=1")
    result = CliRunner().invoke(app, ["data", "import", "--manifest", str(outside), "--dry-run"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == "path_outside_bundle: $\n"
    assert "Traceback" not in result.output
    assert str(tmp_path) not in result.output


def test_cli_debug_preserves_exception(tmp_path):
    from typer.testing import CliRunner
    from clearpath.cli import app
    from clearpath.ingestion.validation import BundleValidationError

    result = CliRunner().invoke(app, ["--debug", "data", "import", "--manifest", str(tmp_path / "outside.json"), "--dry-run"])
    assert result.exit_code == 1
    assert isinstance(result.exception, BundleValidationError)



@pytest.fixture
def cli_database(settings, monkeypatch):
    """CLI commits are tested in a disposable DB, never the transactional test DB."""
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import text
    from sqlalchemy.engine import make_url
    from clearpath.db.session import get_engine

    url = make_url(settings.database_url)
    assert url.database == "clearpath_test"
    name = "clearpath_ingestion_cli_" + uuid4().hex
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    cli_url = url.set(database=name).render_as_string(hide_password=False)
    engine = create_engine(cli_url)
    try:
        monkeypatch.setenv("DATABASE_URL", cli_url)
        monkeypatch.setenv("CLEARPATH_MODE", "synthetic")
        monkeypatch.setenv("CLEARPATH_API_KEY", "test-key")
        command.upgrade(Config(str(REPO / "backend/alembic.ini")), "head")
        monkeypatch.delenv("CLEARPATH_API_KEY")
        yield engine
    finally:
        get_engine(cli_url).dispose()
        engine.dispose()
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        admin.dispose()


def test_cli_import_publish_happy_path(cli_database, monkeypatch, tmp_path):
    from typer.testing import CliRunner
    from clearpath.cli import app

    runner = CliRunner()
    monkeypatch.chdir(tmp_path)  # Default registry path must not depend on CWD.
    missing_city = runner.invoke(app, ["data", "import", "--manifest", str(SYNTHETIC)])
    assert missing_city.exit_code == 1
    assert missing_city.stderr == "unknown_jurisdiction: jurisdiction\n"
    cities = runner.invoke(app, ["data", "import-cities"])
    assert cities.exit_code == 0, cities.output
    assert cities.stdout == "cities=34\n"
    imported = runner.invoke(app, ["data", "import", "--manifest", str(SYNTHETIC)])
    assert imported.exit_code == 0, imported.output
    release_id = UUID(next(line.removeprefix("release_id=") for line in imported.stdout.splitlines()
                           if line.startswith("release_id=")))
    assert "no_op=false" in imported.stdout
    with Session(cli_database) as check:
        assert check.get(DatasetRelease, release_id).status == "draft"
        assert check.scalar(select(func.count()).select_from(Jurisdiction)) == 34
        before = row_counts(check)
        assert check.scalars(select(IngestionRun)).one().status == "ok"
    unconfirmed = runner.invoke(app, ["data", "publish", "--release", str(release_id)])
    assert unconfirmed.exit_code == 1
    assert unconfirmed.stderr == "review_confirmation_required: reviewed\n"
    published = runner.invoke(app, ["data", "publish", "--release", str(release_id), "--reviewed"])
    assert published.exit_code == 0, published.output
    assert f"release_id={release_id}" in published.stdout
    with Session(cli_database) as check:
        release = check.get(DatasetRelease, release_id)
        assert release.status == "active"
        published_at = release.published_at
        assert published_at.utcoffset().total_seconds() == 0
    again = runner.invoke(app, ["data", "import", "--manifest", str(SYNTHETIC)])
    assert again.exit_code == 0, again.output
    assert f"release_id={release_id}" in again.stdout and "no_op=true" in again.stdout
    repeated = runner.invoke(app, ["data", "publish", "--release", str(release_id), "--reviewed"])
    assert repeated.exit_code == 0, repeated.output
    assert "already active" in repeated.stdout
    with Session(cli_database) as check:
        assert row_counts(check) == before
        assert check.get(DatasetRelease, release_id).published_at == published_at
        assert check.scalars(select(IngestionRun.status).order_by(IngestionRun.started_at)).all() == ["ok", "no_op"]
    # The already-active convenience must not bypass operating-mode isolation.
    monkeypatch.setenv("CLEARPATH_MODE", "public")
    wrong_mode = runner.invoke(app, ["data", "publish", "--release", str(release_id), "--reviewed"])
    assert wrong_mode.exit_code == 1
    assert wrong_mode.stderr == "release_kind_mismatch: kind\n"
    monkeypatch.setenv("CLEARPATH_MODE", "synthetic")
    with Session(cli_database) as check:
        release = check.get(DatasetRelease, release_id)
        assert release.status == "active"
        release.status = "retired"
        check.commit()
    retired = runner.invoke(app, ["data", "publish", "--release", str(release_id), "--reviewed"])
    assert retired.exit_code == 1
    assert retired.stderr == "release_not_draft: release\n"
    with Session(cli_database) as check:
        assert check.get(DatasetRelease, release_id).status == "retired"


def test_cli_rolls_back_database_errors(cli_database, monkeypatch):
    from typer.testing import CliRunner
    from clearpath.cli import app
    import clearpath.ingestion.service as service

    runner = CliRunner()
    assert runner.invoke(app, ["data", "import-cities", "--path", str(CITIES)]).exit_code == 0
    monkeypatch.setattr(service, "uuid4", lambda: UUID(int=1))
    result = runner.invoke(app, ["data", "import", "--manifest", str(SYNTHETIC)])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == "database_error: $\n"
    assert "Traceback" not in result.output
    with Session(cli_database) as check:
        assert row_counts(check, (*CONTENT_MODELS, IngestionRun)) == dict.fromkeys(
            [model.__tablename__ for model in (*CONTENT_MODELS, IngestionRun)], 0,
        )


def test_cli_configuration_errors_are_sanitized(monkeypatch):
    from typer.testing import CliRunner
    from clearpath.cli import app

    monkeypatch.setenv("CLEARPATH_MODE", "invalid-mode-must-not-echo")
    result = CliRunner().invoke(app, ["data", "import", "--manifest", str(SYNTHETIC)])
    assert result.exit_code == 1
    assert result.stderr == "configuration_invalid: $\n"
    assert result.stdout == ""
    assert "invalid-mode-must-not-echo" not in result.output


def test_cli_rejects_invalid_release_before_connecting(monkeypatch):
    from typer.testing import CliRunner
    from clearpath.cli import app

    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://unused:unused@invalid.invalid:1/no_database?connect_timeout=1")
    result = CliRunner().invoke(app, ["data", "publish", "--release", "invalid-uuid-must-not-echo", "--reviewed"])
    assert result.exit_code == 1
    assert result.stderr == "schema_invalid: release\n"
    assert result.stdout == ""
    assert "invalid-uuid-must-not-echo" not in result.output



def test_synthetic_demo_assumptions_remain_labeled(bundle):
    expected = {
        "application_preparation": (7, 21), "submission": (1, 3),
        "completeness_review": (10, 30), "plan_review": (20, 60),
        "fee_payment_readiness": (3, 10), "permit_issuance": (1, 5),
    }
    assert {m.key: (m.assumed_days.min, m.assumed_days.max) for m in bundle.manifest.milestones} == expected
    assert all(m.assumed_days.label == "ASSUMPTION" and m.assumed_days.rationale == "synthetic test value"
               for m in bundle.manifest.milestones)


def test_make_seed_demo_is_idempotent(cli_database):
    import subprocess

    command = ["make", "--no-print-directory",
               "DATABASE_URL=" + cli_database.url.render_as_string(hide_password=False), "seed-demo"]
    first = subprocess.run(command, cwd=REPO, capture_output=True, text=True, timeout=90)
    assert first.returncode == 0, first.stdout + first.stderr
    assert "no_op=false" in first.stdout and "status=active" in first.stdout
    with Session(cli_database) as check:
        before = row_counts(check)
        release = check.scalars(select(DatasetRelease)).one()
        assert release.status == "active" and release.kind == "synthetic"
        release_id, published_at = release.id, release.published_at
        assert check.scalar(select(func.count()).select_from(Jurisdiction)) == 34
    again = subprocess.run(command, cwd=REPO, capture_output=True, text=True, timeout=90)
    assert again.returncode == 0, again.stdout + again.stderr
    assert "no_op=true" in again.stdout and "already active" in again.stdout
    with Session(cli_database) as check:
        assert row_counts(check) == before
        assert check.get(DatasetRelease, release_id).published_at == published_at
        assert check.scalars(select(IngestionRun.status).order_by(IngestionRun.started_at)).all() == ["ok", "no_op"]
