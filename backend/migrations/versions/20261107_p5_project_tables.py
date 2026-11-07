"""P5: extend Person 3's project tables with the columns projects/timelines need.

Owner: Person 5. Spec §5. No applicant name, contact data or uploads.

Person 3's ``0001_initial`` creates projects, project_requirements,
project_milestones and project_events. This migration is purely additive: it
adds columns, one index and check constraints with ``p5`` names. It never
drops or renames Person 3's columns or constraints. New NOT NULL columns all
have server defaults, so Person 3's ORM inserts (which don't know these
columns) keep working.

Revision ID: p5_0001_project_tables
Revises: 0001_initial
Create Date: 2026-11-07
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "p5_0001_project_tables"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

EMPTY_LIST = sa.text("'[]'::jsonb")


def _cols(table: str, *cols: sa.Column) -> None:
    for c in cols:
        op.add_column(table, c)


def upgrade() -> None:
    _cols(
        "projects",
        sa.Column("jurisdiction", sa.Text),
        sa.Column("coverage_status", sa.Text, nullable=False, server_default="unconfigured"),
        sa.Column("coverage_reason", sa.Text),
        sa.Column("release_summary", JSONB),
        sa.Column("pathway_summary", JSONB),
        sa.Column("missing_fact_keys", JSONB, nullable=False, server_default=EMPTY_LIST),
        sa.Column("location_evidence", JSONB),
        sa.Column("source_conflicts", JSONB, nullable=False, server_default=EMPTY_LIST),
        sa.Column("citations", JSONB, nullable=False, server_default=EMPTY_LIST),
        sa.Column("warnings", JSONB, nullable=False, server_default=EMPTY_LIST),
    )
    op.create_check_constraint(
        "ck_projects_p5_coverage_status", "projects", "coverage_status IN ('unconfigured','configured')"
    )
    op.create_index("ix_projects_created_at_id", "projects", ["created_at", "id"])

    _cols(
        "project_requirements",
        sa.Column("position", sa.Integer),
        sa.Column("kind", sa.Text),
        sa.Column("title", sa.Text),
        sa.Column("applicability", sa.Text),
        sa.Column("missing_fact_keys", JSONB, nullable=False, server_default=EMPTY_LIST),
        sa.Column("required_for_preparation", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("citation_ids", JSONB, nullable=False, server_default=EMPTY_LIST),
    )
    op.create_check_constraint(
        "ck_project_requirements_p5_kind", "project_requirements", "kind IN ('permit','document','review')"
    )
    op.create_check_constraint(
        "ck_project_requirements_p5_applicability", "project_requirements",
        "applicability IN ('applies','needs_information','not_applicable')",
    )

    _cols(
        "project_milestones",
        sa.Column("position", sa.Integer),
        sa.Column("title", sa.Text),
        sa.Column("predecessor_keys", JSONB, nullable=False, server_default=EMPTY_LIST),
        sa.Column("requirement_keys", JSONB, nullable=False, server_default=EMPTY_LIST),
        sa.Column("actor", sa.Text),
        sa.Column("assumed_min_days", sa.Integer),
        sa.Column("assumed_max_days", sa.Integer),
        sa.Column("assumed_rationale", sa.Text),
        sa.Column("action_titles", JSONB),
        sa.Column("city_service_target", JSONB),
        sa.Column("statutory_clock", JSONB),
        sa.Column("citation_ids", JSONB, nullable=False, server_default=EMPTY_LIST),
    )
    op.create_check_constraint(
        "ck_project_milestones_p5_dates_match_status", "project_milestones",
        "(status = 'not_started' AND started_at IS NULL AND completed_at IS NULL) OR "
        "(status = 'in_progress' AND started_at IS NOT NULL AND completed_at IS NULL) OR "
        "(status = 'completed' AND started_at IS NOT NULL AND completed_at IS NOT NULL AND completed_at >= started_at)",
    )
    op.create_check_constraint(
        "ck_project_milestones_p5_assumed_range", "project_milestones",
        "assumed_min_days IS NULL OR assumed_max_days IS NULL OR "
        "(assumed_min_days >= 0 AND assumed_max_days >= assumed_min_days)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_project_milestones_p5_assumed_range", "project_milestones", type_="check")
    op.drop_constraint("ck_project_milestones_p5_dates_match_status", "project_milestones", type_="check")
    for c in ("citation_ids", "statutory_clock", "city_service_target", "action_titles", "assumed_rationale",
              "assumed_max_days", "assumed_min_days", "actor", "requirement_keys", "predecessor_keys", "title",
              "position"):
        op.drop_column("project_milestones", c)
    op.drop_constraint("ck_project_requirements_p5_applicability", "project_requirements", type_="check")
    op.drop_constraint("ck_project_requirements_p5_kind", "project_requirements", type_="check")
    for c in ("citation_ids", "required_for_preparation", "missing_fact_keys", "applicability", "title", "kind",
              "position"):
        op.drop_column("project_requirements", c)
    op.drop_index("ix_projects_created_at_id", table_name="projects")
    op.drop_constraint("ck_projects_p5_coverage_status", "projects", type_="check")
    for c in ("warnings", "citations", "source_conflicts", "location_evidence", "missing_fact_keys",
              "pathway_summary", "release_summary", "coverage_reason", "coverage_status", "jurisdiction"):
        op.drop_column("projects", c)
