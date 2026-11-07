"""Dataset services operate in the caller's transaction and never commit."""
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from hashlib import sha256
import json
import os
import re
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from clearpath.db.models import (
    CitationLink, DatasetRelease, IngestionRun, Jurisdiction, MilestoneTemplate,
    Pathway, Requirement, SourcePassage, SourceSnapshot,
)
from clearpath.domain.errors import DomainError
from clearpath.ingestion.validation import ValidatedBundle

REPO_ROOT = Path(__file__).resolve().parents[4]


class IngestionError(DomainError):
    """A safe operator-facing ingestion or publication error."""


@dataclass(frozen=True)
class ImportResult:
    release_id: UUID
    no_op: bool
    counts: dict[str, int]


def _citation_owners(bundle: ValidatedBundle) -> Iterator[tuple[str, str, UUID]]:
    for owner_type, owners in (
        ("pathway", bundle.manifest.pathways),
        ("requirement", bundle.manifest.requirements),
        ("milestone", bundle.manifest.milestones),
    ):
        for owner in owners:
            citations = set(owner.citations)
            published_clock = getattr(owner, "published_clock", None)
            if published_clock is not None:
                citations.update(published_clock.citations)
            for passage_id in sorted(citations, key=str):
                yield owner_type, owner.key, passage_id


def bundle_counts(bundle: ValidatedBundle) -> dict[str, int]:
    """Counts also used by the file-only CLI dry run, including deduplicated links."""
    manifest = bundle.manifest
    return {
        "dataset_releases": 1,
        "source_snapshots": len(manifest.sources),
        "source_passages": len(manifest.passages),
        "pathways": len(manifest.pathways),
        "requirements": len(manifest.requirements),
        "milestone_templates": len(manifest.milestones),
        "citation_links": sum(1 for _ in _citation_owners(bundle)),
    }


def import_bundle(session: Session, bundle: ValidatedBundle) -> ImportResult:
    """Import immutable content, or only audit a content-identical reimport.

    Flush each dependency layer explicitly: these ORM models intentionally have
    no relationships, so the unit of work cannot infer all insert ordering.
    Database failures propagate; the caller must roll back the transaction.
    """
    manifest = bundle.manifest
    jurisdiction = session.scalar(
        select(Jurisdiction).where(Jurisdiction.slug == manifest.jurisdiction)
    )
    if jurisdiction is None:
        raise IngestionError(
            "unknown_jurisdiction", "Import the city registry first.", {"path": "jurisdiction"},
        )
    release = session.scalar(select(DatasetRelease).where(
        DatasetRelease.content_hash == bundle.content_hash,
    ))
    no_op = release is not None
    counts = bundle_counts(bundle)
    if no_op:
        counts = dict.fromkeys(counts, 0)
    else:
        payload = manifest.model_dump(mode="json")
        release = DatasetRelease(
            jurisdiction_id=jurisdiction.id, project_type=manifest.project_type,
            profile_key=manifest.profile_key, kind=manifest.kind, status="draft",
            schema_version=manifest.schema_version, content_hash=bundle.content_hash,
            fact_schema=payload["fact_schema"], conflicts=payload["conflicts"],
            curator_label=manifest.curator_label,
        )
        session.add(release)
        session.flush()
        snapshots = {}
        for source in manifest.sources:
            snapshot = SourceSnapshot(
                release_id=release.id, source_key=source.key, url=source.url,
                title=source.title, publisher=source.publisher,
                authority_type=source.authority_type,
                checked_at=datetime.combine(source.checked_at, time.min, tzinfo=timezone.utc),
                sha256=source.sha256, verification_depth=source.verification_depth,
                terms_note=source.terms_note,
            )
            session.add(snapshot)
            snapshots[source.key] = snapshot
        session.flush()
        passage_ids = {}
        for passage in manifest.passages:
            passage_id = uuid4()
            passage_ids[passage.id] = passage_id
            session.add(SourcePassage(
                id=passage_id, release_id=release.id, manifest_passage_id=passage.id,
                snapshot_id=snapshots[passage.source_key].id, locator=passage.locator,
                excerpt=passage.excerpt,
                excerpt_hash=sha256(passage.excerpt.encode("utf-8")).hexdigest(),
                review_status=passage.review_status,
            ))
        session.flush()
        for pathway in manifest.pathways:
            session.add(Pathway(
                release_id=release.id, key=pathway.key, title=pathway.title,
                applies_if=pathway.applies_if, description=pathway.description,
            ))
        for requirement in manifest.requirements:
            session.add(Requirement(
                release_id=release.id, key=requirement.key, pathway_keys=requirement.pathways,
                kind=requirement.kind, title=requirement.title, description=requirement.description,
                applies_if=requirement.applies_if,
                required_for_preparation=requirement.required_for_preparation,
            ))
        for position, milestone in enumerate(manifest.milestones):
            session.add(MilestoneTemplate(
                release_id=release.id, key=milestone.key, position=position, title=milestone.title,
                predecessors=milestone.predecessors, requirement_keys=milestone.requirements,
                published_clock=(milestone.published_clock.model_dump(mode="json")
                                 if milestone.published_clock is not None else None),
                assumed_days=(milestone.assumed_days.model_dump(mode="json")
                              if milestone.assumed_days is not None else None),
            ))
        session.flush()
        for owner_type, owner_key, manifest_passage_id in _citation_owners(bundle):
            session.add(CitationLink(
                release_id=release.id, owner_type=owner_type, owner_key=owner_key,
                passage_id=passage_ids[manifest_passage_id],
            ))
        session.flush()
    session.add(IngestionRun(
        manifest_path=os.path.relpath(bundle.manifest_path, REPO_ROOT),
        content_hash=bundle.content_hash, command="import", status="no_op" if no_op else "ok",
        counts=counts, error_codes=[], release_id=release.id,
    ))
    session.flush()
    return ImportResult(release_id=release.id, no_op=no_op, counts=counts)


def publish_release(
    session: Session, release_id: UUID, *, reviewed: bool, mode: Literal["public", "synthetic"],
) -> DatasetRelease:
    """Activate one draft and retire its predecessor without changing project pins."""
    if not reviewed:
        raise IngestionError(
            "review_confirmation_required", "Confirm the release has been reviewed.", {"path": "reviewed"},
        )
    release = session.get(DatasetRelease, release_id)
    if release is None:
        raise IngestionError("release_not_found", "Release not found.", {"path": "release"}, http_status=404)
    # Serialize all publication decisions for this jurisdiction, including a
    # second attempt to publish the same release after waiting on another caller.
    session.execute(select(Jurisdiction).where(
        Jurisdiction.id == release.jurisdiction_id,
    ).with_for_update()).scalar_one()
    session.refresh(release)
    if release.status != "draft":
        raise IngestionError("release_not_draft", "Only draft releases can be published.", {"path": "release"})
    expected_kind = {"public": "reviewed_public", "synthetic": "synthetic"}.get(mode)
    if release.kind != expected_kind:
        raise IngestionError("release_kind_mismatch", "Release kind does not match the operating mode.", {"path": "kind"})
    owner_keys = session.scalars(
        select(CitationLink.owner_key)
        .join(SourcePassage, CitationLink.passage_id == SourcePassage.id)
        .where(CitationLink.release_id == release.id, SourcePassage.review_status != "reviewed")
        .distinct().order_by(CitationLink.owner_key)
    ).all()
    if owner_keys:
        raise IngestionError(
            "unreviewed_evidence", "Cited evidence requires review.",
            {"path": "citations", "owner_keys": list(owner_keys)},
        )
    if release.kind == "reviewed_public":
        for model, path in ((Pathway, "pathways"), (Requirement, "requirements")):
            if session.scalar(select(model.id).where(model.release_id == release.id).limit(1)) is None:
                raise IngestionError(
                    "empty_release", "Public releases need pathways and requirements.", {"path": path},
                )
    active_releases = session.scalars(select(DatasetRelease).where(
        DatasetRelease.jurisdiction_id == release.jurisdiction_id,
        DatasetRelease.project_type == release.project_type,
        DatasetRelease.profile_key == release.profile_key,
        DatasetRelease.kind == release.kind,
        DatasetRelease.status == "active",
    )).all()
    for previous in active_releases:
        previous.status = "retired"
    # Free the partial unique-index slot before activating the replacement.
    session.flush()
    release.status = "active"
    release.published_at = datetime.now(timezone.utc)
    session.flush()
    return release


def import_cities(session: Session, path: Path) -> int:
    """Upsert the registry without treating registry presence as rule coverage.

    Null file metadata never erases previously checked values. The source file
    uses permit_page/adu_checklist/fee_schedule/checked (not the ORM names).
    """
    cities = json.loads(path.read_text(encoding="utf-8"))["cities"]
    for city in cities:
        name = city["name"]
        slug = "-".join(re.sub(r"[^a-z0-9\s-]", "", name.lower()).split()) + "-ca"
        checked = city.get("checked")
        statement = insert(Jurisdiction).values(
            slug=slug, name=name, state="CA",
            permit_page_url=city.get("permit_page"),
            adu_checklist_url=city.get("adu_checklist"),
            fee_schedule_url=city.get("fee_schedule"),
            checked_at=(datetime.combine(date.fromisoformat(checked), time.min, tzinfo=timezone.utc)
                        if checked is not None else None),
        )
        fields = ("name", "state", "permit_page_url", "adu_checklist_url", "fee_schedule_url", "checked_at")
        session.execute(statement.on_conflict_do_update(
            index_elements=[Jurisdiction.slug],
            set_={field: func.coalesce(getattr(statement.excluded, field), getattr(Jurisdiction, field))
                  for field in fields},
        ))
    session.flush()
    return len(cities)
