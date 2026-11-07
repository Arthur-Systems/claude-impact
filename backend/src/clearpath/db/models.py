"""Shared dataset ORM contract. Ingestion validates JSON and array references."""

from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Identified:
    id: Mapped[UUID] = mapped_column(
        primary_key=True, default=uuid4, server_default=text("gen_random_uuid()")
    )


class SourceSnapshot(Identified, Base):
    __tablename__ = "source_snapshots"
    __table_args__ = (
        UniqueConstraint("source_key", "sha256", name="uq_snapshot_source_hash"),
        CheckConstraint("source_key ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="ck_snapshot_key"),
        CheckConstraint("sha256 ~ '^[0-9a-f]{64}$'", name="ck_snapshot_hash"),
        CheckConstraint(
            "extraction_status IN ('pending','succeeded','failed')", name="ck_snapshot_extraction"
        ),
        CheckConstraint(
            "review_status IN ('pending','reviewed','rejected')", name="ck_snapshot_review"
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from",
            name="ck_snapshot_effective_dates",
        ),
    )
    source_key: Mapped[str] = mapped_column(Text)
    canonical_url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    publisher: Mapped[str] = mapped_column(Text)
    authority_type: Mapped[str] = mapped_column(Text)
    mime_type: Mapped[str] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    sha256: Mapped[str] = mapped_column(String(64))
    local_artifact_key: Mapped[str] = mapped_column(Text)
    extraction_status: Mapped[str] = mapped_column(Text)
    review_status: Mapped[str] = mapped_column(Text)


class Jurisdiction(Identified, Base):
    __tablename__ = "jurisdictions"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_jurisdiction_slug"),
        CheckConstraint("slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="ck_jurisdiction_slug"),
    )
    slug: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    state: Mapped[str] = mapped_column(String(2))
    timezone: Mapped[str] = mapped_column(Text)
    boundary_snapshot_id: Mapped[UUID | None] = mapped_column(ForeignKey("source_snapshots.id"))


class SourcePassage(Identified, Base):
    __tablename__ = "source_passages"
    __table_args__ = (
        UniqueConstraint("snapshot_id", "locator", "excerpt_hash", name="uq_passage_content"),
        CheckConstraint("excerpt_hash ~ '^[0-9a-f]{64}$'", name="ck_passage_hash"),
    )
    snapshot_id: Mapped[UUID] = mapped_column(ForeignKey("source_snapshots.id"), index=True)
    locator: Mapped[str] = mapped_column(Text)
    excerpt: Mapped[str] = mapped_column(Text)
    excerpt_hash: Mapped[str] = mapped_column(String(64))


class DatasetRelease(Identified, Base):
    __tablename__ = "dataset_releases"
    __table_args__ = (
        UniqueConstraint(
            "jurisdiction_id",
            "project_type",
            "profile_key",
            "content_hash",
            name="uq_release_content",
        ),
        CheckConstraint("project_type ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="ck_release_type"),
        CheckConstraint("profile_key ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="ck_release_profile"),
        CheckConstraint("content_hash ~ '^[0-9a-f]{64}$'", name="ck_release_hash"),
        CheckConstraint("schema_version > 0", name="ck_release_schema_version"),
        CheckConstraint("status IN ('draft','active','retired')", name="ck_release_status"),
        CheckConstraint(
            "data_classification IN ('synthetic','reviewed_public')",
            name="ck_release_classification",
        ),
        CheckConstraint("jsonb_typeof(fact_schema) = 'object'", name="ck_release_fact_schema"),
        CheckConstraint("jsonb_typeof(normalized_manifest) = 'object'", name="ck_release_manifest"),
        Index(
            "uq_release_active_profile",
            "jurisdiction_id",
            "project_type",
            "profile_key",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )
    jurisdiction_id: Mapped[UUID] = mapped_column(ForeignKey("jurisdictions.id"), index=True)
    project_type: Mapped[str] = mapped_column(Text)
    profile_key: Mapped[str] = mapped_column(Text)
    fact_schema: Mapped[dict[str, Any]] = mapped_column(JSONB)
    content_hash: Mapped[str] = mapped_column(String(64))
    schema_version: Mapped[int] = mapped_column(Integer)
    normalized_manifest: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(Text)
    data_classification: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    curator_label: Mapped[str] = mapped_column(Text)


class IngestionRun(Identified, Base):
    __tablename__ = "ingestion_runs"
    __table_args__ = (
        CheckConstraint("manifest_hash ~ '^[0-9a-f]{64}$'", name="ck_run_hash"),
        CheckConstraint("status IN ('running','succeeded','failed')", name="ck_run_status"),
        CheckConstraint("jsonb_typeof(counts) = 'object'", name="ck_run_counts"),
        CheckConstraint("finished_at IS NULL OR finished_at >= started_at", name="ck_run_dates"),
    )
    manifest_hash: Mapped[str] = mapped_column(String(64))
    command_kind: Mapped[str] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(Text)
    counts: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    error_codes: Mapped[list[str]] = mapped_column(
        ARRAY(Text), default=list, server_default=text("'{}'::text[]")
    )
    resulting_release_id: Mapped[UUID | None] = mapped_column(ForeignKey("dataset_releases.id"))


class Pathway(Identified, Base):
    __tablename__ = "pathways"
    __table_args__ = (
        UniqueConstraint("release_id", "key", name="uq_pathway_release_key"),
        CheckConstraint("key ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="ck_pathway_key"),
        CheckConstraint("jsonb_typeof(applicability) = 'object'", name="ck_pathway_predicate"),
    )
    release_id: Mapped[UUID] = mapped_column(ForeignKey("dataset_releases.id"), index=True)
    key: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    applicability: Mapped[dict[str, Any]] = mapped_column(JSONB)
    explanation: Mapped[str] = mapped_column(Text)


class Requirement(Identified, Base):
    __tablename__ = "requirements"
    __table_args__ = (
        UniqueConstraint("release_id", "key", name="uq_requirement_release_key"),
        CheckConstraint("key ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="ck_requirement_key"),
        CheckConstraint("kind IN ('permit','document','review')", name="ck_requirement_kind"),
        CheckConstraint("jsonb_typeof(applicability) = 'object'", name="ck_requirement_predicate"),
    )
    release_id: Mapped[UUID] = mapped_column(ForeignKey("dataset_releases.id"), index=True)
    key: Mapped[str] = mapped_column(Text)
    pathway_keys: Mapped[list[str]] = mapped_column(ARRAY(Text))
    kind: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text)
    applicability: Mapped[dict[str, Any]] = mapped_column(JSONB)
    required_for_preparation: Mapped[bool] = mapped_column(Boolean)


class MilestoneTemplate(Identified, Base):
    __tablename__ = "milestone_templates"
    __table_args__ = (
        UniqueConstraint("release_id", "key", name="uq_milestone_release_key"),
        ForeignKeyConstraint(
            ["release_id", "pathway_key"],
            ["pathways.release_id", "pathways.key"],
            name="fk_milestone_release_pathway",
        ),
        CheckConstraint("key ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="ck_milestone_key"),
        CheckConstraint(
            "(forecast_min_days IS NULL AND forecast_max_days IS NULL) OR "
            "(forecast_min_days IS NOT NULL AND forecast_max_days IS NOT NULL "
            "AND forecast_min_days >= 0 AND forecast_max_days >= forecast_min_days)",
            name="ck_milestone_forecast",
        ),
        CheckConstraint(
            "published_clock IS NULL OR jsonb_typeof(published_clock) = 'object'",
            name="ck_milestone_clock",
        ),
    )
    release_id: Mapped[UUID] = mapped_column(ForeignKey("dataset_releases.id"), index=True)
    pathway_key: Mapped[str] = mapped_column(Text)
    key: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    predecessor_keys: Mapped[list[str]] = mapped_column(ARRAY(Text))
    requirement_keys: Mapped[list[str]] = mapped_column(ARRAY(Text))
    forecast_min_days: Mapped[int | None] = mapped_column(Integer)
    forecast_max_days: Mapped[int | None] = mapped_column(Integer)
    published_clock: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))


class PathwayCitation(Base):
    __tablename__ = "pathway_citations"
    pathway_id: Mapped[UUID] = mapped_column(ForeignKey("pathways.id"), primary_key=True)
    passage_id: Mapped[UUID] = mapped_column(ForeignKey("source_passages.id"), primary_key=True)


class RequirementCitation(Base):
    __tablename__ = "requirement_citations"
    requirement_id: Mapped[UUID] = mapped_column(ForeignKey("requirements.id"), primary_key=True)
    passage_id: Mapped[UUID] = mapped_column(ForeignKey("source_passages.id"), primary_key=True)


class MilestoneCitation(Base):
    __tablename__ = "milestone_citations"
    milestone_id: Mapped[UUID] = mapped_column(
        ForeignKey("milestone_templates.id"), primary_key=True
    )
    passage_id: Mapped[UUID] = mapped_column(ForeignKey("source_passages.id"), primary_key=True)
