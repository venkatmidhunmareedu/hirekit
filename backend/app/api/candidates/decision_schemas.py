"""Models for the recruiter decisions: override, stage, reveal (api/openapi.yaml)."""

import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

Stage = Literal["new", "screened", "interview", "offer", "hired", "rejected", "withdrawn"]
# The database refuses a note whose trimmed length is under 10, so the trim is applied here too.
Note = Annotated[str, StringConstraints(strip_whitespace=True, min_length=10)]


class OverrideRequest(BaseModel):
    """A new 0 to 4 score and the reason for it."""

    model_config = ConfigDict(extra="forbid")

    override_score: Annotated[int, Field(ge=0, le=4)]
    note: Note


class StageRequest(BaseModel):
    """The stage to move to and an optional reason."""

    model_config = ConfigDict(extra="forbid")

    stage: Stage
    reason: str | None = None

    @field_validator("reason")
    @classmethod
    def _blank_is_none(cls, value: str | None) -> str | None:
        return (value or "").strip() or None


class ScoreCell(BaseModel):
    """One criterion's score after an override."""

    criterion_id: uuid.UUID
    criterion_name: str
    kind: Literal["must_have", "nice_to_have"]
    status: Literal["scored", "no_evidence", "failed"]
    model_score: int | None
    override_score: int | None
    source: Literal["recruiter_override"]
    stale: bool
    quote: str | None
    flag_reason: str | None
    override_note: str | None


class StageChanged(BaseModel):
    """The move that was recorded."""

    candidate_id: uuid.UUID
    from_stage: Stage
    to_stage: Stage


class Identity(BaseModel):
    """Personal data; only the reveal route returns it."""

    identity_name: str | None
    file_name: str
