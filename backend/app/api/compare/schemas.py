"""Response models for GET /v1/compare (the spec's Comparison)."""

import uuid
from typing import Literal

from pydantic import BaseModel


class CompareFeedback(BaseModel):
    interviewer_id: uuid.UUID
    criterion_id: uuid.UUID
    score: int
    comment: str
    locked: bool


class CompareCell(BaseModel):
    criterion_id: uuid.UUID
    model_score: int | None
    override_score: int | None
    feedback: list[CompareFeedback]
    disagreement: bool


class CompareCriterion(BaseModel):
    id: uuid.UUID
    name: str
    kind: Literal["must_have", "nice_to_have"]


class CompareCandidate(BaseModel):
    candidate_id: uuid.UUID
    candidate_no: int
    cells: list[CompareCell]


class Comparison(BaseModel):
    criteria: list[CompareCriterion]
    candidates: list[CompareCandidate]
