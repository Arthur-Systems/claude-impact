"""SQLAlchemy Core tables for projects (spec §5). Mirrors the P5 migration.

Person 3's ``0001_initial`` migration creates these four tables (lean columns);
Person 5's migration ``p5_0001_project_tables`` only ADDS the extra columns below.
Column names follow Person 3's schema (``location``, ``jurisdiction_id``,
``milestone_key``, ``status``). Kept in Person 5's own MetaData so this module
imports without Person 3's ORM models; ``P5_OWNED_COLUMNS`` lists what P5's
migration adds so Person 3's ``alembic check`` can ignore it (``include_p5_object``).

Release content is immutable after staging, so activation copies the pinned
release's requirement/milestone definitions into project rows. Timeline reads
therefore need only these four tables. No applicant name, contact data or
uploaded documents are stored, ever.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

metadata = sa.MetaData()

projects = sa.Table(
    "projects",
    metadata,
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("project_label", sa.String(80), nullable=False),
    sa.Column("project_type", sa.Text, nullable=False),
    sa.Column("subtype", sa.Text),
    sa.Column("jurisdiction", sa.Text),  # P5: slug as given by the client
    sa.Column("jurisdiction_id", UUID(as_uuid=True)),  # P3: FK jurisdictions.id, resolved from the slug
    sa.Column("location", JSONB, nullable=False),  # API field: declared_location
    sa.Column("proposed_unit_count", sa.Integer),
    sa.Column("affordability_goal", sa.Text, nullable=False),
    sa.Column("affordable_unit_count_goal", sa.Integer),
    sa.Column("state", sa.Text, nullable=False),
    sa.Column("coverage_status", sa.Text, nullable=False),
    sa.Column("coverage_reason", sa.Text),
    sa.Column("release_id", UUID(as_uuid=True)),
    sa.Column("release_summary", JSONB),
    sa.Column("pathway_key", sa.Text),
    sa.Column("pathway_summary", JSONB),
    sa.Column("rule_facts", JSONB, nullable=False),
    sa.Column("missing_fact_keys", JSONB, nullable=False),
    sa.Column("location_evidence", JSONB),
    sa.Column("source_conflicts", JSONB, nullable=False),
    sa.Column("citations", JSONB, nullable=False),
    sa.Column("warnings", JSONB, nullable=False),
    sa.Column("revision", sa.Integer, nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

project_requirements = sa.Table(
    "project_requirements",
    metadata,
    sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id"), primary_key=True),
    sa.Column("requirement_key", sa.Text, primary_key=True),
    sa.Column("position", sa.Integer, nullable=False),
    sa.Column("kind", sa.Text, nullable=False),
    sa.Column("title", sa.Text, nullable=False),
    sa.Column("applicability", sa.Text, nullable=False),
    sa.Column("missing_fact_keys", JSONB, nullable=False),
    sa.Column("required_for_preparation", sa.Boolean, nullable=False),
    sa.Column("citation_ids", JSONB, nullable=False),
    sa.Column("status", sa.Text, nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

project_milestones = sa.Table(
    "project_milestones",
    metadata,
    sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id"), primary_key=True),
    sa.Column("milestone_key", sa.Text, primary_key=True),
    sa.Column("position", sa.Integer, nullable=False),
    sa.Column("title", sa.Text, nullable=False),
    sa.Column("predecessor_keys", JSONB, nullable=False),
    sa.Column("requirement_keys", JSONB, nullable=False),
    sa.Column("actor", sa.Text),
    sa.Column("assumed_min_days", sa.Integer),
    sa.Column("assumed_max_days", sa.Integer),
    sa.Column("assumed_rationale", sa.Text),
    sa.Column("action_titles", JSONB),
    sa.Column("city_service_target", JSONB),
    sa.Column("statutory_clock", JSONB),
    sa.Column("citation_ids", JSONB, nullable=False),
    sa.Column("status", sa.Text, nullable=False),  # not_started | in_progress | completed
    sa.Column("started_at", sa.DateTime(timezone=True)),
    sa.Column("completed_at", sa.DateTime(timezone=True)),
)

project_events = sa.Table(
    "project_events",
    metadata,
    sa.Column("id", UUID(as_uuid=True), primary_key=True),
    sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
    sa.Column("revision", sa.Integer, nullable=False),
    sa.Column("event_type", sa.Text, nullable=False),
    sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("payload", JSONB, nullable=False),
    sa.UniqueConstraint("project_id", "revision", name="uq_project_events_project_revision"),
)

# Lightweight reference to Person 3's jurisdictions table (not part of this MetaData).
jurisdictions = sa.table("jurisdictions", sa.column("id", UUID(as_uuid=True)), sa.column("slug", sa.Text))

# Columns, indexes and check constraints that Person 5's migration adds to Person 3's tables.
P5_OWNED_COLUMNS = {
    "projects": {
        "jurisdiction", "coverage_status", "coverage_reason", "release_summary", "pathway_summary",
        "missing_fact_keys", "location_evidence", "source_conflicts", "citations", "warnings",
    },
    "project_requirements": {
        "position", "kind", "title", "applicability", "missing_fact_keys", "required_for_preparation", "citation_ids",
    },
    "project_milestones": {
        "position", "title", "predecessor_keys", "requirement_keys", "actor", "assumed_min_days", "assumed_max_days",
        "assumed_rationale", "action_titles", "city_service_target", "statutory_clock", "citation_ids",
    },
}
P5_OWNED_INDEXES = {"ix_projects_created_at_id"}


def include_p5_object(obj, name, type_, reflected, compare_to) -> bool:
    """Alembic ``include_object`` hook: hide P5-owned columns/indexes from autogenerate/``alembic check``
    when the ORM models (Person 3) don't declare them."""
    if reflected and compare_to is None:
        if type_ == "column" and name in P5_OWNED_COLUMNS.get(obj.table.name, ()):
            return False
        if type_ == "index" and name in P5_OWNED_INDEXES:
            return False
    return True
