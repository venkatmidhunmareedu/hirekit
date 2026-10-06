"""Request and response models for the feedback routes (api/openapi.yaml FeedbackList)."""

import uuid
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictInt


class FeedbackItem(BaseModel):
    """One criterion's score and comment."""

    model_config = ConfigDict(extra="forbid")

    criterion_id: uuid.UUID
    score: Annotated[StrictInt, Field(ge=0, le=4)]
    comment: Annotated[str, Field(min_length=1)]


class FeedbackSubmit(BaseModel):
    """Feedback for every live criterion of the candidate's role."""

    model_config = ConfigDict(extra="forbid")

    items: Annotated[list[FeedbackItem], Field(min_length=1)]


class FeedbackRow(BaseModel):
    """One stored feedback row."""

    interviewer_id: uuid.UUID
    criterion_id: uuid.UUID
    score: int
    comment: str
    locked: bool


class FeedbackList(BaseModel):
    """Feedback rows, ordered by interviewer then criterion position."""

    data: list[FeedbackRow]
