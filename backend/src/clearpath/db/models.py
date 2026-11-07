"""ClearPath's immutable dataset content and revisioned project records."""
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from clearpath.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UUIDPrimaryKey:
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)


class Jurisdiction(UUIDPrimaryKey, Base):
    __tablename__ = "jurisdictions"
    slug: Mapped[str] = mapped_column(String, unique=True)
    name: Mapped[str] = mapped_column(String)
    state: Mapped[str] = mapped_column(String)
    timezone: Mapped[str] = mapped_column(String, default="America/Los_Angeles", server_default="America/Los_Angeles")
    permit_page_url: Mapped[str | None] = mapped_column(Text)
    adu_checklist_url: Mapped[str | None] = mapped_column(Text)
    fee_schedule_url: Mapped[str | None] = mapped_column(Text)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DatasetRelease(UUIDPrimaryKey, Base):
    __tablename__ = "dataset_releases"
    __table_args__ = (
        CheckConstraint("project_type IN ('adu','duplex','multifamily','other_housing')", name="ck_release_project_type"),
        CheckConstraint("kind IN ('synthetic','reviewed_public')", name="ck_release_kind"),
        CheckConstraint("status IN ('draft','active','retired')", name="ck_release_status"),
        Index("uq_active_release_scope", "jurisdiction_id", "project_type", "profile_key", "kind", unique=True, postgresql_where=text("status = 'active'")),
    )
    jurisdiction_id: Mapped[UUID] = mapped_column(ForeignKey("jurisdictions.id", ondelete="RESTRICT"))
    project_type: Mapped[str] = mapped_column(String)
    profile_key: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    schema_version: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String, unique=True)
    fact_schema: Mapped[dict[str, Any]] = mapped_column(JSONB)
    conflicts: Mapped[list[Any]] = mapped_column(JSONB)
    curator_label: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=text("now()"))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReleaseContent:
    release_id: Mapped[UUID] = mapped_column(ForeignKey("dataset_releases.id", ondelete="RESTRICT"))


class SourceSnapshot(UUIDPrimaryKey, ReleaseContent, Base):
    __tablename__ = "source_snapshots"
    __table_args__ = (
        UniqueConstraint("release_id", "source_key"),
        CheckConstraint("verification_depth IN ('full_text_read','title_only','blocked')", name="ck_snapshot_verification_depth"),
    )
    source_key: Mapped[str] = mapped_column(String)
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    publisher: Mapped[str] = mapped_column(String)
    authority_type: Mapped[str] = mapped_column(String)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sha256: Mapped[str | None] = mapped_column(String)
    verification_depth: Mapped[str] = mapped_column(String)
    terms_note: Mapped[str | None] = mapped_column(Text)


class SourcePassage(ReleaseContent, Base):
    __tablename__ = "source_passages"
    __table_args__ = (
        UniqueConstraint("release_id", "manifest_passage_id"),
        CheckConstraint("review_status IN ('reviewed','needs_review','failed')", name="ck_passage_review_status"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=text("gen_random_uuid()"))
    manifest_passage_id: Mapped[UUID] = mapped_column()
    snapshot_id: Mapped[UUID] = mapped_column(ForeignKey("source_snapshots.id", ondelete="RESTRICT"))
    locator: Mapped[str] = mapped_column(Text)
    excerpt: Mapped[str] = mapped_column(Text)
    excerpt_hash: Mapped[str] = mapped_column(String)
    review_status: Mapped[str] = mapped_column(String)


class Pathway(UUIDPrimaryKey, ReleaseContent, Base):
    __tablename__ = "pathways"
    __table_args__ = (UniqueConstraint("release_id", "key"),)
    key: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(Text)
    applies_if: Mapped[dict[str, Any]] = mapped_column(JSONB)
    description: Mapped[str] = mapped_column(Text)


class Requirement(UUIDPrimaryKey, ReleaseContent, Base):
    __tablename__ = "requirements"
    __table_args__ = (
        UniqueConstraint("release_id", "key"),
        CheckConstraint("kind IN ('permit','document','review')", name="ck_requirement_kind"),
    )
    key: Mapped[str] = mapped_column(String)
    pathway_keys: Mapped[list[str]] = mapped_column(JSONB)
    kind: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    applies_if: Mapped[dict[str, Any]] = mapped_column(JSONB)
    required_for_preparation: Mapped[bool] = mapped_column(Boolean)


class MilestoneTemplate(UUIDPrimaryKey, ReleaseContent, Base):
    __tablename__ = "milestone_templates"
    __table_args__ = (UniqueConstraint("release_id", "key"),)
    key: Mapped[str] = mapped_column(String)
    position: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(Text)
    predecessors: Mapped[list[str]] = mapped_column(JSONB)
    requirement_keys: Mapped[list[str]] = mapped_column(JSONB)
    published_clock: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    assumed_days: Mapped[dict[str, Any] | None] = mapped_column(JSONB)


class CitationLink(UUIDPrimaryKey, ReleaseContent, Base):
    __tablename__ = "citation_links"
    __table_args__ = (
        UniqueConstraint("release_id", "owner_type", "owner_key", "passage_id"),
        CheckConstraint("owner_type IN ('pathway','requirement','milestone')", name="ck_citation_owner_type"),
    )
    owner_type: Mapped[str] = mapped_column(String)
    owner_key: Mapped[str] = mapped_column(String)
    passage_id: Mapped[UUID] = mapped_column(ForeignKey("source_passages.id", ondelete="RESTRICT"))


class IngestionRun(UUIDPrimaryKey, Base):
    __tablename__ = "ingestion_runs"
    __table_args__ = (CheckConstraint("status IN ('ok','no_op','failed')", name="ck_ingestion_status"),)
    manifest_path: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String)
    command: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    counts: Mapped[dict[str, Any]] = mapped_column(JSONB)
    error_codes: Mapped[list[str]] = mapped_column(JSONB)
    release_id: Mapped[UUID | None] = mapped_column(ForeignKey("dataset_releases.id", ondelete="RESTRICT"))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=text("now()"))
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=text("now()"))


class Project(UUIDPrimaryKey, Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint("project_type IN ('adu','duplex','multifamily','other_housing')", name="ck_project_type"),
        CheckConstraint("affordability_goal IN ('affordable_housing','mixed_income','unspecified')", name="ck_project_affordability"),
        CheckConstraint("state IN ('draft','active')", name="ck_project_state"),
        CheckConstraint("(state = 'draft' AND release_id IS NULL AND pathway_key IS NULL) OR (state = 'active' AND release_id IS NOT NULL AND pathway_key IS NOT NULL)", name="ck_project_release_state"),
        CheckConstraint("char_length(project_label) BETWEEN 1 AND 80", name="ck_project_label_length"),
        CheckConstraint("proposed_unit_count >= 0", name="ck_project_proposed_units"),
        CheckConstraint("affordable_unit_count_goal >= 0", name="ck_project_affordable_units"),
        CheckConstraint("affordable_unit_count_goal <= proposed_unit_count", name="ck_project_affordable_limit"),
    )
    project_label: Mapped[str] = mapped_column(String)
    project_type: Mapped[str] = mapped_column(String)
    subtype: Mapped[str | None] = mapped_column(String)
    jurisdiction_id: Mapped[UUID | None] = mapped_column(ForeignKey("jurisdictions.id", ondelete="RESTRICT"))
    location: Mapped[dict[str, Any]] = mapped_column(JSONB)
    proposed_unit_count: Mapped[int | None] = mapped_column(Integer)
    affordability_goal: Mapped[str] = mapped_column(String)
    affordable_unit_count_goal: Mapped[int | None] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String)
    release_id: Mapped[UUID | None] = mapped_column(ForeignKey("dataset_releases.id", ondelete="RESTRICT"))
    pathway_key: Mapped[str | None] = mapped_column(String)
    rule_facts: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    revision: Mapped[int] = mapped_column(Integer, default=1, server_default=text("1"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=text("now()"), onupdate=utcnow)


class ProjectRequirement(Base):
    __tablename__ = "project_requirements"
    __table_args__ = (CheckConstraint("status IN ('not_started','in_progress','ready')", name="ck_project_requirement_status"),)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    requirement_key: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=text("now()"), onupdate=utcnow)


class ProjectMilestone(Base):
    __tablename__ = "project_milestones"
    __table_args__ = (CheckConstraint("status IN ('not_started','in_progress','completed')", name="ck_project_milestone_status"),)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    milestone_key: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProjectEvent(UUIDPrimaryKey, Base):
    __tablename__ = "project_events"
    __table_args__ = (UniqueConstraint("project_id", "revision"),)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    revision: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=text("now()"))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, server_default=text("now()"))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
