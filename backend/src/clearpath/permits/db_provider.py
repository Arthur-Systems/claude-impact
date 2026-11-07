"""Person 4's ReleaseProvider over the ACTIVE releases stored in PostgreSQL.

Coverage is read on every call, so publishing a release takes effect without a restart.
Release content is immutable, so each loaded ReleaseData is cached by release id.
"""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from clearpath.db.models import DatasetRelease, Jurisdiction
from clearpath.db.session import get_engine
from clearpath.locations.schemas import CoverageEntry
from clearpath.permits.release import ReleaseData, ReleaseLoadError
from clearpath.permits.schemas import LookupUnavailable


class DatabaseReleaseProvider:
    def __init__(self, database_url: str, mode: Literal["public", "synthetic"]) -> None:
        self.demo_mode = mode == "synthetic"
        self.dataset_mode = "synthetic" if self.demo_mode else "reviewed_public"
        self.published_at: dict[str, str | None] = {}
        self._database_url = database_url
        self._cache: dict[UUID, ReleaseData] = {}

    def _session(self) -> Session:
        return Session(bind=get_engine(self._database_url))

    def _active(self) -> list:
        try:
            with self._session() as session:
                return session.execute(
                    select(DatasetRelease.id, DatasetRelease.project_type, DatasetRelease.profile_key,
                           DatasetRelease.published_at, Jurisdiction.slug)
                    .join(Jurisdiction, Jurisdiction.id == DatasetRelease.jurisdiction_id)
                    .where(DatasetRelease.status == "active", DatasetRelease.kind == self.dataset_mode)
                ).all()
        except SQLAlchemyError:
            raise LookupUnavailable("dataset_unavailable", "the rule dataset is not available right now") from None

    def coverage(self) -> frozenset[CoverageEntry]:
        return frozenset(CoverageEntry(r.slug, r.project_type, r.profile_key) for r in self._active())

    def configured_profiles(self, jurisdiction: str, project_type: str) -> tuple[str | None, ...]:
        found = {e.profile_key for e in self.coverage() if (e.jurisdiction, e.project_type) == (jurisdiction, project_type)}
        return tuple(sorted(found, key=lambda p: (p is None, p or "")))

    def get_active(self, jurisdiction: str, project_type: str, profile_key: str | None) -> ReleaseData | None:
        row = next((r for r in self._active() if (r.slug, r.project_type, r.profile_key) == (jurisdiction, project_type, profile_key)), None)
        if row is None:
            return None
        if row.id not in self._cache:
            try:
                with self._session() as session:
                    release = session.get(DatasetRelease, row.id)
                    manifest, content_hash = release.manifest, release.content_hash
            except SQLAlchemyError:
                raise LookupUnavailable("dataset_unavailable", "the rule dataset is not available right now") from None
            if manifest is None:  # imported before manifests were stored: unavailable, never guessed
                return None
            try:
                self._cache[row.id] = ReleaseData.from_manifest(manifest, str(row.id), content_hash, self.dataset_mode)
            except ReleaseLoadError:
                return None
            self.published_at[str(row.id)] = row.published_at.isoformat() if row.published_at else None
        return self._cache[row.id]
