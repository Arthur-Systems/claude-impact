"""Request models for project routes. Unknown fields are rejected (spec §9)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LocationInput(Strict):
    """Declared location. Only selected_area / fixture are resolvable offline in this slice."""

    mode: Literal["selected_area", "fixture", "point", "address"]
    area_key: str | None = Field(default=None, max_length=80)
    fixture_id: str | None = Field(default=None, max_length=80)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    address: dict[str, str] | None = None

    @model_validator(mode="after")
    def _one_mode(self):
        need = {"selected_area": "area_key", "fixture": "fixture_id", "address": "address"}
        if self.mode in need and getattr(self, need[self.mode]) is None:
            raise ValueError(f"{need[self.mode]} is required for mode {self.mode}")
        if self.mode == "point" and (self.longitude is None or self.latitude is None):
            raise ValueError("longitude and latitude are required for mode point")
        if self.address is not None:
            allowed = {"number", "street_name", "prefix", "pretype", "street_type", "suffix", "unit"}
            extra = set(self.address) - allowed
            if extra:
                raise ValueError(f"unknown address fields: {sorted(extra)}")
        return self


class RuleFacts(Strict):
    """Rule facts accepted by the first ADU profile (spec §7). All optional; absent = unknown."""

    adu_form: Literal["detached", "attached", "conversion", "junior"] | None = None
    existing_dwelling: StrictBool | None = None
    floor_area_sqft: float | None = Field(default=None, gt=0)


class ProjectCreateInput(Strict):
    project_label: str = Field(min_length=1, max_length=80)
    project_type: Literal["adu", "duplex", "multifamily", "other_housing"]
    subtype: str | None = Field(default=None, max_length=80)
    jurisdiction: str | None = Field(default=None, max_length=80)
    declared_location: LocationInput
    proposed_unit_count: int | None = Field(default=None, gt=0)
    affordability_goal: Literal["affordable_housing", "mixed_income", "unspecified"] = "unspecified"
    affordable_unit_count_goal: int | None = Field(default=None, ge=0)
    rule_facts: RuleFacts = Field(default_factory=RuleFacts)

    @field_validator("project_label")
    @classmethod
    def _label_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("project_label must not be blank")
        return v

    @model_validator(mode="after")
    def _goal_within_total(self):
        if (self.affordable_unit_count_goal is not None and self.proposed_unit_count is not None
                and self.affordable_unit_count_goal > self.proposed_unit_count):
            raise ValueError("affordable_unit_count_goal cannot exceed proposed_unit_count")
        return self


class ProjectActivationInput(Strict):
    pathway_key: str = Field(min_length=1, max_length=120)
    expected_revision: int = Field(ge=1)
    profile_key: str | None = Field(default=None, max_length=120)


class RequirementUpdateInput(Strict):
    status: Literal["not_started", "in_progress", "ready"]
    expected_revision: int = Field(ge=1)


class MilestoneEventInput(Strict):
    kind: Literal["start", "complete", "reopen"]
    milestone_key: str = Field(min_length=1, max_length=120)
    occurred_at: datetime
    correction_code: Literal["city_correction", "applicant_revision"] | None = None
    expected_revision: int = Field(ge=1)

    @field_validator("occurred_at")
    @classmethod
    def _aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("occurred_at must include a timezone offset")
        return v


class ProjectUpdateInput(Strict):
    """Draft-only edit. Omitted fields are unchanged; rule_facts replaces the whole object."""

    expected_revision: int = Field(ge=1)
    project_label: str | None = Field(default=None, min_length=1, max_length=80)
    project_type: Literal["adu", "duplex", "multifamily", "other_housing"] | None = None
    subtype: str | None = Field(default=None, max_length=80)
    jurisdiction: str | None = Field(default=None, max_length=80)
    declared_location: LocationInput | None = None
    proposed_unit_count: int | None = Field(default=None, gt=0)
    affordability_goal: Literal["affordable_housing", "mixed_income", "unspecified"] | None = None
    affordable_unit_count_goal: int | None = Field(default=None, ge=0)
    rule_facts: RuleFacts | None = None
