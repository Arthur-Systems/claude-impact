"""Frozen, network-free manifest contract (Pydantic v2).

Source identifiers deliberately use uppercase keys (e.g. IRV-ADU), unlike
lowercase rule/profile/jurisdiction slugs.
"""
from datetime import date
from typing import Annotated, Literal, Self
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import (
    AliasChoices, BaseModel, ConfigDict, Field, ModelWrapValidatorHandler, PrivateAttr,
    SerializationInfo, SerializerFunctionWrapHandler, StrictBool, StrictFloat, StrictInt,
    StringConstraints, field_validator, model_serializer, model_validator,
)

from clearpath.permits.predicates import ADU_FACT_SCHEMA

Slug = Annotated[str, StringConstraints(pattern=r'^[a-z0-9][a-z0-9_-]{0,79}$')]
SourceKey = Annotated[str, StringConstraints(pattern=r'^[A-Z0-9][A-Z0-9_-]{0,79}$')]
NonEmpty = Annotated[str, StringConstraints(min_length=1)]


def _without_curator_notes(data: object) -> object:
    """Copy JSON containers iteratively; curator notes never enter persisted payloads."""
    if not isinstance(data, (dict, list)):
        return data
    result = {} if isinstance(data, dict) else []
    pending = [(data, result)]
    while pending:
        source, target = pending.pop()
        entries = source.items() if isinstance(source, dict) else enumerate(source)
        for key, value in entries:
            if isinstance(key, str) and key.startswith('_'):
                continue
            if isinstance(value, (dict, list)):
                copied = {} if isinstance(value, dict) else []
                pending.append((value, copied))
            else:
                copied = value
            if isinstance(target, dict):
                target[key] = copied
            else:
                target.append(copied)
    return result


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class SourceDescriptor(StrictModel):
    key: SourceKey
    url: str
    title: str
    publisher: str
    authority_type: str
    checked_at: date
    sha256: Annotated[str, StringConstraints(pattern=r'^[0-9a-f]{64}$')] | None = None
    verification_depth: Literal['full_text_read', 'title_only', 'blocked']
    terms_note: str | None = None

    @field_validator('url')
    @classmethod
    def https_without_credentials(cls, value: str) -> str:
        try:
            parsed = urlsplit(value)
            if (parsed.scheme != 'https' or not parsed.hostname
                    or parsed.username is not None or parsed.password is not None
                    or any(c.isspace() or ord(c) < 32 for c in value)):
                raise ValueError('invalid source URL')
            # Accessing port also rejects malformed port values.
            parsed.port
        except ValueError:
            raise ValueError('invalid source URL') from None
        return value


class Passage(StrictModel):
    id: UUID
    source_key: SourceKey
    locator: NonEmpty
    excerpt: NonEmpty
    review_status: Literal['reviewed', 'needs_review', 'failed']


class Pathway(StrictModel):
    key: Slug
    title: str
    description: str = ''
    applies_if: dict
    citations: list[UUID]


class Requirement(StrictModel):
    key: Slug
    pathways: Annotated[list[Slug], Field(min_length=1)]
    kind: Literal['permit', 'document', 'review']
    title: str
    description: str
    applies_if: dict
    required_for_preparation: StrictBool
    citations: list[UUID]


class AssumedDays(StrictModel):
    min: Annotated[StrictInt, Field(ge=0)] | None
    max: Annotated[StrictInt, Field(ge=0)] | None
    label: Literal['ASSUMPTION']
    rationale: NonEmpty | None = None

    @model_validator(mode='after')
    def ordered_bounds(self) -> Self:
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError('invalid bounds')
        if (self.min is not None or self.max is not None) and self.rationale is None:
            raise ValueError('rationale required for estimated bounds')
        return self


class PublishedClock(StrictModel):
    kind: Literal['city_service_target', 'statutory_clock', 'observed', 'assumption']
    value: StrictInt | Annotated[StrictFloat, Field(allow_inf_nan=False)] | None
    unit: str
    scope: NonEmpty
    qualifier: str | None = None
    verification: str | None = None
    citation: UUID | None = None
    citations: list[UUID] = Field(default_factory=list)

    @model_validator(mode='after')
    def guidance_requires_citation(self) -> Self:
        if (self.kind in ('city_service_target', 'statutory_clock')
                and self.citation is None and not self.citations):
            raise ValueError('published guidance requires a citation')
        return self


class Milestone(StrictModel):
    key: Slug
    title: str
    predecessors: list[Slug]
    requirements: list[Slug]
    published_clock: PublishedClock | None
    assumed_days: AssumedDays | None
    citations: list[UUID]


class Conflict(StrictModel):
    model_config = ConfigDict(loc_by_alias=False)

    rule_keys: Annotated[list[NonEmpty], Field(min_length=1)]
    source_keys: Annotated[list[NonEmpty], Field(
        min_length=1, validation_alias=AliasChoices('source_keys', 'sources'),
    )]
    summary: NonEmpty
    _source_field: str = PrivateAttr(default='source_keys')

    @model_validator(mode='wrap')
    @classmethod
    def remember_source_field(cls, data: object, handler: ModelWrapValidatorHandler[Self]) -> Self:
        conflict = handler(data)
        if isinstance(data, dict) and 'sources' in data:
            conflict._source_field = 'sources'
        return conflict

    @model_serializer(mode='wrap')
    def preserve_source_field(self, handler: SerializerFunctionWrapHandler, info: SerializationInfo) -> dict:
        payload = handler(self)
        # Persistence uses round-trip mode; ordinary consumers keep the canonical field.
        if info.round_trip and self._source_field == 'sources':
            payload['sources'] = payload.pop('source_keys')
        return payload


class Manifest(StrictModel):
    schema_version: StrictInt
    kind: Literal['synthetic', 'reviewed_public'] = 'reviewed_public'
    jurisdiction: Slug
    project_type: Literal['adu', 'duplex', 'multifamily', 'other_housing']
    profile_key: Slug
    subtype: str | None = None
    curator_label: str = ''
    fact_schema: dict[Slug, Literal['string', 'boolean', 'number']]
    sources: list[SourceDescriptor]
    passages: list[Passage]
    pathways: list[Pathway]
    requirements: list[Requirement]
    milestones: list[Milestone]
    conflicts: list[Conflict]

    @model_validator(mode='before')
    @classmethod
    def strip_curator_notes(cls, data: object) -> object:
        normalized = _without_curator_notes(data)
        if (isinstance(data, dict) and isinstance(normalized, dict)
                and isinstance(data.get('passages'), list)):
            for raw, passage in zip(data['passages'], normalized['passages'], strict=True):
                if isinstance(passage, dict) and 'review_status' not in passage:
                    passage['review_status'] = 'needs_review' if raw.get('_review_note') else 'reviewed'
        return normalized

    @model_validator(mode='before')
    @classmethod
    def default_adu_fact_schema(cls, data: object) -> object:
        if isinstance(data, dict) and data.get('project_type') == 'adu' and 'fact_schema' not in data:
            return {**data, 'fact_schema': {key: kind.value for key, kind in ADU_FACT_SCHEMA.items()}}
        return data
