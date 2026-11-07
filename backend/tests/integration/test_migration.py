from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url


TABLES = {
    "jurisdictions", "dataset_releases", "source_snapshots", "source_passages",
    "pathways", "requirements", "milestone_templates", "citation_links",
    "ingestion_runs", "projects", "project_requirements", "project_milestones", "project_events",
}


def test_migration_creates_schema(settings, monkeypatch, test_database_name):
    # Isolate DDL from all transactional tests (and never reset the dev database).
    url = make_url(settings.database_url)
    assert url.database == test_database_name
    name = "clearpath_migration_" + uuid4().hex
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    engine = create_engine(url.set(database=name))
    try:
        monkeypatch.setenv("DATABASE_URL", url.set(database=name).render_as_string(hide_password=False))
        config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert TABLES <= set(inspect(connection).get_table_names())
            assert connection.execute(text("SELECT extname FROM pg_extension WHERE extname='vector'")).scalar_one() == "vector"
            head = ScriptDirectory.from_config(config).get_current_head()
            assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == head
        command.upgrade(config, "head")
        command.check(config)
        command.downgrade(config, "base")
        with engine.connect() as connection:
            assert not TABLES.intersection(inspect(connection).get_table_names())
            assert connection.execute(text("SELECT extname FROM pg_extension WHERE extname='vector'")).scalar_one() == "vector"
        command.upgrade(config, "head")
    finally:
        engine.dispose()
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        admin.dispose()
