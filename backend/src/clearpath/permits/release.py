"""Read-only release data for permit lookup, and the provider seam for Person 3's DB.

``ReleaseData.from_manifest`` takes a manifest dict in Person 3's contract shape
(``ingestion/schemas.py`` on origin/p3-platform) and indexes it for lookup. Later, a
database-backed ``ReleaseProvider`` can replace ``InMemoryReleaseProvider`` without
changing the lookup service.

Draft manifests (e.g. Person 2's backend/data/irvine_adu/manifest.json) may lack
``fact_schema`` and ``profile_key``. Those gaps are handled ONLY by
``derive_draft_manifest_fallbacks`` and are reported as a warning in every lookup.
"""

from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Protocol

from clearpath.locations.schemas import CoverageEntry

DATASET_MODES = ("synthetic", "reviewed_public")

DRAFT_ADU_FACT_SCHEMA: Mapping[str, str] = MappingProxyType(
    {"adu_form": "string", "existing_dwelling": "bool", "floor_area_sqft": "number"}
)
"""Fact types assumed for a draft ADU manifest that has no fact_schema (SPEC.md section 7 facts)."""

_CONFLICT_NAMESPACE = uuid.UUID("6f2b3c1e-8a7d-4f5e-9b0c-2d1e4a5b6c7d")


class ReleaseLoadError(ValueError):
    """A manifest cannot be turned into release data."""


@dataclass(frozen=True)
class DraftManifestFallbacks:
    fact_schema: Mapping[str, Any]
    profile_key: str | None
    gaps: tuple[str, ...] = ()


def derive_draft_manifest_fallbacks(manifest: Mapping[str, Any]) -> DraftManifestFallbacks:
    """Fill gaps in a DRAFT manifest, and say which gaps were filled.

    * no ``fact_schema``: use DRAFT_ADU_FACT_SCHEMA, for ADU manifests only
    * no ``profile_key``: the profile is unknown (None); it never matches an explicit
      profile_key in a request
    """
    gaps: list[str] = []
    schema = manifest.get("fact_schema")
    if schema is None:
        if manifest.get("project_type") != "adu":
            raise ReleaseLoadError("manifest has no fact_schema, and a default exists only for ADU manifests")
        schema = dict(DRAFT_ADU_FACT_SCHEMA)
        gaps.append("fact_schema_missing")
    profile_key = manifest.get("profile_key")
    if profile_key is None:
        gaps.append("profile_key_missing")
    return DraftManifestFallbacks(fact_schema=schema, profile_key=profile_key, gaps=tuple(gaps))


@dataclass(frozen=True)
class Conflict:
    id: str
    rule_keys: tuple[str, ...]
    source_keys: tuple[str, ...]
    summary: str


@dataclass(frozen=True)
class ReleaseData:
    release_id: str
    content_hash: str
    dataset_mode: str
    jurisdiction: str
    project_type: str
    profile_key: str | None
    fact_schema: Mapping[str, Any]
    sources: Mapping[str, Mapping[str, Any]]
    passages: Mapping[str, Mapping[str, Any]]
    pathways: tuple[Mapping[str, Any], ...]
    requirements: tuple[Mapping[str, Any], ...]
    milestones: tuple[Mapping[str, Any], ...]
    conflicts: tuple[Conflict, ...]
    draft_gaps: tuple[str, ...] = field(default=())
    test_only_unreviewed: bool = False
    """True only when a test forced unreviewed data to load as reviewed_public."""

    @property
    def coverage_entry(self) -> CoverageEntry:
        return CoverageEntry(self.jurisdiction, self.project_type, self.profile_key)

    def is_reviewed(self, passage_id: str) -> bool:
        """Only an explicit review_status of 'reviewed' counts. Missing means NOT reviewed."""
        passage = self.passages.get(passage_id)
        return passage is not None and passage.get("review_status") == "reviewed"

    @classmethod
    def from_manifest(
        cls,
        manifest: Mapping[str, Any],
        release_id: str,
        content_hash: str,
        dataset_mode: str,
        *,
        test_only_allow_unreviewed: bool = False,
    ) -> ReleaseData:
        """Build release data.

        ``reviewed_public`` must be earned: the manifest must say ``kind: reviewed_public``,
        have no draft gaps, and have every passage marked ``review_status: reviewed``.
        Otherwise this raises ReleaseLoadError. ``test_only_allow_unreviewed`` skips that
        check FOR TESTS ONLY; the release is then flagged and every lookup warns.
        """
        if dataset_mode not in DATASET_MODES:
            raise ReleaseLoadError("dataset_mode must be 'synthetic' or 'reviewed_public'")
        if not isinstance(manifest, Mapping):
            raise ReleaseLoadError("manifest must be an object")
        kind = manifest.get("kind")
        if kind is not None and kind != dataset_mode:
            raise ReleaseLoadError("manifest kind does not match dataset_mode")
        for key in ("jurisdiction", "project_type"):
            if not isinstance(manifest.get(key), str):
                raise ReleaseLoadError(f"manifest needs a '{key}' string")

        m = copy.deepcopy(dict(manifest))
        fallbacks = derive_draft_manifest_fallbacks(m)

        def rows(name: str) -> list[dict]:
            value = m.get(name) or []
            if not isinstance(value, list) or not all(isinstance(r, dict) for r in value):
                raise ReleaseLoadError(f"manifest '{name}' must be a list of objects")
            return value

        sources = {s["key"]: MappingProxyType(s) for s in rows("sources") if isinstance(s.get("key"), str)}
        passages = {str(p["id"]): MappingProxyType(p) for p in rows("passages") if "id" in p}

        forced = False
        if dataset_mode == "reviewed_public":
            problems = _public_label_problems(kind, fallbacks.gaps, rows("passages"))
            if problems and not test_only_allow_unreviewed:
                raise ReleaseLoadError("cannot label this manifest reviewed_public: " + "; ".join(problems))
            forced = bool(problems)

        conflicts = []
        for index, c in enumerate(rows("conflicts")):
            rule_keys = c.get("rule_keys") if isinstance(c.get("rule_keys"), list) else []
            # Contract name is source_keys; Person 2's draft uses sources.
            source_keys = c.get("source_keys", c.get("sources"))
            source_keys = source_keys if isinstance(source_keys, list) else []
            conflicts.append(
                Conflict(
                    id=str(uuid.uuid5(_CONFLICT_NAMESPACE, f"{release_id}:{index}")),
                    rule_keys=tuple(k for k in rule_keys if isinstance(k, str)),
                    source_keys=tuple(k for k in source_keys if isinstance(k, str)),
                    summary=c.get("summary") if isinstance(c.get("summary"), str) else "",
                )
            )

        return cls(
            release_id=str(release_id),
            content_hash=content_hash,
            dataset_mode=dataset_mode,
            jurisdiction=m["jurisdiction"],
            project_type=m["project_type"],
            profile_key=fallbacks.profile_key,
            fact_schema=MappingProxyType(dict(fallbacks.fact_schema)),
            sources=MappingProxyType(sources),
            passages=MappingProxyType(passages),
            pathways=tuple(MappingProxyType(p) for p in rows("pathways")),
            requirements=tuple(MappingProxyType(r) for r in rows("requirements")),
            milestones=tuple(MappingProxyType(r) for r in rows("milestones")),
            conflicts=tuple(conflicts),
            draft_gaps=fallbacks.gaps,
            test_only_unreviewed=forced,
        )


def _public_label_problems(kind: Any, draft_gaps: tuple[str, ...], passages: list[dict]) -> list[str]:
    """Reasons a manifest is not reviewed public data. Empty list means it qualifies."""
    problems = []
    if kind != "reviewed_public":
        problems.append("manifest kind is not 'reviewed_public'")
    if draft_gaps:
        problems.append("draft manifest gaps: " + ", ".join(draft_gaps))
    unreviewed = sum(1 for p in passages if p.get("review_status") != "reviewed")
    if unreviewed:
        problems.append(f"{unreviewed} unreviewed passage(s)")
    return problems


class ReleaseProvider(Protocol):
    """What the lookup service needs from storage. Person 3's DB will implement this."""

    demo_mode: bool

    def coverage(self) -> frozenset[CoverageEntry]:
        """Configured rule profiles (the coverage catalog), whether or not their release is loadable."""

    def configured_profiles(self, jurisdiction: str, project_type: str) -> tuple[str | None, ...]:
        """Profile keys configured for a city and project type. None means 'profile unknown'."""

    def get_active(self, jurisdiction: str, project_type: str, profile_key: str | None) -> ReleaseData | None:
        """The active release for a profile, or None if it is unavailable."""


def _profile_sort(profile: str | None) -> tuple[bool, str]:
    return (profile is None, profile or "")


class InMemoryReleaseProvider:
    """Releases held in memory, for tests and the offline demo.

    Demo (synthetic) and public releases never mix in one provider (SPEC.md section 10).
    ``configured`` adds catalog entries with no release, to model an unavailable dataset.
    """

    def __init__(
        self, releases: Iterable[ReleaseData] = (), *, demo_mode: bool, configured: Iterable[CoverageEntry] = ()
    ) -> None:
        self.demo_mode = demo_mode
        expected = "synthetic" if demo_mode else "reviewed_public"
        self._releases: dict[CoverageEntry, ReleaseData] = {}
        for r in releases:
            if r.dataset_mode != expected:
                raise ValueError(f"a {'demo' if demo_mode else 'public'} provider only holds {expected} releases")
            if r.coverage_entry in self._releases:
                raise ValueError("only one active release per jurisdiction, project type and profile")
            self._releases[r.coverage_entry] = r
        self._catalog = frozenset(self._releases) | frozenset(CoverageEntry(*c) for c in configured)

    def coverage(self) -> frozenset[CoverageEntry]:
        return self._catalog

    def configured_profiles(self, jurisdiction: str, project_type: str) -> tuple[str | None, ...]:
        found = {c.profile_key for c in self._catalog if c.jurisdiction == jurisdiction and c.project_type == project_type}
        return tuple(sorted(found, key=_profile_sort))

    def get_active(self, jurisdiction: str, project_type: str, profile_key: str | None) -> ReleaseData | None:
        return self._releases.get(CoverageEntry(jurisdiction, project_type, profile_key))
