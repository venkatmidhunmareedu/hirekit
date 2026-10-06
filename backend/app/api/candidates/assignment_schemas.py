"""Models for the assignment routes, the interviewer list and GET /v1/me/candidates."""

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


class InterviewerOption(BaseModel):
    """An interviewer a recruiter may assign: id and display name, never the email."""

    id: uuid.UUID
    name: str


class InterviewerList(BaseModel):
    """The interviewers a recruiter can pick from."""

    data: list[InterviewerOption]


class CandidateAssignment(BaseModel):
    """One interviewer currently assigned to a candidate."""

    user_id: uuid.UUID
    name: str


class CandidateAssignments(BaseModel):
    """A candidate's assigned interviewers."""

    data: list[CandidateAssignment]
