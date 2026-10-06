"""Request and response models for the role routes (api/openapi.yaml)."""

import uuid
from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.core.criteria_limits import (
    KINDS,
    LEVELS,
    MAX_CRITERIA,
    MAX_DESCRIPTOR_CHARS,
    MAX_NAME_CHARS,
    MAX_WEIGHT,
    MIN_CRITERIA,
    MIN_WEIGHT,
)

MAX_TITLE_CHARS = 200
MAX_JOB_DESCRIPTION_CHARS = 20000


def _one_line(value: str) -> str:
    if len(value.splitlines()) > 1:
        raise ValueError("must be a single line")
    return value


def _stripped(max_length: int) -> StringConstraints:
    return StringConstraints(strip_whitespace=True, min_length=1, max_length=max_length)


# Strip, then length, then the single-line check (order matters: constraints before the validator).
Name = Annotated[str, _stripped(MAX_NAME_CHARS), AfterValidator(_one_line)]
Descriptor = Annotated[str, _stripped(MAX_DESCRIPTOR_CHARS), AfterValidator(_one_line)]


class RoleCreate(BaseModel):
    """A new Draft role."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=MAX_TITLE_CHARS)
    job_description: str = Field(min_length=1, max_length=MAX_JOB_DESCRIPTION_CHARS)


class RubricLevelIn(BaseModel):
    """One rubric level in a PUT; lenient on count, strict on content."""

    model_config = ConfigDict(extra="forbid")

    level: StrictInt = Field(ge=min(LEVELS), le=max(LEVELS))
    descriptor: Descriptor


class CriterionIn(BaseModel):
    """One criterion in a PUT; `id` set edits in place, absent creates."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID | None = None
    name: Name
    kind: str
    weight: StrictInt = Field(ge=MIN_WEIGHT, le=MAX_WEIGHT)
    rubric: list[RubricLevelIn] = Field(max_length=len(LEVELS))

    @field_validator("kind")
    @classmethod
    def _kind(cls, value: str) -> str:
        if value not in KINDS:
            raise ValueError(f"must be one of {', '.join(KINDS)}")
        return value

    @model_validator(mode="after")
    def _distinct_levels(self) -> Self:
        levels = [r.level for r in self.rubric]
        if len(set(levels)) != len(levels):
            raise ValueError("rubric levels must be distinct")
        return self


class CriteriaReplace(BaseModel):
    """The whole criteria set of a role."""

    model_config = ConfigDict(extra="forbid")

    criteria: list[CriterionIn] = Field(min_length=MIN_CRITERIA, max_length=MAX_CRITERIA)

    @model_validator(mode="after")
    def _unique(self) -> Self:
        names = [" ".join(c.name.split()).casefold() for c in self.criteria]
        if len(set(names)) != len(names):
            raise ValueError("criterion names must be unique")
        ids = [c.id for c in self.criteria if c.id is not None]
        if len(set(ids)) != len(ids):
            raise ValueError("criterion ids must be unique")
        return self


class ApproveRequest(BaseModel):
    """The criteria version the recruiter saw."""

    model_config = ConfigDict(extra="forbid")

    criteria_version: StrictInt = Field(ge=1)


class RoleOut(BaseModel):
    """A role without its criteria."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    job_description: str
    status: Literal["draft", "approved"]
    criteria_version: int
    created_at: datetime
    updated_at: datetime


class RubricLevelOut(BaseModel):
    """One rubric level."""

    level: int
    descriptor: str


class CriterionOut(BaseModel):
    """A live criterion with its rubric."""

    id: uuid.UUID
    name: str
    kind: Literal["must_have", "nice_to_have"]
    weight: float
    position: int
    rubric: list[RubricLevelOut]


class RoleDetail(RoleOut):
    """A role with its live criteria in display order."""

    criteria: list[CriterionOut]


class RoleList(BaseModel):
    """The list envelope."""

    data: list[RoleOut]
