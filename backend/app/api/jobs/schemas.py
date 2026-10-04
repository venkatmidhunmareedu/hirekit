"""Request and response shapes of the job routes (api/openapi.yaml)."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

JobType = Literal[
    "process_resume", "propose_criteria", "generate_kit", "regenerate_question", "rescore"
]
JobStatus = Literal["queued", "running", "succeeded", "failed", "stale", "cancelled"]
ProcessingStatus = Literal["queued", "parsing", "anonymizing", "scoring", "done", "failed"]


class JobAccepted(BaseModel):
    """202 body: the id the Web polls."""

    job_id: int


class Job(BaseModel):
    """One job; `candidate_no` is the number, never a file name."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    type: JobType
    status: JobStatus
    role_id: uuid.UUID
    candidate_no: int | None
    criteria_version: int
    attempt: int
    last_error: str | None
    created_at: datetime


class QueueItem(BaseModel):
    """One candidate of the role with its latest scoring job."""

    model_config = ConfigDict(from_attributes=True)

    candidate_id: uuid.UUID
    candidate_no: int
    processing_status: ProcessingStatus
    failure_reason: str | None
    job: Job | None


class QueueView(BaseModel):
    """The per-role queue: items plus job-based counts."""

    data: list[QueueItem]
    waiting: int
    running: int
