"""Response models for the ranked list, the detail and the resume text (api/openapi.yaml)."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

Stage = Literal["new", "screened", "interview", "offer", "hired", "rejected", "withdrawn"]
ProcessingStatus = Literal["queued", "parsing", "anonymizing", "scoring", "done", "failed"]


class ScoreCell(BaseModel):
    """One criterion's score; quote, flag reason and note are null for an interviewer."""

    criterion_id: uuid.UUID
    criterion_name: str
    kind: Literal["must_have", "nice_to_have"]
    status: Literal["scored", "no_evidence", "failed"]
    model_score: int | None
    override_score: int | None
    source: Literal["model_suggestion", "no_evidence_found", "recruiter_override", "failed"]
    stale: bool
    quote: str | None
    flag_reason: str | None
    override_note: str | None


class RankedCandidate(BaseModel):
    """One row of the ranked list; identified by `candidate_no`, never by name."""

    id: uuid.UUID
    candidate_no: int
    stage: Stage
    processing_status: ProcessingStatus
    failure_reason: str | None
    total: float
    must_have_covered: int
    must_have_total: int
    stale: bool
    duplicate_of_candidate_no: int | None
    scores: list[ScoreCell]


class Page(BaseModel):
    limit: int
    offset: int
    total: int


class RankedList(BaseModel):
    data: list[RankedCandidate]
    page: Page


class AuditEvent(BaseModel):
    id: int
    kind: Literal[
        "score_override",
        "stage_change",
        "identity_reveal",
        "feedback_edit_approved",
        "feedback_edited",
    ]
    actor_id: uuid.UUID
    criterion_name: str | None
    old_score: int | None
    new_score: int | None
    from_stage: Stage | None
    to_stage: Stage | None
    note: str | None
    created_at: datetime


class CandidateDetail(BaseModel):
    """Built with only the fields the viewer may see; the route drops the unset ones."""

    id: uuid.UUID
    candidate_no: int
    role_id: uuid.UUID
    stage: Stage | None = None
    processing_status: ProcessingStatus | None = None
    scores: list[ScoreCell] | None = None
    audit: list[AuditEvent] | None = None
    has_submitted: bool | None = None


class CandidateText(BaseModel):
    raw_text: str
    anonymized_text: str
