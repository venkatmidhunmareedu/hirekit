"""GET /v1/jobs/{id}, POST /v1/jobs/{id}:cancel, GET /v1/roles/{id}/queue."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.api.jobs.deps import Jobs
from app.api.jobs.schemas import Job, QueueView
from app.api.roles.router import Db, Roles, errors
from app.core.auth import RecruiterUser
from app.domain.jobs import service

NO_STORE = "no-store"
jobs_router = APIRouter(prefix="/v1/jobs", tags=["jobs"])
queue_router = APIRouter(prefix="/v1/roles", tags=["resumes"])


@jobs_router.get("/{job_id}", response_model=Job, responses=errors(404))
async def get_job(job_id: int, _: RecruiterUser, jobs: Jobs, response: Response) -> Job:
    """A job's status."""
    response.headers["Cache-Control"] = NO_STORE
    return await service.get_job(jobs, job_id)


@jobs_router.post("/{job_id}:cancel", response_model=Job, responses=errors(404, 409))
async def cancel_job(job_id: int, _: RecruiterUser, db: Db, jobs: Jobs, response: Response) -> Job:
    """Cancel a queued or running job."""
    response.headers["Cache-Control"] = NO_STORE
    return await service.cancel_job(db, jobs, job_id)


@queue_router.get("/{role_id}/queue", response_model=QueueView, responses=errors(404, 422))
async def get_queue(
    role_id: uuid.UUID,
    _: RecruiterUser,
    roles: Roles,
    jobs: Jobs,
    response: Response,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> QueueView:
    """Per-file status for the role, newest first, with job-based counts."""
    response.headers["Cache-Control"] = NO_STORE
    return await service.queue(roles, jobs, role_id, limit)
