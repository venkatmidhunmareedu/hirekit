"""Request and response models for the kit routes (api/openapi.yaml Kit, Question, JobAccepted)."""

import uuid
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


class QuestionOut(BaseModel):
    """One question with what a strong and a weak answer look like."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    criterion_id: uuid.UUID
    question_text: str
    strong_answer: str
    weak_answer: str
    position: int


class KitOut(BaseModel):
    """The kit; `stale` is derived from the criteria version, never stored."""

    role_id: uuid.UUID
    stale: bool
    criteria_version: int
    questions: list[QuestionOut]


class QuestionUpdate(BaseModel):
    """Fields to change in place; at least one, none null."""

    model_config = ConfigDict(extra="forbid")

    question_text: Text | None = None
    strong_answer: Text | None = None
    weak_answer: Text | None = None
    position: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _something_to_change(self) -> Self:
        sent = self.model_fields_set
        if not sent or any(getattr(self, name) is None for name in sent):
            raise ValueError("send at least one field, and none of them null")
        return self


class JobAccepted(BaseModel):
    """The id of the enqueued job, polled at GET /v1/jobs/{id}."""

    job_id: int
