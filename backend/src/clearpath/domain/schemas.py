from enum import Enum

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectType(str, Enum):
    adu = "adu"
    duplex = "duplex"
    multifamily = "multifamily"
    other_housing = "other_housing"


class ReleaseKind(str, Enum):
    synthetic = "synthetic"
    reviewed_public = "reviewed_public"


class ReleaseStatus(str, Enum):
    draft = "draft"
    active = "active"
    retired = "retired"


class AffordabilityGoal(str, Enum):
    affordable_housing = "affordable_housing"
    mixed_income = "mixed_income"
    unspecified = "unspecified"
