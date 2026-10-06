"""Request and response models for POST /v1/roles/{id}/resumes (api/openapi.yaml UploadResponse)."""

import uuid
from typing import Literal

from pydantic import BaseModel


class UploadFileResult(BaseModel):
    """What happened to one uploaded file; `file_name` is echoed here and nowhere else."""

    file_name: str
    status: Literal["accepted", "rejected", "role_not_approved"]
    candidate_id: uuid.UUID | None = None
    candidate_no: int | None = None
    duplicate_of_candidate_no: int | None = None
    reason: str | None = None


class UploadResponse(BaseModel):
    """One result per file, in the order the files were sent."""

    results: list[UploadFileResult]
