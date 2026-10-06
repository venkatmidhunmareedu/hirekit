"""Models for the assignment routes and GET /v1/me/candidates (api/openapi.yaml)."""

import uuid

from pydantic import BaseModel, ConfigDict


class AssignRequest(BaseModel):
    """The interviewer to assign."""

    model_config = ConfigDict(extra="forbid")

    user_id: uuid.UUID


class Assignment(BaseModel):
    """One interviewer assigned to one candidate."""

    candidate_id: uuid.UUID
    user_id: uuid.UUID


class MyCandidate(BaseModel):
    """What an interviewer sees of an assigned candidate: no name, file, score or quote."""

    candidate_id: uuid.UUID
    candidate_no: int
    role_id: uuid.UUID
    role_title: str
    has_submitted: bool


class MyCandidates(BaseModel):
    """The caller's assigned candidates."""

    data: list[MyCandidate]
