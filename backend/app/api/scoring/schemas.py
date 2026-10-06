"""Responses for POST /v1/candidates/{id}:retry and POST /v1/roles/{id}:rescore."""

from pydantic import BaseModel


class JobAccepted(BaseModel):
    """The id of the job that was enqueued."""

    job_id: int


class RescoreAccepted(BaseModel):
    """The jobs enqueued and the candidate numbers skipped because a scoring job was open."""

    job_ids: list[int]
    skipped_candidate_nos: list[int]
